"""Concept models for gate G1 (NOT print files): the screw-clamp saddle with the display pod in two positions.

    cd ../mechkit && uv run python "../Monitor weather display/parts/custom/concept.py"

Writes renders/concept_A_*.png and concept_B_*.png, plus work/concept_*.step.
Frame (mm): X along the monitor's bottom edge, +Y toward the user, +Z up. The monitor's front face is the plane
Y = 0 and its underside is Z = 0; the monitor body is at Y -23.4 .. 0, Z >= 0.

Every size here is a concept placeholder. Tags: monitor 23.4 thick and 24 chin = stated by the user; everything
about the display module, the C3 board, the inserts and the bolt heads = ASSUMED until measured.
"""

import sys
from pathlib import Path

PROJECT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT.parent / "mechkit"))

import build123d as bd  # noqa: E402

P = {
    "mon_thick": 23.4,      # stated
    "mon_chin": 24.0,       # stated: nothing on the front may go higher than this
    "tilt_deg": 10.0,       # assumed: "ever so slightly up"
    "wall": 3.0,
    "saddle_w": 40.0,       # along the monitor edge
    "lip_h": 12.0,          # front lip height (half the chin)
    "back_gap": 2.5,        # room behind the monitor for the clamp shoe
    "back_t": 6.0,          # back wall thickness (holds the brass insert)
    "back_h": 22.0,
    "bolt_z": 12.0,
    "pod_od": 47.0,         # ASSUMED from a typical 1.28 inch GC9A01 board (about 39 mm) + walls
    "pod_depth": 20.0,
    "window_d": 33.0,       # ASSUMED visible area of the display
    "pod_drop": 27.0,       # pod centre below the saddle's underside
}


def pod(p, y_face):
    """Hollow tilted pod whose front face centre sits at Y = y_face."""
    r, depth = p["pod_od"] / 2, p["pod_depth"]
    shell = bd.Cylinder(r, depth) - bd.Pos(0, 0, -p["wall"] / 2 - 0.01) * bd.Cylinder(r - p["wall"], depth - p["wall"]) - bd.Cylinder(p["window_d"] / 2, depth + 2)
    glass = bd.Pos(0, 0, depth / 2 - p["wall"] - 0.75) * bd.Cylinder(r - p["wall"] - 0.3, 1.5)
    place = bd.Pos(0, y_face - depth / 2, -p["wall"] - p["pod_drop"]) * bd.Rot(X=p["tilt_deg"] - 90)
    return place * shell, place * glass


def saddle(p):
    w, t = p["saddle_w"], p["wall"]
    y_back_in = -(p["mon_thick"] + p["back_gap"])
    plate = bd.Pos(0, (t + y_back_in - p["back_t"]) / 2, -t / 2) * bd.Box(w, t - (y_back_in - p["back_t"]), t)
    lip = bd.Pos(0, t / 2, p["lip_h"] / 2) * bd.Box(w, t, p["lip_h"])
    back = bd.Pos(0, y_back_in - p["back_t"] / 2, p["back_h"] / 2) * bd.Box(w, p["back_t"], p["back_h"])
    hole = bd.Pos(0, y_back_in - p["back_t"] / 2, p["bolt_z"]) * bd.Rot(X=90) * bd.Cylinder(2.0, p["back_t"] + 2)
    return plate + lip + (back - hole)


def clamp_hardware(p):
    y_back_in = -(p["mon_thick"] + p["back_gap"])
    shoe = bd.Pos(0, -p["mon_thick"] - 1.25, p["bolt_z"]) * bd.Rot(X=90) * bd.Cylinder(7.0, 2.5)
    bolt = bd.Pos(0, y_back_in - 2.0, p["bolt_z"]) * bd.Rot(X=90) * bd.Cylinder(1.5, 10.0)
    head = bd.Pos(0, y_back_in - p["back_t"] - 1.5, p["bolt_z"]) * bd.Rot(X=90) * bd.Cylinder(2.75, 3.0)
    return shoe + bolt + head


def neck(p, y_face):
    """Web joining the saddle's underside to the top of the pod."""
    t = p["wall"]
    y0, y1 = y_face - p["pod_depth"] + 2, y_face - 2
    return bd.Pos(0, (y0 + y1) / 2, -t - (p["pod_drop"] - p["pod_od"] / 2 + 4) / 2) * bd.Box(24, y1 - y0, p["pod_drop"] - p["pod_od"] / 2 + 4)


def concept(p, y_face):
    shell, glass = pod(p, y_face)
    printed = saddle(p) + neck(p, y_face) + shell
    return {"printed": printed, "glass": glass, "hardware": clamp_hardware(p),
            "monitor": bd.Pos(0, -p["mon_thick"] / 2, 45) * bd.Box(150, p["mon_thick"], 90),
            "picture": bd.Pos(0, 0.2, p["mon_chin"] + 33) * bd.Box(150, 0.4, 66)}


def render(parts, path, eye):
    import pyvista as pv

    pv.OFF_SCREEN = True
    tmp = PROJECT / "work"
    tmp.mkdir(exist_ok=True)
    plotter = pv.Plotter(off_screen=True, window_size=(1300, 900))
    style = {"monitor": ("#3a3d42", 1.0), "picture": ("#8fb8de", 1.0), "printed": ("#e8762c", 1.0), "glass": ("#101418", 1.0), "hardware": ("#c9a227", 1.0)}
    for name, solid in parts.items():
        stl = tmp / ("_%s.stl" % name)
        bd.export_stl(solid, str(stl), tolerance=0.05)
        plotter.add_mesh(pv.read(str(stl)), color=style[name][0], opacity=style[name][1], smooth_shading=True, split_sharp_edges=True)
        stl.unlink()
    plotter.set_background("white")
    plotter.camera_position = [eye, (0, -8, 5), (0, 0, 1)]
    plotter.camera.zoom(1.25)
    plotter.screenshot(str(path))
    plotter.close()


def main():
    (PROJECT / "renders").mkdir(exist_ok=True)
    (PROJECT / "work").mkdir(exist_ok=True)
    for label, y_face in (("A_inline", 3.0), ("B_forward", 14.0)):
        parts = concept(P, y_face)
        bd.export_step(parts["printed"], str(PROJECT / "work" / ("concept_%s.step" % label)))
        bb = parts["printed"].bounding_box()
        print("%s: printed volume %.0f mm3 (about %.0f g solid PETG), size %.0f x %.0f x %.0f mm, lowest point %.0f mm below the monitor, "
              "front-most point %.0f mm in front of the bezel" % (label, parts["printed"].volume, parts["printed"].volume * 1.27e-3,
                                                                  bb.size.X, bb.size.Y, bb.size.Z, -bb.min.Z, bb.max.Y))
        render(parts, PROJECT / "renders" / ("concept_%s_front.png" % label), (150, 260, 70))
        render(parts, PROJECT / "renders" / ("concept_%s_side.png" % label), (330, -12, 5))


if __name__ == "__main__":
    main()
