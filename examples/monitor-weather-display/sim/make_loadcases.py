"""Write sim/loadcases.json from the current design parameters (run after any change to parts/custom/build.py).

    cd ../mechkit && uv run python "../Monitor weather display/sim/make_loadcases.py"
    then:          uv run python -m mechkit sim "../Monitor weather display"
"""
import json
import math
import sys
from pathlib import Path

PROJECT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT / "parts" / "custom"))
import build as B  # noqa: E402

p = B.P
t = math.radians(p["tilt_deg"])
n = [0.0, round(math.cos(t), 6), round(math.sin(t), 6)]
zmid = p["pod_depth"] + p["cover_t"] + p["hanger_t"] / 2
hy, hz = B.yz(p, p["bolt_v"], zmid)
y_in = -(p["mon_thick"] + p["back_gap"])
lip_face = {"type": "plane", "normal": [0, 1, 0], "offset": 0.0, "box": [[-30, -0.1, 0.0], [30, 0.1, p["lip_h"] + 0.1]]}
under_monitor = {"type": "plane", "normal": [0, 0, 1], "offset": 0.0, "box": [[-30, -p["mon_thick"], -0.1], [30, 0.0, 0.1]]}
insert = {"type": "cylinder", "point": [p["bolt_x_clamp"], y_in - p["back_t"] / 2, p["bolt_z"]], "axis": [0, 1, 0], "d": p["m4_insert_hole_d"],
          "span": [0.0, p["back_t"] / 2]}      # the insert pocket on the inner half of the wall: where the screw's reaction goes
holes = [{"type": "cylinder", "point": [sx * p["bolt_x"], round(hy, 4), round(hz, 4)], "axis": n, "d": p["m3_clear"]} for sx in (-1, 1)]
data = {
    "about": "Clamp load cases (mm, N), written by sim/make_loadcases.py from the design parameters. World frame: X along the monitor edge, +Y toward the user, +Z up.",
    "parts": [{
        "name": "Clamp", "step": "exports/%s/Clamp_as_assembled.step" % B.VERSION, "mesh_sizes": [2.5, 1.6], "material": "petg_printed_assumed", "layers": "in_plane",
        "notes": "printed on its side, so the layers run along the U profile",
        "cases": [
            {"name": "clamp force", "about": "the bolt pressing the monitor with 30 N: the back wall is pushed backward by the same force; the front lip bears on the bezel",
             "min_safety_factor": 3.0, "max_deflection_mm": 1.0, "fix": [lip_face], "loads": [{"force": [0, -30.0, 0], "on": insert}]},
            {"name": "cable tug", "about": "the pod's weight plus a 5 N pull on the unit, carried by the two pod bolts",
             "min_safety_factor": 3.0, "max_deflection_mm": 0.5, "fix": [under_monitor, lip_face],
             "loads": [{"force": [0, 0, -3.0], "on": holes[0]}, {"force": [0, 0, -3.0], "on": holes[1]}]}]}]}
out = PROJECT / "sim" / "loadcases.json"
out.write_text(json.dumps(data, indent=1), encoding="utf-8", newline="\n")
print("written", out, "for", B.VERSION)
