"""Calibrate the printed-material card against real test bars (turns "assumed" into "calibrated").

    python -m mechkit.calibration make <folder>          write the 3 test-bar STLs + instructions
    python -m mechkit.calibration fit --flat 200:4.6 --edge 1000:3.9 --upright 200:5.0 [--upright-break-g 900] [--flat-break-g 2500]
                                      (each bar as  grams:sag_mm)

The bars are 120 x 10 x 4 mm. Printed three ways they load the plastic differently:
    bar_flat      lying flat (4 mm tall): bends across the 4 mm, layers run along the bar
    bar_on_edge   on its 4 mm edge (10 mm tall): bends across the 10 mm, layers run along the bar
    bar_upright   standing (120 mm tall, with a foot): layers are stacked ALONG the bar, so bending pulls them apart
Test: clamp 20 mm of the bar to a table edge (a book and a clamp), hang a known weight 90 mm out from the table edge,
and measure how far the weight point drops (ruler or calipers against the table edge; a phone photo works).
Stiffness comes from the sag:  E = F L^3 / (3 I sag).  Strength across layers comes from the weight at which the
upright bar snaps:  stress = 6 F L / (b h^2).
"""

import json
import sys
from pathlib import Path

L_BAR, B_BAR, H_BAR = 120.0, 10.0, 4.0
CLAMP, ARM = 20.0, 90.0                 # mm held on the table; mm from the table edge to the weight
G = 9.81


def modulus_from_sag(weight_g, sag_mm, bend_height, bend_width, arm=ARM):
    """Young's modulus (MPa) from a cantilever test: weight in grams hung `arm` mm out, sag in mm."""
    force = weight_g / 1000.0 * G
    inertia = bend_width * bend_height ** 3 / 12.0
    return force * arm ** 3 / (3.0 * inertia * sag_mm)


def break_stress(weight_g, bend_height, bend_width, arm=ARM):
    """Bending stress (MPa) at the clamp when the bar broke under `weight_g` grams hung `arm` mm out."""
    return 6.0 * (weight_g / 1000.0 * G) * arm / (bend_width * bend_height ** 2)


def fit(flat=None, edge=None, upright=None, upright_break_g=None, flat_break_g=None):
    """Material values from the measurements that were made. flat / edge / upright = (weight in grams, sag in mm)."""
    out = {"bars": {}}
    if flat:
        out["bars"]["flat"] = {"weight_g": flat[0], "sag_mm": flat[1], "e_mpa": round(modulus_from_sag(flat[0], flat[1], H_BAR, B_BAR), 0)}
    if edge:
        out["bars"]["on_edge"] = {"weight_g": edge[0], "sag_mm": edge[1], "e_mpa": round(modulus_from_sag(edge[0], edge[1], B_BAR, H_BAR), 0)}
    if upright:
        out["bars"]["upright"] = {"weight_g": upright[0], "sag_mm": upright[1], "e_mpa": round(modulus_from_sag(upright[0], upright[1], H_BAR, B_BAR), 0)}
    along = [b["e_mpa"] for k, b in out["bars"].items() if k in ("flat", "on_edge")]
    if along:
        out["e_mpa"] = round(min(along), 0)                      # the lower of the two is used (safe side)
    if upright_break_g:
        out["strength_across_layers_mpa"] = round(break_stress(upright_break_g, H_BAR, B_BAR), 1)
    if flat_break_g:
        out["strength_mpa"] = round(break_stress(flat_break_g, H_BAR, B_BAR), 1)
    if "strength_mpa" in out and "strength_across_layers_mpa" in out:
        out["across_layers_factor"] = round(out["strength_across_layers_mpa"] / out["strength_mpa"], 2)
    return out


def _box_stl(path, lx, ly, lz):
    """Write a block as a binary STL (12 triangles), sitting on z = 0."""
    import struct
    v = [(x, y, z) for x in (0.0, lx) for y in (0.0, ly) for z in (0.0, lz)]
    quads = [(0, 2, 3, 1), (4, 5, 7, 6), (0, 1, 5, 4), (2, 6, 7, 3), (0, 4, 6, 2), (1, 3, 7, 5)]
    tris = [(q[0], q[1], q[2]) for q in quads] + [(q[0], q[2], q[3]) for q in quads]
    with Path(path).open("wb") as f:
        f.write(b"mechkit calibration bar".ljust(80, b" "))
        f.write(struct.pack("<I", len(tris)))
        for a, b, c in tris:
            pa, pb, pc = v[a], v[b], v[c]
            u = [pb[i] - pa[i] for i in range(3)]
            w = [pc[i] - pa[i] for i in range(3)]
            n = (u[1] * w[2] - u[2] * w[1], u[2] * w[0] - u[0] * w[2], u[0] * w[1] - u[1] * w[0])
            length = (n[0] ** 2 + n[1] ** 2 + n[2] ** 2) ** 0.5
            f.write(struct.pack("<12fH", *(x / length for x in n), *pa, *pb, *pc, 0))


def make(folder):
    """Write the three bar STLs (already oriented for printing) and the instruction sheet."""
    folder = Path(folder)
    folder.mkdir(parents=True, exist_ok=True)
    _box_stl(folder / "bar_flat.stl", L_BAR, B_BAR, H_BAR)
    _box_stl(folder / "bar_on_edge.stl", L_BAR, H_BAR, B_BAR)
    _box_stl(folder / "bar_upright.stl", B_BAR, H_BAR, L_BAR)
    text = """# Material test bars (120 x 10 x 4 mm)

Print all three with the SAME settings you use for real parts (material, walls, infill, temperature).
`bar_upright.stl` stands 120 mm tall on a 10 x 4 mm base: add a brim (8 mm) in the slicer so it does not fall over.

## Sag test (stiffness): do it for each bar
1. Lay the bar over a table edge with 20 mm on the table; hold that end down hard (a clamp, or a book and a heavy
   weight). `bar_flat` and `bar_upright` lie on their 10 mm face; `bar_on_edge` stands on its 4 mm edge.
2. Mark a point 90 mm out from the table edge. Measure its height above the floor (or against a ruler).
3. Hang a known weight at that mark (a bag with something weighed on a kitchen scale; about 200 g for the flat and
   upright bars, about 1000 g for the on-edge bar). Measure the height again. The difference is the sag.
4. Tell Claude: the weight in grams and the sag in mm for each bar.

## Break test (strength), optional but valuable
Same set-up with `bar_upright` (it is the weak direction): add weight in steps until it snaps; report the last
weight it held and the weight that broke it. Wear eye protection; the pieces can fly.

Results go in with:  python -m mechkit.calibration fit --flat GRAMS:SAG --edge GRAMS:SAG --upright GRAMS:SAG --upright-break-g GRAMS
"""
    (folder / "README.md").write_text(text, encoding="utf-8", newline="\n")
    return [str(folder / n) for n in ("bar_flat.stl", "bar_on_edge.stl", "bar_upright.stl", "README.md")]


def main():
    args = sys.argv[1:]
    if len(args) >= 2 and args[0] == "make":
        for f in make(args[1]):
            print("written:", f)
    elif args and args[0] == "fit":
        def val(flag):
            return float(args[args.index(flag) + 1]) if flag in args else None

        def pair(flag):
            return tuple(float(x) for x in args[args.index(flag) + 1].split(":")) if flag in args else None
        print(json.dumps(fit(pair("--flat"), pair("--edge"), pair("--upright"), val("--upright-break-g"), val("--flat-break-g")), indent=1))
    else:
        sys.exit(__doc__)


if __name__ == "__main__":
    main()
