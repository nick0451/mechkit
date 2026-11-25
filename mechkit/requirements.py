"""Requirements a build must meet, as data, checked against the reports the pipeline writes.

`requirements.json` in a project:

    {"requirements": [
       {"id": "R1", "text": "Does not tip when a switch is flicked", "check": {"type": "stability_min_ratio", "min": 1.5}},
       {"id": "R2", "text": "Prints in under a day", "check": {"type": "print_time_max_h", "max": 24}},
       {"id": "R3", "text": "Feels solid", "check": {"type": "manual"}, "result": {"status": "pass", "by": "user", "date": "..."}} ]}

    python -m mechkit check <project folder> [--reports <folder with the report files>]

Each check reads one report file (the newest export folder by default): stability.json, print_estimates.json,
sim_report.json, mount_checks.json. A missing report gives "not evaluated", never a silent pass.
Statuses: pass | fail | not evaluated | manual (waiting for a person).
"""

import json
import re
from pathlib import Path


def _load(folders, name):
    """The first copy of a report file found in the given folder(s)."""
    for folder in folders if isinstance(folders, (list, tuple)) else [folders]:
        path = Path(folder) / name
        if path.is_file():
            return json.loads(path.read_text(encoding="utf-8"))
    return None


def _stability_min_ratio(check, reports):
    s = _load(reports, "stability.json")
    if s is None:
        return "not evaluated", "no stability.json"
    worst = s["worst"]
    ratio = worst["tips_at_n"] / worst["force_n"]
    return ("pass" if ratio >= check["min"] else "fail"), "weakest: %s tips at %.1f N = %.2fx its assumed %.1f N (need %.2fx)" % (
        worst["action"], worst["tips_at_n"], ratio, worst["force_n"], check["min"])


def _print_time_max_h(check, reports):
    e = _load(reports, "print_estimates.json")
    if e is None or e.get("problems"):
        return "not evaluated", "no usable print_estimates.json"
    hours = e["total_seconds"] / 3600.0
    return ("pass" if hours <= check["max"] else "fail"), "%.1f h estimated (limit %.1f h)" % (hours, check["max"])


def _filament_max_g(check, reports):
    e = _load(reports, "print_estimates.json")
    if e is None or e.get("problems"):
        return "not evaluated", "no usable print_estimates.json"
    return ("pass" if e["total_g"] <= check["max"] else "fail"), "%.0f g estimated (limit %.0f g)" % (e["total_g"], check["max"])


def _parts_fit_bed(check, reports):
    e = _load(reports, "print_estimates.json")
    if e is None:
        return "not evaluated", "no print_estimates.json"
    bed = check["bed_mm"]
    big = [f["file"] for f in e["files"] if f.get("size") and max(f["size"]) > bed]      # sizes are as printed (x, y, z)
    unknown = [f["file"] for f in e["files"] if not f.get("size")]
    if unknown:
        return "not evaluated", "no size recorded for %s" % unknown[:3]
    return ("pass" if not big else "fail"), "%d files on a %g mm bed%s" % (len(e["files"]), bed, "; too big: %s" % big if big else "")


def _strength_min_safety_factor(check, reports):
    s = _load(reports, "sim_report.json")
    if s is None:
        return "not evaluated", "no sim_report.json"
    cases = [c for c in s["cases"] if check.get("case") in (None, c["case"])]
    if not cases:
        return "not evaluated", "no matching load case"
    worst = min(cases, key=lambda c: c.get("safety_factor", 0))
    status = "pass" if worst.get("safety_factor", 0) >= check["min"] else "fail"
    tag = worst.get("material", {}).get("tag", "assumed")
    if status == "pass" and tag != "calibrated" and check.get("calibrated_only", True):
        return "not evaluated", "safety factor %.2f, but the material is only '%s': calibrate before relying on it" % (worst["safety_factor"], tag)
    return status, "lowest safety factor %.2f in case %s (need %.2f; material %s)" % (worst.get("safety_factor", 0), worst["case"], check["min"], tag)


def _mounts_pass(check, reports):
    rows = _load(reports, "mount_checks.json")
    if rows is None:
        return "not evaluated", "no mount_checks.json"
    bad = [r for r in rows if not r[3]]
    return ("pass" if not bad else "fail"), "%d mount checks, %d failed" % (len(rows), len(bad))


CHECKS = {
    "stability_min_ratio": _stability_min_ratio,
    "print_time_max_h": _print_time_max_h,
    "filament_max_g": _filament_max_g,
    "parts_fit_bed": _parts_fit_bed,
    "strength_min_safety_factor": _strength_min_safety_factor,
    "mounts_pass": _mounts_pass,
}


def newest_export(project):
    folders = [p for p in (Path(project) / "exports").glob("*_v*") if p.is_dir() and re.search(r"_v(\d+)$", p.name)]
    return max(folders, key=lambda p: int(re.search(r"_v(\d+)$", p.name).group(1))) if folders else None


def evaluate(requirements, reports):
    """[{id, text, status, detail}] for a list of requirement dicts against a folder of report files."""
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
            status, detail = CHECKS[kind](check, reports)
        out.append({"id": r["id"], "text": r["text"], "status": status, "detail": detail})
    return out


def check_project(project, reports=None):
    project = Path(project)
    if not (project / "requirements.json").is_file():
        raise SystemExit("%s has no requirements.json (see mechkit/templates/requirements.json for the layout)" % project)
    data = json.loads((project / "requirements.json").read_text(encoding="utf-8"))
    reports = Path(reports) if reports else newest_export(project)
    places = [p for p in (reports, project / "sim" / "reports") if p is not None and Path(p).is_dir()]     # export folder, then sim reports
    return evaluate(data["requirements"], places or None), reports


def print_results(results, reports):
    print("requirements checked against: %s" % (reports or "(no reports yet)"))
    for r in results:
        print("  %-4s %-14s %s" % (r["id"], r["status"].upper() if r["status"] == "fail" else r["status"], r["text"]))
        print("        %s" % r["detail"])
    counts = {}
    for r in results:
        counts[r["status"]] = counts.get(r["status"], 0) + 1
    print(", ".join("%d %s" % (n, s) for s, n in sorted(counts.items())))
