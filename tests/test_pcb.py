"""Board design flow: edit a board, check it, make the package a manufacturer takes, keep a copy a stable KiCad opens.

    uv run python tests/test_pcb.py

Needs the `kicad` extra (`uv sync --extra kicad`: kicode, a KiCad nightly). Without it the edit and package checks are
skipped with a line saying so, and the parts that must fail closed are still tested.
"""

import csv
import json
import shutil
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path

KIT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(KIT))

from mechkit import electronics  # noqa: E402

results = []


def check(name, cond, detail=""):
    results.append(bool(cond))
    print("  %-4s %s  %s" % ("ok" if cond else "FAIL", name, "" if cond else str(detail)[:400]))


def raises(exc, fn):
    try:
        fn()
    except exc:
        return True
    return False


# A 30 x 20 mm two-layer board: two M3 mounting holes, a two-pad part R1, one track. y = track position.
BOARD = '''(kicad_pcb (version 20221018) (generator pcbnew)
  (general (thickness 1.6))
  (paper "A4")
  (layers (0 "F.Cu" signal) (31 "B.Cu" signal) (36 "B.SilkS" user) (37 "F.SilkS" user) (38 "B.Mask" user) (39 "F.Mask" user) (44 "Edge.Cuts" user))
  (setup)
  (net 0 "") (net 1 "A") (net 2 "B")
  (footprint "MountingHole:MountingHole_3.2mm_M3" (layer "F.Cu") (at 4 4)
    (pad "" np_thru_hole circle (at 0 0) (size 3.2 3.2) (drill 3.2) (layers "*.Cu" "*.Mask")))
  (footprint "MountingHole:MountingHole_3.2mm_M3" (layer "F.Cu") (at 26 16)
    (pad "" np_thru_hole circle (at 0 0) (size 3.2 3.2) (drill 3.2) (layers "*.Cu" "*.Mask")))
  (footprint "Resistor_SMD:R_0805_2012Metric" (layer "F.Cu") (at 15 6)
    (fp_text reference "R1" (at 0 -1.6) (layer "F.SilkS") (effects (font (size 1 1) (thickness 0.15))))
    (fp_text value "10k" (at 0 1.6) (layer "F.Fab") (effects (font (size 1 1) (thickness 0.15))))
    (pad "1" smd roundrect (at -0.95 0) (size 1 1.4) (layers "F.Cu" "F.Paste" "F.Mask") (roundrect_rratio 0.25) (net 1 "A"))
    (pad "2" smd roundrect (at 0.95 0) (size 1 1.4) (layers "F.Cu" "F.Paste" "F.Mask") (roundrect_rratio 0.25) (net 2 "B")))
  (gr_rect (start 0 0) (end 30 20) (stroke (width 0.1) (type default)) (fill none) (layer "Edge.Cuts"))
  (segment (start 8 %(y)s) (end 14.05 %(y)s) (width 0.25) (layer "F.Cu") (net 1))
)
'''


def main():
    tmp = Path(tempfile.mkdtemp(prefix="mechkit_pcb_"))
    try:
        print("placement file for JLCPCB (columns renamed, values untouched)")
        pos = tmp / "x-pos.csv"
        pos.write_text("Ref,Val,Package,PosX,PosY,Rot,Side\nR1,10k,R_0805,15.0000,-6.0000,90.0000,top\nC2,1u,C_0603,3.5,-9,0,bottom\n", encoding="utf-8")
        n = electronics.jlc_placement(pos, tmp / "cpl.csv")
        rows = list(csv.DictReader(open(tmp / "cpl.csv", newline="", encoding="utf-8")))
        check("two parts, JLCPCB's column names", n == 2 and list(rows[0]) == ["Designator", "Val", "Package", "Mid X", "Mid Y", "Rotation", "Layer"])
        check("R1 at (15, -6) rotated 90 on Top; C2 on Bottom", (rows[0]["Designator"], rows[0]["Mid X"], rows[0]["Mid Y"], rows[0]["Rotation"], rows[0]["Layer"])
              == ("R1", "15.0000", "-6.0000", "90.0000", "Top") and rows[1]["Layer"] == "Bottom", rows)
        (tmp / "bad.csv").write_text("a,b\n1,2\n", encoding="utf-8")
        check("NEGATIVE: a file that is not KiCad's placement file is refused", raises(ValueError, lambda: electronics.jlc_placement(tmp / "bad.csv", tmp / "o.csv")))
        check("NEGATIVE: a package folder without a manifest is not current", electronics.package_is_current(tmp, pos)[0] is False)

        if electronics.find_kicad_cli() is None:
            print("  (no kicad-cli at all: everything below is skipped)")
        else:
            for name, y in (("good", "6"), ("edge", "19.95")):
                (tmp / name).mkdir()
                (tmp / name / "demo.kicad_pcb").write_text(BOARD % {"y": y}, encoding="utf-8")
            good, edge = tmp / "good" / "demo.kicad_pcb", tmp / "edge" / "demo.kicad_pcb"

            print("the gate: rule-check errors block fabrication files")
            check("NEGATIVE: a board with a DRC error is refused, nothing written", raises(PermissionError, lambda: electronics.fab_package(edge, tmp / "fab_edge"))
                  and not (tmp / "fab_edge").exists())
            check("NEGATIVE: a one-word go-ahead is not accepted", raises(PermissionError, lambda: electronics.fab_package(edge, tmp / "fab_edge", go_ahead="ok")))
            check("NEGATIVE: a missing board is refused (check not evaluated)", raises(PermissionError, lambda: electronics.fab_package(tmp / "none.kicad_pcb", tmp / "fab_none")))
            m = electronics.fab_package(edge, tmp / "fab_edge", go_ahead="user, 2026-11-25: prototype, go ahead anyway")
            check("with the person's go-ahead it is written, and the manifest records their words and the error",
                  m["go_ahead"].startswith("user, 2026-11-25") and m["blocked_by"] == ["drc"] and m["checks"]["drc"]["status"] == "fail"
                  and any(i["code"] == "copper_edge_clearance" for i in m["checks"]["drc"]["issues"]), m["checks"])

            print("the command line keeps the same gate")
            def cli(*a):
                r = subprocess.run([sys.executable, "-m", "mechkit", "pcb"] + [str(x) for x in a], capture_output=True, text=True, cwd=str(KIT))
                return r.returncode, r.stdout + r.stderr
            code, text = cli("check", edge)
            check("pcb check exits 1 on a DRC error and names it", code == 1 and "copper_edge_clearance" in text, (code, text[-300:]))
            check("pcb check exits 0 on the clean board", cli("check", good)[0] == 0)
            check("NEGATIVE: pcb check exits 2 when the board is missing", cli("check", tmp / "none.kicad_pcb")[0] == 2)
            code, text = cli("fab", edge, "--out", tmp / "fab_cli")
            check("NEGATIVE: pcb fab refuses the board with the error and writes nothing", code != 0 and "NOT WRITTEN" in text and not (tmp / "fab_cli").exists(), (code, text[-300:]))
            code, text = cli("interface", good)
            check("pcb interface prints the 30 x 20 x 1.6 mm board as JSON", code == 0 and json.loads(text)["dims"]["length_x"]["value"] == 30.0, text[-200:])

            print("the package from a clean board")
            m = electronics.fab_package(good, tmp / "fab")
            out = tmp / "fab"
            names = [f["path"] for f in m["files"]]
            check("clean board: no go-ahead recorded, DRC pass", m["go_ahead"] is None and m["blocked_by"] == [] and m["checks"]["drc"]["status"] == "pass", m["checks"])
            check("gerbers for both copper layers, both masks, the outline; and a drill file",
                  all(any(k in n for n in names) for k in ("F_Cu", "B_Cu", "F_Mask", "B_Mask", "Edge_Cuts")) and any(n.startswith("drill/") for n in names), names)
            with zipfile.ZipFile(out / "demo-gerbers.zip") as z:
                zipped = z.namelist()
            check("the zip holds exactly the gerber and drill files", sorted(zipped) == sorted(Path(n).name for n in names if n.startswith(("gerbers/", "drill/"))), zipped)
            drl = next(out.glob("drill/*.drl")).read_text(encoding="utf-8", errors="replace")
            check("the drill file has the two 3.2 mm holes", "3.2" in drl and drl.count("X") >= 2, drl[:300])
            cpl = list(csv.DictReader(open(out / "assembly" / "demo-cpl-jlcpcb.csv", newline="", encoding="utf-8")))
            r1 = [r for r in cpl if r["Designator"] == "R1"]
            check("placement: R1 at x = 15, y = -6 (KiCad's y negated), Top", r1 and abs(float(r1[0]["Mid X"]) - 15) < 1e-6 and abs(float(r1[0]["Mid Y"]) + 6) < 1e-6
                  and r1[0]["Layer"] == "Top", cpl)
            check("the manifest names the board by sha256 and every file by sha256", m["board"]["sha256"] == electronics._sha256(good)
                  and all(len(f["sha256"]) == 64 for f in m["files"]) and "no schematic beside the board: no BOM" in m["notes"], m["notes"])
            check("the package is current", electronics.package_is_current(out, good) == (True, ""))
            g = out / "gerbers" / "demo-F_Cu.gbr"
            g.write_bytes(g.read_bytes() + b"\n")
            check("NEGATIVE: a gerber changed by hand makes it not current", electronics.package_is_current(out, good)[0] is False)
            electronics.fab_package(good, out)
            check("making it again replaces the folder whole (no staging left behind)", electronics.package_is_current(out, good)[0]
                  and not (tmp / "fab.staging").exists() and not (tmp / "fab.old").exists())

            if not electronics.have_editor():
                print("  (kicad extra not installed: edits, routing and the stable copy are skipped)")
                check("NEGATIVE: an edit without the extra says how to get it", raises(RuntimeError, lambda: electronics.edit_board(good).__enter__()))
            else:
                print("editing the board (KiCad nightly through its API)")
                from kicode.util.units import from_mm
                with electronics.edit_board(good) as b:
                    tracks = b.get_tracks()
                    for t in tracks:
                        t.width = from_mm(0.5)
                    b.update_items(tracks)
                import cad.kicad_pcb as kp
                check("the track is 0.5 mm wide in the saved file", [t.width for t in kp.read(good).tracks] == [0.5], [t.width for t in kp.read(good).tracks])
                check("NEGATIVE: the package made before the edit is no longer current", electronics.package_is_current(out, good)[0] is False)
                before = good.read_bytes()

                def failing():
                    with electronics.edit_board(good) as b:
                        tracks = b.get_tracks()
                        tracks[0].width = from_mm(2.0)
                        b.update_items(tracks)
                        raise ValueError("stop")
                check("NEGATIVE: a block that raises saves nothing", raises(ValueError, failing) and good.read_bytes() == before)
                copy = good.parent / "kicad-10.0" / "demo.kicad_pcb"
                check("a stable-format copy was refreshed beside it, marked read-only", copy.is_file() and (copy.parent / "READ-ONLY-COPY.txt").is_file())
                stable = electronics.find_stable_kicad_cli()
                if stable and "10.99" not in (electronics.kicad_version(stable) or ""):
                    a = subprocess.run([str(stable), "pcb", "drc", "-o", str(tmp / "a.rpt"), str(good)], capture_output=True, text=True)
                    c = subprocess.run([str(stable), "pcb", "drc", "-o", str(tmp / "c.rpt"), str(copy)], capture_output=True, text=True)
                    check("the installed stable KiCad refuses the nightly file and opens the copy", a.returncode != 0 and (tmp / "c.rpt").is_file(),
                          (a.returncode, c.returncode, (c.stdout + c.stderr)[-200:]))
                else:
                    print("  (no stable KiCad installed: opening the copy in it is not checked)")
                r = electronics.check(board=good)
                check("the edited board still passes DRC", r["drc"]["status"] == "pass", r["drc"]["summary"])
                pic = electronics.render(good, tmp / "board.png")
                check("KiCad renders a picture of it", pic.is_file() and pic.read_bytes()[:4] == b"\x89PNG" and pic.stat().st_size > 5000)
                with electronics.edit_board(tmp / "new" / "fresh.kicad_pcb", stable=None) as b:
                    pass
                check("a board that is not there yet is made, with its project", (tmp / "new" / "fresh.kicad_pcb").is_file() and (tmp / "new" / "fresh.kicad_pro").is_file())
                check("NEGATIVE: an empty new board has no outline: its package is blocked", raises(PermissionError, lambda: electronics.fab_package(tmp / "new" / "fresh.kicad_pcb", tmp / "fab_new")))
        check("cad_server is not imported", not any(m == "cad_server" or m.startswith("cad_server.") for m in sys.modules))
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    print("\n%d checks, %d failed" % (len(results), results.count(False)))
    sys.exit(1 if False in results else 0)


if __name__ == "__main__":
    main()
