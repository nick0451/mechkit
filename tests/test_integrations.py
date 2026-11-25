"""Second set of adopted capabilities: standard hardware (bd_warehouse), tipping / sliding and mechanism travel
(MuJoCo + text-to-cad), CNC / moulding checks, clearance and mass, KiCad rule checks and board interface, slicing.

    uv run python tests/test_integrations.py

Known answers are worked by hand in the comments. Parts that need a program on the machine (KiCad, a slicer) are
skipped with a line saying so when it is absent, and tested for failing closed either way.
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

from mechkit import dfm, electronics, hardware, motion, requirements, slicer  # noqa: E402
from mechkit.kernel import b3d  # noqa: E402

results = []


def check(name, cond, detail=""):
    results.append(bool(cond))
    print("  %-4s %s  %s" % ("ok" if cond else "FAIL", name, "" if cond else str(detail)[:300]))


def raises(exc, fn):
    try:
        fn()
    except exc:
        return True
    return False


BOARD = '''(kicad_pcb (version 20221018) (generator pcbnew)
  (general (thickness 1.6))
  (paper "A4")
  (layers (0 "F.Cu" signal) (31 "B.Cu" signal) (44 "Edge.Cuts" user))
  (setup)
  (net 0 "") (net 1 "A")
  (footprint "MountingHole:MountingHole_3.2mm_M3" (layer "F.Cu") (at 4 4)
    (pad "" np_thru_hole circle (at 0 0) (size 3.2 3.2) (drill 3.2) (layers "*.Cu" "*.Mask")))
  (footprint "MountingHole:MountingHole_3.2mm_M3" (layer "F.Cu") (at 26 16)
    (pad "" np_thru_hole circle (at 0 0) (size 3.2 3.2) (drill 3.2) (layers "*.Cu" "*.Mask")))
  (gr_rect (start 0 0) (end 30 20) (stroke (width 0.1) (type default)) (fill none) (layer "Edge.Cuts"))
  (segment (start 8 %(y)s) (end 22 %(y)s) (width 0.25) (layer "F.Cu") (net 1))
)
'''


def main():
    tmp = Path(tempfile.mkdtemp(prefix="mechkit_integ_"))
    try:
        print("standard hardware (ISO 4762 M3: head 5.5 nominal / 5.68 max x 3.0, normal clearance hole 3.4)")
        s, f = hardware.screw("M3-0.5", 10)
        d = f["dims"]
        check("M3 socket head: thread 3.0, head about 5.5-5.7 x 3.0", d["thread_d"]["value"] == 3.0 and 5.4 <= d["head_d"]["value"] <= 5.7
              and abs(d["head_h"]["value"] - 3.0) < 0.01, d)
        check("clearance hole 3.4 (normal), tap hole 2.5", f["clearance_hole_d"]["normal"]["value"] == 3.4 and f["tap_hole_d"]["soft"]["value"] == 2.5)
        check("every number is tagged stated, with the standard as its source", all(v["tag"] == "stated" and "ISO 4762" in v["source"] for v in d.values()))
        bb = s.bounding_box()
        check("frame: head above z = 0, 10 mm shank below", abs(bb.min.Z + 10) < 0.01 and abs(bb.max.Z - 3.0) < 0.01, (bb.min.Z, bb.max.Z))
        check("the solid is valid and near a 3 mm rod + head in volume", s.is_valid and 100 < s.volume < 150, s.volume)
        check("NEGATIVE: a size the standard lacks is refused", raises(ValueError, lambda: hardware.screw("M3.7-0.5", 10)))
        check("NEGATIVE: an unknown kind is refused", raises(ValueError, lambda: hardware.screw("M3-0.5", 10, kind="wood")))
        ins, fi = hardware.insert("M3-0.5")
        ib = ins.bounding_box()
        check("an M3 heat-set insert: 4-6 mm across, valid, with a maker and a hole size", 4.0 <= fi["dims"]["outer_d"]["value"] <= 6.0 and ins.is_valid
              and fi["maker"] == "CNCKitchen", fi)
        check("its hole is the maker's 4.0 mm for the insert, not the thread's 2.5 mm tap drill", fi["hole_d"]["value"] == 4.0, fi["hole_d"])
        check("insert stands on z = 0, as tall as its stated length (5.7)", abs(ib.min.Z) < 0.01 and abs(ib.max.Z - fi["dims"]["length"]["value"]) < 0.05
              and fi["dims"]["length"]["value"] == 5.7, (ib.min.Z, ib.max.Z))
        check("the maker's product reference is carried for sourcing", "cnckitchen" in (fi["sold_as"] or "").lower(), fi["sold_as"])
        check("NEGATIVE: an unknown maker is refused", raises(ValueError, lambda: hardware.insert("M3-0.5", maker="nobody")))

        print("tipping and sliding: a 40 x 40 x 100 mm box of 200 g on a floor")
        box = bd.Pos(0, 0, 50) * bd.Box(40, 40, 100)
        # tips about its far edge when F x 80 mm = m g x 20 mm  ->  F = 0.2 x 9.81 x 20 / 80 = 0.4905 N (needs friction > 0.25)
        r = motion.stability({"box": (box, 200.0)}, [{"action": "push at 80 mm", "at": (-20, 0, 80), "direction": (1, 0, 0), "force_n": 0.2}], friction=0.5)
        w = r.get("worst") or {}
        check("pushed at 80 mm height it tips at 0.4905 N (within 3 %)", not r["problems"] and w.get("mode") == "tips" and abs(w["tips_at_n"] - 0.4905) < 0.015, r)
        check("ratio = limit / applied force", abs(w.get("ratio", 0) - w.get("tips_at_n", 0) / 0.2) < 0.01)
        # on a slippery floor (friction 0.1) it slides first, at 0.1 x 0.2 x 9.81 = 0.1962 N, when pushed low
        r = motion.stability({"box": (box, 200.0)}, [{"action": "push at 10 mm", "at": (-20, 0, 10), "direction": (1, 0, 0), "force_n": 0.1}], friction=0.1)
        w = r.get("worst") or {}
        check("on a slippery floor it slides at 0.1962 N (within 4 %)", w.get("mode") == "slides" and abs(w["tips_at_n"] - 0.1962) < 0.008, r)
        r = motion.stability({"box": (box, 200.0)}, [{"action": "press down", "at": (0, 0, 100), "direction": (0, 0, -1), "force_n": 1.0}])
        check("pressing straight down never tips it: reported as a lower bound", r["worst"]["mode"] == "holds" and r["worst"]["at_least"])
        check("inputs carry their tags (assumed until measured)", r["inputs"]["friction"]["tag"] == "assumed" and r["inputs"]["mass_g"] == {"value": 200.0, "tag": "assumed"})
        lean = bd.Pos(60, 0, 98) * bd.Box(120, 40, 4) + bd.Pos(2, 0, 48) * bd.Box(4, 40, 96)        # arm far past its 4 mm foot
        r = motion.stability({"L": (lean, 100.0)}, [{"action": "touch", "at": (0, 0, 50), "direction": (1, 0, 0), "force_n": 0.1}])
        check("NEGATIVE: a shape that falls over by itself is a problem, with no result", r["problems"] and "worst" not in r, r)
        motion.write_report(tmp / "st", r)
        ev = lambda c, folder: requirements.evaluate([{"id": "T", "text": "t", "check": c}], [folder])[0]  # noqa: E731
        check("NEGATIVE: the stability requirement is 'not evaluated' on that report", ev({"type": "stability_min_ratio", "min": 1.5}, tmp / "st")["status"] == "not evaluated")
        r = motion.stability({"box": (box, 200.0)}, [{"action": "push at 80 mm", "at": (-20, 0, 80), "direction": (1, 0, 0), "force_n": 0.2}], friction=0.5)
        motion.write_report(tmp / "st", r)
        check("ratio 2.45 passes a 1.5 requirement and fails a 3.0 one", ev({"type": "stability_min_ratio", "min": 1.5}, tmp / "st")["status"] == "pass"
              and ev({"type": "stability_min_ratio", "min": 3.0}, tmp / "st")["status"] == "fail")

        print("mechanism travel: a 10 mm cube sliding toward a wall 12 mm away")
        base = bd.Pos(10, 0, -7) * bd.Box(40, 20, 2) + bd.Pos(18.5, 0, 1) * bd.Box(3, 20, 18)     # plate + wall, wall face at x = 17
        cube = bd.Box(10, 10, 10)                                                                # its face at x = 5: gap 12
        base.label, cube.label = "base", "cube"
        slide = bd.LinearJoint("slide", base, axis=bd.Axis((0, 0, 0), (1, 0, 0)), linear_range=(0, 30))
        slide.connect_to(bd.RigidJoint("seat", cube, bd.Location((0, 0, 0))), position=0)
        asm = bd.Compound(label="slider", children=[base, cube])
        rows = motion.sweep(asm, "slide", [0, 4, 8, 12, 12.5, 16])
        check("no overlap up to 12 mm of travel", all(not r["overlaps"] for r in rows[:4]), rows)
        check("first collision at 12.5 mm, cube against base, 0.5 x 100 = 50 mm3", motion.first_collision(rows) == 12.5
              and rows[4]["overlaps"][0][:2] == ("base", "cube") and abs(rows[4]["overlaps"][0][2] - 50.0) < 0.5, rows[4])
        check("an allowed pair is ignored", motion.first_collision(motion.sweep(asm, "slide", [16], ignore=[("base", "cube")])) is None)
        check("NEGATIVE: a joint that does not exist is refused", raises(Exception, lambda: motion.sweep(asm, "nope", [1])))

        print("clearance and mass")
        a, b = bd.Box(10, 10, 10), bd.Pos(15, 0, 0) * bd.Box(10, 10, 10)
        check("two 10 mm cubes 15 mm apart: gap 5 mm", dfm.clearance(a, b)["gap_mm"] == 5.0)
        check("NEGATIVE: something that is not a shape raises", raises(b3d.GeometryCheckError, lambda: dfm.clearance(a, object())))
        m = dfm.mass({"a": (a, 1.27), "b": (b, 1.27)})                                       # 2 x 1 cm3 x 1.27 g/cm3, centred between
        check("mass 2.54 g, centre of mass at x = 7.5", abs(m["mass_g"] - 2.54) < 0.001 and abs(m["centre_mm"][0] - 7.5) < 0.001 and m["parts"]["a"] == 1.27, m)

        print("CNC and moulding checks")
        pocket = bd.Pos(0, 0, 5) * bd.Box(40, 30, 10) - bd.Pos(0, 0, 7) * bd.Box(20, 10, 6)   # sharp internal corners
        r = dfm.cnc({"pocket": pocket, "block": bd.Pos(0, 0, 5) * bd.Box(40, 30, 10)}, material="aluminum")
        check("a plain block passes the CNC check", r["parts"]["block"]["status"] == "pass", r["parts"]["block"])
        check("a pocket with sharp internal corners is flagged", r["parts"]["pocket"]["errors"] + r["parts"]["pocket"]["warnings"] >= 1, r["parts"]["pocket"]["summary"])
        r = dfm.molding({"brick": bd.Pos(0, 0, 10) * bd.Box(40, 30, 20)})
        check("a 20 mm thick brick is flagged for moulding (wall far too thick, no draft)", r["parts"]["brick"]["errors"] + r["parts"]["brick"]["warnings"] >= 1,
              r["parts"]["brick"]["summary"])
        check("NEGATIVE: a non-shape -> not evaluated", dfm.cnc({"x": object()})["parts"]["x"]["status"] == "not evaluated")

        print("KiCad: rule checks, board interface, export")
        ev = lambda c, folder: requirements.evaluate([{"id": "E", "text": "t", "check": c}], [folder])[0]  # noqa: E731
        check("NEGATIVE: no electronics report -> not evaluated", ev({"type": "electronics_ok"}, tmp)["status"] == "not evaluated")
        old = {k: os.environ.get(k) for k in ("MECHKIT_KICAD_CLI", "CAD_KICAD_CLI")}
        cli = electronics.find_kicad_cli()
        if cli is None:
            print("  (KiCad's kicad-cli not found: its checks are skipped)")
            r = electronics.check(board=tmp / "none.kicad_pcb")
            check("NEGATIVE: without KiCad the check is 'not evaluated'", r["status"] == "not evaluated" and r["drc"]["status"] == "not evaluated")
        else:
            for name, y in (("good", "10"), ("edge", "19.95")):                               # a track 0.05 mm from the board edge
                (tmp / name).mkdir()
                (tmp / name / ("%s.kicad_pcb" % name)).write_text(BOARD % {"y": y}, encoding="utf-8")
            good, edge = tmp / "good" / "good.kicad_pcb", tmp / "edge" / "edge.kicad_pcb"
            r = electronics.check(board=good)
            check("a board with one track in the middle passes DRC", r["drc"]["status"] == "pass" and r["drc"]["errors"] == 0, r["drc"]["summary"])
            electronics.write_report(tmp / "el", r)
            check("the electronics requirement passes on it", ev({"type": "electronics_ok"}, tmp / "el")["status"] == "pass")
            check("and fails a zero-warnings limit (dangling track)", ev({"type": "electronics_ok", "max_warnings": 0}, tmp / "el")["status"] == "fail")
            r = electronics.check(board=edge)
            check("NEGATIVE: a track on the board edge fails DRC (copper_edge_clearance)", r["drc"]["status"] == "fail"
                  and any(i["code"] == "copper_edge_clearance" for i in r["drc"]["issues"]), r["drc"]["summary"])
            electronics.write_report(tmp / "el", r)
            check("NEGATIVE: and the requirement fails", ev({"type": "electronics_ok"}, tmp / "el")["status"] == "fail")
            r = electronics.check(board=tmp / "missing.kicad_pcb")
            check("NEGATIVE: a missing board is 'not evaluated'", r["status"] == "not evaluated", r["drc"])
            face = electronics.board_interface(good)
            check("board interface: 30 x 20 x 1.6 mm, tagged stated", [face["dims"][k]["value"] for k in ("length_x", "width_y", "thickness")] == [30.0, 20.0, 1.6]
                  and all(v["tag"] == "stated" for v in face["dims"].values()), face["dims"])
            check("two 3.2 mm holes at (4, 4) and (26, 16)", sorted((h["x"], h["y"], h["diameter"]) for h in face["holes"]) == [(4.0, 4.0, 3.2), (26.0, 16.0, 3.2)], face["holes"])
            written = electronics.export(good, "step", tmp / "board_step")
            check("the board exports as STEP", written and written[0].suffix.lower() in (".step", ".stp") and written[0].stat().st_size > 1000, written)
            own = electronics._kicode_cli()
            check("the library was pointed at the KiCad chosen (its own nightly when the kicad extra is installed)",
                  os.environ.get("CAD_KICAD_CLI") == (None if cli == own else str(cli)), os.environ.get("CAD_KICAD_CLI"))
        for k, v in old.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v

        print("slicing: a 20 mm cube")
        proj = tmp / "proj"
        (proj / "exports" / "v1").mkdir(parents=True)
        bd.export_stl(bd.Pos(0, 0, 10) * bd.Box(20, 20, 20), str(proj / "exports" / "v1" / "cube.stl"))
        evp = lambda c: requirements.evaluate([{"id": "P", "text": "t", "check": c}], [proj / "exports" / "v1"])[0]  # noqa: E731
        check("_stl_size reads 20 x 20 x 20", slicer._stl_size(proj / "exports" / "v1" / "cube.stl") == [20.0, 20.0, 20.0])
        check("'1h 2m 3s' is 3723 s", slicer._seconds("1h 2m 3s") == 3723)
        r = slicer.estimates(proj, "v1", "Bambu Lab A1 0.4 nozzle", "0.20mm Standard @BBL A1", "Bambu PETG Basic @BBL A1", slicer=tmp / "no-such-slicer.exe")
        check("NEGATIVE: a slicer that is not there -> a problem, and print time 'not evaluated'", r["problems"] and evp({"type": "print_time_max_h", "max": 24})["status"] == "not evaluated", r["problems"])
        if slicer.find_slicer() is None:
            print("  (no slicer found: the real slice is skipped)")
        else:
            r = slicer.estimates(proj, "v1", "Bambu Lab A1 0.4 nozzle", "0.20mm Standard @BBL A1", "Bambu PETG Basic @BBL A1")
            f0 = (r["files"] or [{}])[0]
            # a solid PETG cube would weigh 8 cm3 x 1.27 = 10.2 g; with 2 walls and 15 % infill it must be well under that
            check("the cube slices: 2 to 8 g, 5 min to 2 h, 100 layers at 0.2 mm", not r["problems"] and 2.0 < f0.get("g", 0) < 8.0
                  and 300 < f0.get("seconds", 0) < 7200 and f0.get("layers") == 100, r)
            check("the report records the settings sliced with", f0.get("settings", {}).get("layer_height") == "0.2" and f0["settings"].get("filament_type") == "PETG", f0.get("settings"))
            check("requirements read it: under 24 h, under 100 g, fits a 256 mm bed", all(evp(c)["status"] == "pass" for c in (
                {"type": "print_time_max_h", "max": 24}, {"type": "filament_max_g", "max": 100}, {"type": "parts_fit_bed", "bed_mm": 256})))
            check("NEGATIVE: a 10 mm bed fails", evp({"type": "parts_fit_bed", "bed_mm": 10})["status"] == "fail")
            r = slicer.estimates(proj, "v1", "No Such Printer", "0.20mm Standard @BBL A1", "Bambu PETG Basic @BBL A1")
            check("NEGATIVE: an unknown printer preset -> a problem, not an estimate", r["problems"] and r["total_seconds"] == 0, r["problems"])

        print("isolation")
        check("cad_server is not imported", not any(m == "cad_server" or m.startswith("cad_server.") for m in sys.modules))
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    print("\n%d checks, %d failed" % (len(results), results.count(False)))
    sys.exit(1 if False in results else 0)


if __name__ == "__main__":
    main()
