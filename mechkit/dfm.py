"""Manufacturability and geometry checks, done by text-to-cad's `cad` library.

    text-to-cad, MIT licence, Copyright (c) earthtojake: https://github.com/earthtojake/text-to-cad
    MechKit uses it as an installed dependency (pinned in pyproject.toml); none of its code is copied here.

What MechKit calls, and what it turns each result into (one plain dict per part, for reports and requirements):

    printing(parts, ...)        cad.build123d.printing: overhangs, walls, bed contact, bridges, build volume (FDM / SLA ...)
    sheet_metal(parts, ...)     cad.build123d.sheet_metal: bends, flanges, holes near bends, sheet size
    laser_dxf(path, ...)        cad.dxf.dfm: a cut file for laser / waterjet / router: closed contours, double cuts,
                                holes, slots and webs against the kerf and the thickness
    flat_pattern(shape, ...)    cad.build123d.unfold: a bent sheet part's exact flat pattern, written as DXF
    geometry(parts)             is_sound, topology_errors, self_intersections: is each solid usable geometry

Rules: text-to-cad's GENERAL rules (each finding names its source, e.g. Protolabs Network design guides). They are not
the user's printer's or a shop's limits: every report says so in "rules", and a result never stands in for a test print.

Fail closed: a check that raises, or that the library reports as not_checked, is "not evaluated", never a pass.
Telemetry: the library itself sends nothing (only its `cad` command does); DO_NOT_TRACK=1 is set anyway.
"""

import json
import os
from pathlib import Path

CHECKER = "text-to-cad cad"
RULES = "text-to-cad general rules (published design guides, cited per finding); not a named shop's or this printer's limits"
_STATUS = {"ok": "pass", "failed": "fail", "not_checked": "not evaluated"}


def _cad():
    os.environ.setdefault("DO_NOT_TRACK", "1")
    import cad
    import cad.build123d as cb
    return cad, cb


def version():
    try:
        from importlib.metadata import version as v
        return v("cad")
    except Exception:
        return "unknown"


def _issue(i):
    return {k: getattr(i, k, None) for k in ("severity", "code", "message", "location", "hint", "rule", "value", "limit", "unit", "source")}


def entry(result):
    """One CheckResult as a plain dict: status pass | fail | not evaluated, counts, findings (info dropped), summary."""
    status = _STATUS.get(getattr(result, "status", ""), "not evaluated")
    issues = [_issue(i) for i in getattr(result, "issues", []) or []]
    return {"status": status, "reason": getattr(result, "reason", None),
            "errors": sum(1 for i in issues if i["severity"] == "error"),
            "warnings": sum(1 for i in issues if i["severity"] == "warning"),
            "issues": [i for i in issues if i["severity"] in ("error", "warning")],
            "summary": getattr(result, "summary", "")}


def _guarded(fn):
    try:
        return entry(fn())
    except Exception as e:                                   # a check that could not run is not a pass
        return {"status": "not evaluated", "reason": "%s: %s" % (type(e).__name__, e), "errors": 0, "warnings": 0,
                "issues": [], "summary": "check could not run"}


def _report(process, parts, settings):
    statuses = [p["status"] for p in parts.values()]
    overall = "fail" if "fail" in statuses else ("pass" if statuses and all(s == "pass" for s in statuses) else "not evaluated")
    return {"process": process, "checker": "%s %s" % (CHECKER, version()), "rules": RULES, "settings": settings,
            "status": overall, "parts": parts}


def printing(parts, material="petg", technology="fdm", **options):
    """{name: solid IN ITS PRINT ORIENTATION, on z = 0} -> printing report. options: build_volume, angle_limit,
    layer_height, nozzle, printer (passed to cad.build123d.printing)."""
    _, cb = _cad()
    settings = dict(material=material, technology=technology, **options)
    return _report("printing", {n: _guarded(lambda s=s: cb.printing(s, **settings)) for n, s in parts.items()}, settings)


def sheet_metal(parts, material=None, thickness=None, k_factor=None, bend_radius=None, kerf=None, sheet_size=None):
    """{name: bent sheet solid} -> sheet-metal report."""
    _, cb = _cad()
    settings = {k: v for k, v in dict(material=material, thickness=thickness, k_factor=k_factor, bend_radius=bend_radius,
                                      kerf=kerf, sheet_size=sheet_size).items() if v is not None}
    return _report("sheet", {n: _guarded(lambda s=s: cb.sheet_metal(s, **settings)) for n, s in parts.items()}, settings)


def laser_dxf(paths, material=None, thickness=None, kerf=None, units="mm", sheet_size=None):
    """{name: DXF path} (or one path) -> cut-file report for laser / waterjet / router cutting."""
    cad, _ = _cad()
    import cad.dxf
    if isinstance(paths, (str, Path)):
        paths = {Path(paths).stem: paths}
    settings = {k: v for k, v in dict(material=material, thickness=thickness, kerf=kerf, units=units, sheet_size=sheet_size).items() if v is not None}
    return _report("laser", {n: _guarded(lambda p=p: cad.dxf.dfm(Path(p), **settings)) for n, p in paths.items()}, settings)


def flat_pattern(shape, out, thickness=None, k_factor=None, material=None, bend_lines=False):
    """Unfold a bent sheet part and write its flat pattern as DXF (mm). Returns the path. Raises when it cannot unfold:
    a flat pattern that could not be made is never written."""
    _, cb = _cad()
    import build123d as bd
    flat = cb.unfold(shape, thickness=thickness, k_factor=k_factor, material=material, bend_lines=bend_lines)
    return write_dxf(flat, out)


def write_dxf(shape_2d, out):
    """Write a flat (XY) shape or face as a DXF cut file, outlines on layer CUT, in mm."""
    import build123d as bd
    out = Path(out)
    out.parent.mkdir(parents=True, exist_ok=True)
    exporter = bd.ExportDXF(unit=bd.Unit.MM)
    exporter.add_layer("CUT")
    exporter.add_shape(shape_2d, layer="CUT")
    tmp = out.with_name(out.name + ".tmp")
    exporter.write(str(tmp))
    tmp.replace(out)
    return out


def geometry(parts):
    """{name: solid} -> {name: {status, sound, topology_errors, self_intersections}}: is each solid usable geometry."""
    _, cb = _cad()
    out = {}
    for n, s in parts.items():
        try:
            topo = [str(i) for i in cb.topology_errors(s)]
            selfx = [str(i) for i in cb.self_intersections(s)]
            sound = bool(cb.is_sound(s))
            out[n] = {"status": "pass" if sound and not topo and not selfx else "fail", "sound": sound,
                      "topology_errors": topo[:10], "self_intersections": selfx[:10]}
        except Exception as e:
            out[n] = {"status": "not evaluated", "reason": "%s: %s" % (type(e).__name__, e)}
    return out


def write_report(folder, report):
    """Write dfm_report.json whole, then swap it in. Returns the path."""
    folder = Path(folder)
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / "dfm_report.json"
    tmp = folder / "dfm_report.json.tmp"
    tmp.write_text(json.dumps(report, indent=1, default=str), encoding="utf-8", newline="\n")
    tmp.replace(path)
    return path


def problems(report):
    """Lines for a build's problem list: geometry that is not sound, and DFM errors (warnings are for the pre-print review)."""
    out = []
    for n, g in (report.get("geometry") or {}).items():
        if g["status"] != "pass":
            out.append("geometry %s: %s" % (n, g.get("reason") or "not sound (%s)" % "; ".join((g.get("topology_errors") or []) + (g.get("self_intersections") or []))[:200]))
    for key in ("printing", "sheet", "laser"):
        r = report.get(key)
        if not r:
            continue
        for n, e in r["parts"].items():
            if e["status"] == "fail":
                out.append("%s %s: %d error(s): %s" % (key, n, e["errors"], "; ".join("%s at %s" % (i["code"], i["location"]) for i in e["issues"] if i["severity"] == "error")[:200]))
            elif e["status"] != "pass":
                out.append("%s %s: not evaluated (%s)" % (key, n, e.get("reason")))
    return out
