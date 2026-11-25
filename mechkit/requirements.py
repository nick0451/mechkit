"""Requirements a build must meet, as data, checked against the reports the pipeline writes.

`requirements.json` in a project:

    {"requirements": [
       {"id": "R1", "text": "Does not tip when a switch is flicked", "check": {"type": "stability_min_ratio", "min": 1.5}},
       {"id": "R2", "text": "Prints in under a day", "check": {"type": "print_time_max_h", "max": 24}},
       {"id": "R3", "text": "Feels solid", "check": {"type": "manual"}, "result": {"status": "pass", "by": "user", "date": "..."}} ]}

    python -m mechkit check <project folder> [--reports <folder with the report files>]

Each check reads one report file (the newest export folder by default): stability.json, print_estimates.json,
sim_report.json, mount_checks.json, dfm_report.json. A missing report gives "not evaluated", never a silent pass.
Statuses: pass | fail | not evaluated | manual (waiting for a person).
`python -m mechkit check` exits 0 only when every requirement passes, 1 when any fails, 2 when none fails but some are
not evaluated or still waiting for a person: an unchecked requirement is never reported as success.

A strength result counts only when it is clean and current: no problems or solver warnings, the two mesh sizes agree,
the STEP file simulated is byte-for-byte the one in the project now (sha256), and the material is calibrated with a
calibration record. Otherwise it is "not evaluated" (or "fail" when it failed).
"""

import hashlib
import json
from pathlib import Path

from . import revisions


def _load(folders, name):
    """The first copy of a report file found in the given folder(s)."""
    for folder in folders if isinstance(folders, (list, tuple)) else [folders]:
        path = Path(folder) / name
        if path.is_file():
            return json.loads(path.read_text(encoding="utf-8"))
    return None


def _stability_min_ratio(check, reports, project=None):
    s = _load(reports, "stability.json")
    if s is None:
        return "not evaluated", "no stability.json"
    worst = s["worst"]
    ratio = worst["tips_at_n"] / worst["force_n"]
    return ("pass" if ratio >= check["min"] else "fail"), "weakest: %s tips at %.1f N = %.2fx its assumed %.1f N (need %.2fx)" % (
        worst["action"], worst["tips_at_n"], ratio, worst["force_n"], check["min"])


def _print_time_max_h(check, reports, project=None):
    e = _load(reports, "print_estimates.json")
    if e is None or e.get("problems"):
        return "not evaluated", "no usable print_estimates.json"
    hours = e["total_seconds"] / 3600.0
    return ("pass" if hours <= check["max"] else "fail"), "%.1f h estimated (limit %.1f h)" % (hours, check["max"])


def _filament_max_g(check, reports, project=None):
    e = _load(reports, "print_estimates.json")
    if e is None or e.get("problems"):
        return "not evaluated", "no usable print_estimates.json"
    return ("pass" if e["total_g"] <= check["max"] else "fail"), "%.0f g estimated (limit %.0f g)" % (e["total_g"], check["max"])


def _parts_fit_bed(check, reports, project=None):
    e = _load(reports, "print_estimates.json")
    if e is None:
        return "not evaluated", "no print_estimates.json"
    bed = check["bed_mm"]
    big = [f["file"] for f in e["files"] if f.get("size") and max(f["size"]) > bed]      # sizes are as printed (x, y, z)
    unknown = [f["file"] for f in e["files"] if not f.get("size")]
    if unknown:
        return "not evaluated", "no size recorded for %s" % unknown[:3]
    return ("pass" if not big else "fail"), "%d files on a %g mm bed%s" % (len(e["files"]), bed, "; too big: %s" % big if big else "")


def _sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _stale(case, project):
    """Why a case's result may not describe the current geometry, or None when it does."""
    if not case.get("step") or not case.get("step_sha256"):
        return "the result does not record which geometry it was run on: run the simulation again"
    if project is None:
        return "no project folder given, so the simulated geometry cannot be compared with the current one"
    step = Path(project) / case["step"]
    if not step.is_file():
        return "%s no longer exists" % case["step"]
    if _sha256(step) != case["step_sha256"]:
        return "%s changed after it was simulated: run the simulation again" % case["step"]
    return None


def _strength_min_safety_factor(check, reports, project=None):
    s = _load(reports, "sim_report.json")
    if s is None:
        return "not evaluated", "no sim_report.json"
    cases = [c for c in s["cases"] if check.get("case") in (None, c["case"])]
    if not cases:
        return "not evaluated", "no matching load case"
    if any(not isinstance(c.get("safety_factor"), (int, float)) for c in cases):
        return "not evaluated", "a matching case has no safety factor"
    worst = min(cases, key=lambda c: c["safety_factor"])
    tag = worst.get("material", {}).get("tag", "assumed")
    detail = "lowest safety factor %.2f in case %s (need %.2f; material %s)" % (worst["safety_factor"], worst["case"], check["min"], tag)
    failed = ["%s: %s" % (c["case"], p) for c in cases for p in c.get("problems", [])]
    if worst["safety_factor"] < check["min"] or failed:
        return "fail", detail + ("; " + "; ".join(failed) if failed else "")
    for c in cases:                                            # a pass counts only when every matching case is clean
        stale = _stale(c, project)
        if stale:
            return "not evaluated", "%s: %s" % (c["case"], stale)
        if not c.get("converged", False):
            return "not evaluated", "%s: the mesh sizes disagree (stress on a sharp corner): refine before relying on it" % c["case"]
        solver = [w for w in c.get("warnings", []) if w.startswith("SOLVER")]
        if solver:
            return "not evaluated", "%s: solver warning: %s" % (c["case"], solver[0])
    if check.get("calibrated_only", True):
        m = worst.get("material", {})
        if tag != "calibrated":
            return "not evaluated", "safety factor %.2f, but the material is only '%s': calibrate before relying on it" % (worst["safety_factor"], tag)
        if not m.get("calibration"):
            return "not evaluated", "safety factor %.2f, but material '%s' is tagged calibrated without a calibration record" % (worst["safety_factor"], m.get("name"))
    return "pass", detail


def _mounts_pass(check, reports, project=None):
    rows = _load(reports, "mount_checks.json")
    if rows is None:
        return "not evaluated", "no mount_checks.json"
    bad = [r for r in rows if not r[3]]
    return ("pass" if not bad else "fail"), "%d mount checks, %d failed" % (len(rows), len(bad))


def _dfm_ok(check, reports, project=None):
    """{"type": "dfm_ok", "process": "printing" | "sheet" | "laser", "max_warnings": N (optional)}: dfm_report.json."""
    r = _load(reports, "dfm_report.json")
    proc = check.get("process", "printing")
    if r is None or not r.get(proc):
        return "not evaluated", "no %s check in dfm_report.json" % proc
    parts = r[proc]["parts"]
    failed = [n for n, e in parts.items() if e["status"] == "fail"]
    unchecked = [n for n, e in parts.items() if e["status"] != "pass" and e["status"] != "fail"]
    warnings = sum(e.get("warnings", 0) for e in parts.values())
    detail = "%d parts, %d failed, %d not evaluated, %d warnings (%s; %s)" % (len(parts), len(failed), len(unchecked), warnings,
                                                                          r[proc].get("checker"), "general rules, not a shop's")
    if failed:
        return "fail", detail + ": " + ", ".join(failed)
    if unchecked or not parts:
        return "not evaluated", detail + (": " + ", ".join(unchecked) if unchecked else "")
    if "max_warnings" in check and warnings > check["max_warnings"]:
        return "fail", detail + " (limit %d warnings)" % check["max_warnings"]
    return "pass", detail


def _geometry_sound(check, reports, project=None):
    """{"type": "geometry_sound"}: every solid in dfm_report.json's geometry section is valid, closed, not self-intersecting."""
    r = _load(reports, "dfm_report.json")
    g = (r or {}).get("geometry")
    if not g:
        return "not evaluated", "no geometry check in dfm_report.json"
    bad = [n for n, v in g.items() if v["status"] == "fail"]
    unchecked = [n for n, v in g.items() if v["status"] not in ("pass", "fail")]
    if bad:
        return "fail", "not sound: %s" % ", ".join(bad)
    if unchecked:
        return "not evaluated", "could not check: %s" % ", ".join(unchecked)
    return "pass", "%d solids sound" % len(g)


CHECKS = {
    "stability_min_ratio": _stability_min_ratio,
    "print_time_max_h": _print_time_max_h,
    "filament_max_g": _filament_max_g,
    "parts_fit_bed": _parts_fit_bed,
    "strength_min_safety_factor": _strength_min_safety_factor,
    "mounts_pass": _mounts_pass,
    "dfm_ok": _dfm_ok,
    "geometry_sound": _geometry_sound,
}


def newest_export(project):
    return revisions.newest(project)


def evaluate(requirements, reports, project=None):
    """[{id, text, status, detail}] for a list of requirement dicts against a folder of report files.
    project: the project folder, needed to confirm that simulation results match the current geometry."""
    out = []
    for r in requirements:
        check = r.get("check", {"type": "manual"})
        kind = check.get("type", "manual")
        if kind == "manual":
            result = r.get("result") or {}
            status = result.get("status", "manual")
            detail = "confirmed by %s on %s" % (result.get("by"), result.get("date")) if result else "waiting for a person to check"
        elif kind not in CHECKS:
            status, detail = "not evaluated", "unknown check type '%s'" % kind
        elif reports is None:
            status, detail = "not evaluated", "no report folder yet"
        else:
            status, detail = CHECKS[kind](check, reports, project)
        out.append({"id": r["id"], "text": r["text"], "status": status, "detail": detail})
    return out


def check_project(project, reports=None):
    project = Path(project)
    if not (project / "requirements.json").is_file():
        raise SystemExit("%s has no requirements.json (see mechkit/templates/requirements.json for the layout)" % project)
    data = json.loads((project / "requirements.json").read_text(encoding="utf-8"))
    reports = Path(reports) if reports else newest_export(project)
    places = [p for p in (reports, project / "sim" / "reports") if p is not None and Path(p).is_dir()]     # export folder, then sim reports
    return evaluate(data["requirements"], places or None, project), reports


def print_results(results, reports):
    print("requirements checked against: %s" % (reports or "(no reports yet)"))
    for r in results:
        print("  %-4s %-14s %s" % (r["id"], r["status"].upper() if r["status"] == "fail" else r["status"], r["text"]))
        print("        %s" % r["detail"])
    counts = {}
    for r in results:
        counts[r["status"]] = counts.get(r["status"], 0) + 1
    print(", ".join("%d %s" % (n, s) for s, n in sorted(counts.items())))


def exit_code(results):
    """0 = every requirement passes, 1 = at least one fails, 2 = none fails but some are not evaluated or waiting."""
    if any(r["status"] == "fail" for r in results):
        return 1
    return 0 if all(r["status"] == "pass" for r in results) else 2
