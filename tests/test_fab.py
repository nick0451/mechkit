"""Capabilities adopted from text-to-cad (`cad` library, MIT): manufacturability checks, geometry soundness, laser cut
files, flat patterns, engineering drawings, and the requirement checks that read their report.

    uv run python tests/test_fab.py

Every check below has a known answer worked out by hand or a deliberately broken input (NEGATIVE), and the fail-closed
rule is tested: a check that cannot run is "not evaluated", never a pass.
"""

import json
import math
import os
import shutil
import sys
import tempfile
from pathlib import Path

KIT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(KIT))
import build123d as bd  # noqa: E402

from mechkit import dfm, drawing, requirements  # noqa: E402

results = []


def check(name, cond, detail=""):
    results.append(bool(cond))
    print("  %-4s %s  %s" % ("ok" if cond else "FAIL", name, "" if cond else str(detail)[:300]))


def plate(w, h, t):
    return bd.Pos(0, 0, t / 2) * bd.Box(w, h, t)


def main():
    tmp = Path(tempfile.mkdtemp(prefix="mechkit_fab_"))
    try:
        print("library and privacy")
        check("the cad library is the pinned version", dfm.version() == "0.11.17", dfm.version())
        dfm._cad()
        check("DO_NOT_TRACK is set before the library is used", os.environ.get("DO_NOT_TRACK") == "1")

        print("result mapping (fail closed)")
        Fake = type("Fake", (), {})

        def fake(status, issues=()):
            r = Fake()
            r.status, r.issues, r.reason, r.summary = status, list(issues), None, status
            return r
        issue = type("I", (), {"severity": "error", "code": "x", "message": "m", "location": "face 1", "hint": None,
                               "rule": "x", "value": 1, "limit": 2, "unit": "mm", "source": "s"})()
        check("ok -> pass", dfm.entry(fake("ok"))["status"] == "pass")
        check("failed -> fail, error counted", dfm.entry(fake("failed", [issue]))["status"] == "fail" and dfm.entry(fake("failed", [issue]))["errors"] == 1)
        check("NEGATIVE: not_checked -> not evaluated", dfm.entry(fake("not_checked"))["status"] == "not evaluated")
        check("NEGATIVE: an unknown status -> not evaluated", dfm.entry(fake("weird"))["status"] == "not evaluated")
        check("NEGATIVE: a check that raises -> not evaluated", dfm._guarded(lambda: 1 / 0)["status"] == "not evaluated")

        print("3D printing checks (FDM, 0.4 mm nozzle)")
        good = plate(40, 30, 4) - bd.Pos(0, 0, 2) * bd.Cylinder(3, 4)
        thin = plate(40, 30, 4) + bd.Pos(0, 0, 4 + 5) * bd.Box(30, 0.3, 10)          # a 0.3 mm fin standing on the plate
        r = dfm.printing({"good": good, "thin": thin}, material="petg", technology="fdm", nozzle=0.4)
        check("a plain plate with a hole passes", r["parts"]["good"]["status"] == "pass", r["parts"]["good"])
        check("NEGATIVE: a 0.3 mm wall fails with a wall error", r["parts"]["thin"]["status"] == "fail"
              and any(i["code"].startswith("printing.wall") and i["severity"] == "error" for i in r["parts"]["thin"]["issues"]), r["parts"]["thin"]["summary"])
        check("the report is 'fail' when one part fails", r["status"] == "fail")
        check("the report names the checker and that its rules are general", r["checker"].startswith("text-to-cad cad") and "not a named shop" in r["rules"])
        check("findings carry a cited source", all(i["source"] for i in r["parts"]["thin"]["issues"] if i["code"].startswith("printing.wall")))
        over = plate(40, 30, 4) + bd.Pos(0, 0, 20) * bd.Box(40, 30, 4) + bd.Pos(-18, 0, 12) * bd.Box(4, 30, 12)   # a shelf: flat underside
        r2 = dfm.printing({"shelf": over}, material="petg", technology="fdm", nozzle=0.4)
        check("a flat overhang is reported", any(i["code"] == "printing.overhang_angle" for i in r2["parts"]["shelf"]["issues"]), r2["parts"]["shelf"]["summary"])

        print("geometry soundness")
        g = dfm.geometry({"box": bd.Box(10, 10, 10), "two": bd.Compound([bd.Box(10, 10, 10), bd.Pos(5, 0, 0) * bd.Box(10, 10, 10)])})
        check("a box is sound", g["box"]["status"] == "pass", g["box"])
        check("NEGATIVE: two overlapping solids in one compound are not", g["two"]["status"] == "fail", g["two"])
        check("NEGATIVE: something that is not a shape -> not evaluated", dfm.geometry({"x": object()})["x"]["status"] == "not evaluated")

        print("laser cut files (3 mm acrylic, 0.2 mm kerf)")
        good2d = bd.Rectangle(100, 60) - bd.Pos(-35, 0) * bd.Circle(3) - bd.Pos(35, 0) * bd.Circle(3)
        small = good2d - bd.Pos(0, 20) * bd.Circle(0.4)
        paths = {"good": dfm.write_dxf(good2d, tmp / "good.dxf"), "small": dfm.write_dxf(small, tmp / "small.dxf")}
        import ezdxf
        doc = ezdxf.new()
        doc.layers.add("CUT")
        doc.modelspace().add_lwpolyline([(0, 0), (50, 0), (50, 30)], dxfattribs={"layer": "CUT"})     # not closed
        doc.saveas(tmp / "open.dxf")
        paths["open"] = tmp / "open.dxf"
        r = dfm.laser_dxf(paths, material="acrylic", thickness=3.0, kerf=0.2)
        check("a closed plate with two 6 mm holes passes", r["parts"]["good"]["status"] == "pass", r["parts"]["good"])
        check("a 0.8 mm hole in 3 mm sheet is warned about", r["parts"]["small"]["warnings"] >= 1
              and any(i["code"] == "sheet.hole_diameter" for i in r["parts"]["small"]["issues"]), r["parts"]["small"])
        check("NEGATIVE: an open contour does not pass", r["parts"]["open"]["status"] != "pass", r["parts"]["open"])
        check("NEGATIVE: a missing file -> not evaluated", dfm.laser_dxf(tmp / "missing.dxf")["status"] == "not evaluated")

        print("flat pattern of a bent bracket (2 mm, inside radius 2, K = 0.4)")
        t, ri, k = 2.0, 2.0, 0.4
        part = bd.Pos(20, 10, t / 2) * bd.Box(40, 20, t) + bd.Pos(t / 2, 10, 15) * bd.Box(t, 20, 30)
        outer = [e for e in part.edges().filter_by(bd.Axis.Y) if abs(e.center().X) < 1e-6 and abs(e.center().Z) < 1e-6]
        part = part.fillet(ri + t, outer)
        inner = [e for e in part.edges().filter_by(bd.Axis.Y) if abs(e.center().X - t) < 1e-6 and abs(e.center().Z - t) < 1e-6]
        part = part.fillet(ri, inner)
        out = dfm.flat_pattern(part, tmp / "bracket.dxf", thickness=t, k_factor=k)
        flat = ezdxf.readfile(out)
        xs = [p[0] for e in flat.modelspace() for p in ((e.dxf.start, e.dxf.end) if e.dxftype() == "LINE" else ())]
        want = (40 - ri - t) + (30 - ri - t) + math.pi / 2 * (ri + k * t)            # straight flanges + bend allowance
        got = max(xs) - min(xs) if xs else 0
        check("flat length = flanges + BA = %.3f mm (hand formula)" % want, abs(got - want) < 0.01, "%.3f" % got)
        s = dfm.sheet_metal({"bracket": part}, thickness=t)
        check("the bent bracket passes the sheet-metal check", s["parts"]["bracket"]["status"] == "pass", s["parts"]["bracket"])

        print("drawings: every number measured from the solid")
        block = bd.Box(60, 40, 10) - bd.Pos(-20, 0, 0) * bd.Cylinder(3, 10) - bd.Pos(20, 0, 0) * bd.Cylinder(3, 10)
        block = block - bd.Pos(0, 10, 2.5) * bd.Cylinder(2, 5)                         # blind 5 deep from the top
        block = block - bd.Pos(10, -10, -3) * bd.Cylinder(1.5, 4)                      # blind 4 deep from the bottom
        block = block - bd.Pos(-10, -10, 0) * bd.Cylinder(2, 10) - bd.Pos(-10, -10, 3.5) * bd.Cylinder(3, 3)   # stepped
        block = block + bd.Pos(0, -10, 7.5) * bd.Cylinder(4, 5)                        # boss: not a hole
        block = block.fillet(1.0, block.edges().filter_by(bd.Axis.Z).group_by(bd.Axis.X)[0])
        holes = {(h["diameter"], h["thru"], h["far_side"], tuple(h["steps"])): h for h in drawing.round_holes(block, 2)}
        check("two 6 mm through holes", sum(1 for h in drawing.round_holes(block, 2) if h["diameter"] == 6 and h["thru"]) == 2, holes.keys())
        check("a 4 mm blind hole, 5 deep, from the top", any(h["diameter"] == 4 and not h["thru"] and h["depth"] == 5 and not h["far_side"] for h in holes.values()))
        check("a 3 mm blind hole from the far side", any(h["diameter"] == 3 and h["far_side"] and h["depth"] == 4 for h in holes.values()))
        check("a stepped hole is one hole: 4 thru with a 6 x 3 step", any(h["diameter"] == 4 and h["thru"] and h["steps"] == [(6.0, 3.0)] for h in holes.values()), holes.keys())
        check("NEGATIVE: the boss and the fillets are not holes", all(h["diameter"] in (3, 4, 6) for h in holes.values()), holes.keys())
        sheet = drawing.part_sheet(block, "Test block", part_number="T-1", material="PETG", source="test")
        pdf = drawing.write(sheet, tmp / "block.pdf")
        check("the PDF is written", pdf.is_file() and pdf.read_bytes()[:4] == b"%PDF" and pdf.stat().st_size > 20000)
        check("the sheet says where its numbers came from", any("MEASURED FROM THE MODEL" in n for n in sheet.notes))
        big = bd.Box(300, 200, 150)
        bs = drawing.part_sheet(big, "Big", size="A3")
        check("a large part gets a reducing scale", bs.scale < 1.0, bs.scale)
        check("and still writes", drawing.write(bs, tmp / "big.pdf").is_file())

        print("requirements read the report")
        rep = {"printing": r_print_report(), "geometry": {"a": {"status": "pass"}, "b": {"status": "pass"}}}
        dfm.write_report(tmp / "rep", rep)
        ev = lambda c: requirements.evaluate([{"id": "D", "text": "t", "check": c}], [tmp / "rep"])[0]  # noqa: E731
        check("dfm_ok passes on a clean report", ev({"type": "dfm_ok", "process": "printing"})["status"] == "pass")
        check("max_warnings is enforced", ev({"type": "dfm_ok", "process": "printing", "max_warnings": 0})["status"] == "fail")
        check("geometry_sound passes", ev({"type": "geometry_sound"})["status"] == "pass")
        rep["printing"]["parts"]["b"]["status"] = "fail"
        rep["geometry"]["b"]["status"] = "not evaluated"
        dfm.write_report(tmp / "rep", rep)
        check("NEGATIVE: one failed part fails dfm_ok", ev({"type": "dfm_ok", "process": "printing"})["status"] == "fail")
        check("NEGATIVE: an unchecked solid -> geometry not evaluated", ev({"type": "geometry_sound"})["status"] == "not evaluated")
        rep["printing"]["parts"]["b"]["status"] = "not evaluated"
        dfm.write_report(tmp / "rep", rep)
        check("NEGATIVE: an unchecked part -> dfm_ok not evaluated", ev({"type": "dfm_ok", "process": "printing"})["status"] == "not evaluated")
        check("NEGATIVE: no laser section -> not evaluated", ev({"type": "dfm_ok", "process": "laser"})["status"] == "not evaluated")
        check("build problem lines list failures and unchecked parts", len(dfm.problems(rep)) == 2, dfm.problems(rep))

        print("isolation: nothing of the cad command or its telemetry was loaded")
        check("cad_server is not imported", not any(m == "cad_server" or m.startswith("cad_server.") for m in sys.modules),
              [m for m in sys.modules if m.startswith("cad_server")][:5])
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    print("\n%d checks, %d failed" % (len(results), results.count(False)))
    sys.exit(1 if False in results else 0)


def r_print_report():
    return {"process": "printing", "checker": "test", "rules": "test", "status": "pass", "settings": {},
            "parts": {"a": {"status": "pass", "warnings": 1, "errors": 0, "issues": []},
                      "b": {"status": "pass", "warnings": 0, "errors": 0, "issues": []}}}


if __name__ == "__main__":
    main()
