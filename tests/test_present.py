"""Presentation layer, offline part: manifest, label layout, picture sheets, and the checks around the Fusion sender.

    uv run python tests/test_present.py

Fusion is not needed (the scripts sent to Fusion are only syntax-checked here; tests/live_present.py runs them).
"""

import ast
import copy
import json
import shutil
import sys
import tempfile
from pathlib import Path

KIT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(KIT))
import build123d as bd  # noqa: E402

from mechkit.present import fusion, layout, manifest, sheet  # noqa: E402

def _example():
    """The worked example: your own working copy beside the kit if there is one, else the copy in examples/."""
    for p in (KIT.parent / "Monitor weather display", KIT / "examples" / "monitor-weather-display"):
        if (p / "exports").is_dir():
            return p
    return KIT / "examples" / "monitor-weather-display"


MWD = _example()
results = []


def check(name, cond, detail=""):
    results.append(bool(cond))
    print("  %-4s %s  %s" % ("ok" if cond else "FAIL", name, detail))


def raises(fn, text):
    try:
        fn()
    except ValueError as e:
        return text in str(e)
    return False


def sample_items():
    plate = bd.Box(40, 30, 4)
    lid = bd.Pos(0, 0, 4) * bd.Box(40, 30, 2)
    screws = [bd.Pos(x, 0, 3) * bd.Cylinder(1.5, 8) for x in (-12, 12)]
    table = bd.Pos(0, 0, -7) * bd.Box(120, 90, 10)
    return [manifest.item("Plate", plate, 1, "printed", "The base plate.", "#2b2d31", material="PETG", part_number="T-1"),
            manifest.item("Lid", lid, 2, "printed", "The lid.", "#c8ccd2", material="PETG", explode=(0, 0, 20)),
            manifest.item("Screw_A", screws[0], 3, "hardware", "M3 screw.", "#9aa0a8", part="Screw M3", explode=(0, 0, 45)),
            manifest.item("Screw_B", screws[1], 3, "hardware", "M3 screw.", "#9aa0a8", part="Screw M3", explode=(0, 0, 45)),
            manifest.item("Table", table, 0, "reference", "The desk.", "#3a3d42", opacity=0.3)]


def main():
    tmp = Path(tempfile.mkdtemp(prefix="mk_present_"))
    try:
        print("manifest")
        items = sample_items()
        views = [manifest.view("Front", (120, 200, 60), (0, 0, 0)), manifest.view("Exploded", (160, 160, 110), (0, 0, 20), group="exploded")]
        path = manifest.write(tmp, "v1", "Sample", items, views)
        data = manifest.load(path)
        check("one STEP file per item", all((path.parent / e["step"]).is_file() for e in data["parts"]) and len(data["parts"]) == 5)
        check("volumes recorded", abs(data["parts"][0]["volume_mm3"] - 4800.0) < 0.01, "%.2f" % data["parts"][0]["volume_mm3"])
        rows = data["table"]
        check("table: one row per label, reference left out", [r["label"] for r in rows] == [1, 2, 3])
        check("table: same part counted together", rows[2]["qty"] == 2 and rows[2]["part"] == "Screw M3")
        check("document and cloud folder named after the project", data["document"] == "Sample_Presentation" and data["cloud_folder"] == "Admin Project/Sample")
        off = data["exploded_offset"]
        ax = [i for i in range(3) if off[i]][0]
        check("exploded group stands clear of the assembled one", data["exploded_bbox"][0][ax] + off[ax] >= data["assembled_bbox"][1][ax] + 59.9,
              "offset %s" % off)
        side = manifest.load(manifest.write(tmp / "side", "v1", "Sample", items, [manifest.view("Exploded", (300, 20, 60), (0, 0, 20), group="exploded")]))
        check("the offset avoids the direction the views look along", side["exploded_offset"][0] == 0 and side["exploded_offset"][1] > 0,
              str(side["exploded_offset"]))
        check("no overlaps after the explode moves", manifest.exploded_overlaps(items) == [])
        clash = copy.copy(items[1])
        clash["explode"] = [0.0, 0.0, -2.0]                                  # 1 mm down into the plate
        check("an explode move into another part is reported", len(manifest.exploded_overlaps([items[0], clash])) == 1)
        bad = [dict(i) for i in items]
        bad[3]["part"] = "Other screw"
        check("one label for two different parts is refused", raises(lambda: manifest.write(tmp / "b1", "v1", "S", bad, views), "label 3"))
        bad = [dict(i) for i in items]
        bad[1]["label"] = 5
        check("gaps in the label numbers are refused", raises(lambda: manifest.write(tmp / "b2", "v1", "S", bad, views), "without gaps"))
        bad = [dict(i) for i in items]
        bad[0]["description"] = " "
        check("a part without a description is refused", raises(lambda: manifest.write(tmp / "b3", "v1", "S", bad, views), "description"))
        bad = [dict(i) for i in items]
        bad[4]["explode"] = [0.0, 0.0, 5.0]
        check("a reference item may not be exploded", raises(lambda: manifest.write(tmp / "b4", "v1", "S", bad, views), "reference"))
        check("find() returns the newest manifest", manifest.find(tmp) == path)
        check("a manifest without steps is fine", data["steps"] == [])
        good = [manifest.step("Base", "Put the plate down.", ["Plate"]), manifest.step("Close", "Lid on, two screws.", ["Lid", "Screw_A", "Screw_B"])]
        with_steps = manifest.load(manifest.write(tmp / "s1", "v1", "S", items, views, steps=good))
        check("steps are stored in order", [s["title"] for s in with_steps["steps"]] == ["Base", "Close"])
        check("an item left out of the steps is refused", raises(lambda: manifest.write(tmp / "s2", "v1", "S", items, views, steps=good[:1]), "not added in any step"))
        twice = good + [manifest.step("Again", "x", ["Lid"])]
        check("an item in two steps is refused", raises(lambda: manifest.write(tmp / "s3", "v1", "S", items, views, steps=twice), "more than one step"))
        ref = [good[0], manifest.step("Close", "x", ["Lid", "Screw_A", "Screw_B", "Table"])]
        check("a reference item in a step is refused", raises(lambda: manifest.write(tmp / "s4", "v1", "S", items, views, steps=ref), "reference item"))
        aimed = [good[0], manifest.step("Close", "x", ["Lid", "Screw_A", "Screw_B"], view=((100, -200, 80), (0, 0, 0)), pull={"Lid": (0, 0, 15)})]
        am = manifest.load(manifest.write(tmp / "s6", "v1", "S", items, views, steps=aimed,
                                          guide=manifest.guide(tools=[("Hex key 2.5 mm", "M3")], wiring={"from": "A", "to": "B", "wires": [{"from": "1", "to": "x"}]},
                                                               commissioning=[{"title": "Test", "checks": ["it works"]}])))
        check("a step keeps its view and pull", am["steps"][1]["view"]["up"] == [0.0, 0.0, 1.0] and am["steps"][1]["pull"] == {"Lid": [0.0, 0.0, 15.0]}
              and am["steps"][0]["view"] is None)
        check("the guide's sections are stored", am["guide"]["tools"][0] == {"name": "Hex key 2.5 mm", "note": "M3"}
              and am["guide"]["wiring"]["wires"][0]["signal"] == "" and am["guide"]["commissioning"][0]["checks"] == ["it works"] and am["guide"]["printing"] is None)
        check("a manifest without a guide stores none", with_steps["guide"] is None)
        badpull = [good[0], manifest.step("Close", "x", ["Lid", "Screw_A", "Screw_B"], pull={"Nope": (0, 0, 1)})]
        check("a pull naming an unknown item is refused", raises(lambda: manifest.write(tmp / "s7", "v1", "S", items, views, steps=badpull), "pulls 'Nope'"))
        ghost = [good[0], manifest.step("Close", "x", ["Lid", "Screw_A", "Screw_B", "Nope"])]
        check("a step naming an unknown item is refused", raises(lambda: manifest.write(tmp / "s5", "v1", "S", items, views, steps=ghost), "not an item"))

        print("label layout")
        pts = [(i * 10.0, i * 2.0) for i in range(8)] + [(40.0, 8.5), (40.5, 8.0)]
        spots = layout.place_balloons(pts, 5.0, 30.0)
        gaps = [((spots[i][0] - spots[j][0]) ** 2 + (spots[i][1] - spots[j][1]) ** 2) ** 0.5 for i in range(len(spots)) for j in range(i + 1, len(spots))]
        check("balloons do not touch each other", min(gaps) >= 10.0, "closest %.1f" % min(gaps))
        r, u, t = layout.camera_basis((0, -100, 0), (0, 0, 0), (0, 0, 1))
        check("camera basis", [round(c, 6) for c in r] == [1, 0, 0] and [round(c, 6) for c in u] == [0, 0, 1] and [round(c, 6) for c in t] == [0, -1, 0],
              "right %s up %s" % (r, u))
        L = fusion.label_layout(data)
        check("one balloon per counted item", sorted(b["label"] for b in L["balloons"]) == [1, 2, 3, 3])
        toward = layout.camera_basis(views[1]["eye"], views[1]["target"], views[1]["up"])[2]
        front = max(sum(c[i] * toward[i] for i in range(3)) for c in
                    [[data["exploded_bbox"][a][0], data["exploded_bbox"][b][1], data["exploded_bbox"][c][2]] for a in (0, 1) for b in (0, 1) for c in (0, 1)])
        check("label sheet is in front of every part", sum(L["origin"][i] * toward[i] for i in range(3)) > front)
        d2 = copy.deepcopy(data)
        fusion.view_extents(d2)
        check("every view gets a picture width and a middle to aim at", all(v["extent"] > 100 and len(v["centre"]) == 3 for v in d2["views"]),
              str([v["extent"] for v in d2["views"]]))

        print("sheets")
        files = sheet.make(data, tmp / "sheets")
        pngs = [f for f in files if f.suffix == ".png"]
        check("one picture per view + the parts table", len(pngs) == 2 and (tmp / "sheets" / "parts_table.md").is_file())
        check("pictures are not empty", all(f.stat().st_size > 20000 for f in pngs), str([f.stat().st_size for f in pngs]))
        from PIL import Image
        sizes = [Image.open(f).size for f in pngs]
        check("the exploded sheet carries the table beside the picture", sizes[0] == (sheet.W3D, sheet.H) and sizes[1] == (sheet.W3D + sheet.WTAB, sheet.H), str(sizes))
        check("table text lists the quantities", "| 3 | Screw M3 | 2 |" in sheet.table_markdown(data))

        print("Fusion sender (no Fusion: scripts and checks only)")
        payload = dict(d2, labels=L)
        for name in ("PREPARE", "IMPORT", "EXPLODE", "VIEWS", "SAVE", "VERIFY"):
            code = getattr(fusion, name).replace("__DATA__", repr(json.dumps(payload)))
            try:
                ast.parse(code)
                ok = True
            except SyntaxError as e:
                ok = False
                print("     ", e)
            check("script %s parses" % name, ok)
        made = [{"key": e["key"], "bodies": 1, "volume_mm3": e["volume_mm3"], "moved_mm": 0.0, "nested": 0} for e in data["parts"]]
        comp = {e["key"]: {"name": e["name"], "description": e["description"], "part_number": e["part_number"], "volume_mm3": e["volume_mm3"], "solid": True}
                for e in data["parts"]}
        by = {e["key"]: e for e in data["parts"]}
        seen = {"direct": True, "views": ["Front", "Exploded"], "up": "z",
                "groups": {"Assembled": {k: dict(v, box=fusion.expected_box(by[k], "z", data["exploded_offset"], False)) for k, v in comp.items()},
                           "Exploded": {k: dict(v, box=fusion.expected_box(by[k], "z", data["exploded_offset"], True)) for k, v in comp.items() if k != "Table"}}}
        check("a faithful read-back passes", fusion.check(data, made, seen) == [], str(fusion.check(data, made, seen)))
        wrong = copy.deepcopy(made)
        wrong[0]["volume_mm3"] *= 1000                                      # what a unit mix-up would look like
        check("a wrong volume is caught", any("volume" in p for p in fusion.check(data, wrong, seen)))
        seen2 = copy.deepcopy(seen)
        del seen2["groups"]["Exploded"]["Lid"]
        seen2["views"] = ["Front"]
        probs = fusion.check(data, made, seen2)
        check("a missing exploded part and a missing view are caught", any("Exploded group" in p for p in probs) and any("named views" in p for p in probs))
        seen3 = copy.deepcopy(seen)
        seen3["groups"]["Exploded"]["Lid"]["box"] = seen["groups"]["Assembled"]["Lid"]["box"]      # a copy that was never moved apart
        check("an exploded part left in its assembled place is caught", any("Lid in the Exploded group" in p for p in fusion.check(data, made, seen3)))
        check("kit front (+Y) faces Fusion's front view in both document frames",
              fusion.to_fusion((0, 1, 0), "z") == (0, -1, 0) and fusion.to_fusion((0, 1, 0), "y") == (0, 0, 1) and fusion.to_fusion((0, 0, 1), "y") == (0, 1, 0))
        cfg = Path.home() / ".fusion-mcp" / "config.json"
        if cfg.is_file():
            scope = json.loads(cfg.read_text(encoding="utf-8")).get("scope", {})
            if scope.get("enabled"):
                check("scope guard: a folder outside the list is refused", not fusion.scope_allows("Admin Project/__not_a_real_folder__")[0])
                check("scope guard: a listed folder's sub-folder is allowed", fusion.scope_allows(scope["folders"][0] + "/Purchased")[0])

        if (MWD / "exports").is_dir():
            print("monitor weather display")
            m = manifest.load(manifest.find(MWD))
            log = json.loads((MWD / "logs" / ("build_%s.json" % m["version"])).read_text(encoding="utf-8"))
            vol = {e["key"]: e["volume_mm3"] for e in m["parts"]}
            same = all(abs(vol[k] - v["volume_mm3"]) < 0.1 for k, v in log["parts"].items())
            check("printed parts in the manifest are the printed parts of the build", same and not log["problems"])
            qty = {r["part"]: r["qty"] for r in m["table"]}
            check("parts table: 13 rows, 3 M3 bolts, 3 M3 inserts, 1 display",
                  len(m["table"]) == 13 and qty["Bolt M3 x 10, socket head"] == 3 and qty["Heat-set insert M3"] == 3 and qty["Round display GC9A01 1.28 in"] == 1, str(len(m["table"])))
            check("every item is one solid", all(e["bodies"] == 1 for e in m["parts"]), str({e["key"]: e["bodies"] for e in m["parts"] if e["bodies"] != 1}))
            check("7 printed parts", sum(1 for r in m["table"] if r["kind"] == "printed") == 7)
            check("7 assembly steps covering all 18 parts", len(m["steps"]) == 7 and sum(len(s["add"]) for s in m["steps"]) == 18)
            check("every step says where its picture is taken from and what is pulled out", all(s["view"] and s["pull"] for s in m["steps"]))
            pm = json.loads((MWD / "pinmap.json").read_text(encoding="utf-8"))
            wires = {(w["from"], w["to"]) for w in m["guide"]["wiring"]["wires"]}
            check("the wiring page is the pin map: 7 wires, every GPIO as written there",
                  len(wires) == 7 and all(("GPIO%d" % x["gpio"], x["connects_to"].replace("display pad ", "")) in wires for x in pm["pins"])
                  and ("3V3", "VCC") in wires and ("GND", "GND") in wires, str(sorted(wires)))
            check("the guide lists tools, consumables, print settings and commissioning",
                  len(m["guide"]["tools"]) >= 5 and len(m["guide"]["consumables"]) >= 2 and len(m["guide"]["printing"]["parts"]) == 7
                  and [c["title"] for c in m["guide"]["commissioning"]] == ["Load the firmware", "First start", "Functional test", "Final inspection"])
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    print("\n%d checks, %d failed" % (len(results), results.count(False)))
    sys.exit(1 if False in results else 0)


if __name__ == "__main__":
    main()
