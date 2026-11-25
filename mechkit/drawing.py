"""Engineering drawings of parts, drawn by text-to-cad's `cad.eng_drawing` (MIT, Copyright (c) earthtojake,
https://github.com/earthtojake/text-to-cad; used as an installed dependency, no code copied).

    part_sheet(shape, title, ...)    one A3/A4 sheet: top, front, right and iso views, overall sizes, hole callouts
    write(sheets, out_pdf)           one PDF, a page per sheet

Dimension provenance: every number on a sheet is MEASURED FROM THE SOLID as built (bounding extents for the overall
sizes, the cylinder's own radius and length for each hole). Nothing is typed in, so a drawing cannot disagree with the
model it came from. The sheet says where its numbers came from and that no tolerances are stated: the tags of the
design values (stated / measured / scaled / assumed) stay in the project's requirements.json and interface.json.
"""

import math
import os
import re
from pathlib import Path

AXES = (0, 1, 2)          # x, y, z
VIEW_AXIS = {"top": 2, "front": 1, "right": 0}     # the model axis each view looks along (third-angle, Z up)


def _cad_drawing():
    os.environ.setdefault("DO_NOT_TRACK", "1")
    import cad.eng_drawing as ed
    return ed


def _vec(v):
    return (v.X, v.Y, v.Z)


def round_holes(shape, axis, min_span=0.97):
    """Full round holes along a model axis: [{centre (3-tuple, on the axis at the hole's top), diameter, depth, thru}].
    A hole is a concave cylindrical surface whose pieces together go (almost) all the way round; fillets, slots and
    bosses are left out. Sizes come from the geometry."""
    import build123d as bd

    groups = {}
    for f in shape.faces():
        if f.geom_type != bd.GeomType.CYLINDER:
            continue
        ax = f.axis_of_rotation
        d = _vec(ax.direction)
        if abs(d[axis]) < 0.999:
            continue
        r = f.radius
        p = f.position_at(0.5, 0.5)
        n = f.normal_at(p)
        o = ax.position
        v = p - o
        radial = v - ax.direction * v.dot(ax.direction)
        if radial.length < 1e-9 or n.dot(radial) > 0:         # normal points away from the axis: a boss, not a hole
            continue
        bb = f.bounding_box()
        lo, hi = _vec(bb.min)[axis], _vec(bb.max)[axis]
        if hi - lo <= 1e-6:
            continue
        c = list(_vec(o))
        key = tuple(round(c[i], 3) for i in AXES if i != axis) + (round(r, 3), round(lo, 3), round(hi, 3))
        g = groups.setdefault(key, {"centre": c, "r": r, "lo": lo, "hi": hi, "span": 0.0})
        g["span"] += f.area / (r * (hi - lo))
    def open_at(c, at):                                        # no material just past this end of the hole, on its axis
        q = list(c)
        q[axis] = at
        return not shape.is_inside(bd.Vector(*q))

    # coaxial segments that touch end to end are one stepped hole (e.g. a counterbore, or a 4.5 / 4.4 mm step)
    lines = {}
    for g in groups.values():
        if g["span"] >= 2 * math.pi * min_span:
            lines.setdefault(tuple(round(g["centre"][i], 3) for i in AXES if i != axis), []).append(g)
    holes = []
    for segs in lines.values():
        segs.sort(key=lambda g: g["lo"])
        stacks = [[segs[0]]]
        for g in segs[1:]:
            if abs(g["lo"] - stacks[-1][-1]["hi"]) < 1e-3:
                stacks[-1].append(g)
            else:
                stacks.append([g])
        for st in stacks:
            lo, hi = st[0]["lo"], st[-1]["hi"]
            c = st[0]["centre"]
            open_lo, open_hi = open_at(c, lo - 0.05), open_at(c, hi + 0.05)
            end = hi if open_hi or not open_lo else lo              # the end it is drilled from
            at = list(c)
            at[axis] = end
            narrow = min(st, key=lambda g: g["r"])
            holes.append({"centre": tuple(at), "diameter": round(2 * narrow["r"], 3), "depth": round(hi - lo, 3),
                          "thru": open_lo and open_hi, "far_side": open_lo and not open_hi,
                          "steps": [(round(2 * g["r"], 3), round(g["hi"] - g["lo"], 3)) for g in (st if end == lo else st[::-1]) if g is not narrow]})
    return sorted(holes, key=lambda h: (h["diameter"], h["centre"]))


def part_sheet(shape, title, part_number="", material="", revision="A", author="", source="", size="A3", scale=None,
               notes=()):
    """One sheet for one part, in its own frame (the frame it prints in reads best). scale None = fit the sheet."""
    ed = _cad_drawing()
    bb = shape.bounding_box()
    if scale is None:                                          # largest standard scale that leaves room for dimensions
        w, h = {"A4": (297.0, 210.0), "A3": (420.0, 297.0), "A2": (594.0, 420.0)}.get(size, (420.0, 297.0))
        across = (bb.size.X + bb.size.Y) or 1.0                # top + right side by side; top over front, with dimension rows
        down = (bb.size.Y + bb.size.Z) or 1.0
        fit = min(0.5 * w / across, 0.5 * h / down)
        scale = next((k for k in STANDARD_SCALES if k <= fit), STANDARD_SCALES[-1])
    sheet = ed.Sheet(size=size, scale=scale, title=title.upper(), part_number=part_number, material=material,
                     revision=revision, author=author,
                     notes=("DIMENSIONS MEASURED FROM THE MODEL%s." % (" (%s)" % source if source else ""),
                            "NO TOLERANCES STATED: PRINTED PART, CHECK FIT WITH A TEST PRINT.") + tuple(notes))
    top, front, right, iso = sheet.three_views(shape, iso=True)
    views = {"top": top, "front": front, "right": right}
    called = []
    for name, view in views.items():
        view.overall()
        same = {}
        for h in round_holes(shape, VIEW_AXIS[name]):
            same.setdefault((h["diameter"], h["depth"], h["thru"], h["far_side"], tuple(h["steps"])), []).append(h)
        for (dia, depth, thru, far, steps), hs in same.items():
            first, n = hs[0], len(hs)
            if thru:                                           # the library places these clear of the views
                view.hole(first["centre"], dia, thru=True, count=n if n > 1 else None,
                          label=", ".join("Ø%g %g DEEP" % st for st in steps) or None)
            else:                                              # written out: the sheet's font has no depth / counterbore symbols
                text = "%sØ%g %g DEEP" % ("%d× " % n if n > 1 else "", dia, depth)
                text += "".join(", Ø%g %g DEEP" % st for st in steps) + (" FAR SIDE" if far else "")
                view.note(text, first["centre"])
            called.append({"view": name, "diameter": dia, "depth": None if thru else depth, "thru": thru, "count": n,
                           "steps": list(steps), "far_side": far})
    sheet.mechkit_holes = called
    sheet.mechkit_args = dict(shape=shape, title=title, part_number=part_number, material=material, revision=revision,
                              author=author, source=source, size=size, scale=scale, notes=notes)
    return sheet


STANDARD_SCALES = (2.0, 1.5, 1.0, 0.75, 0.5, 0.25, 0.2, 0.1)


def write(sheets, out_pdf):
    """Write sheets (one or a list) as one PDF; returns the path."""
    ed = _cad_drawing()
    out = Path(out_pdf).resolve()
    out.parent.mkdir(parents=True, exist_ok=True)
    sheets = list(sheets) if isinstance(sheets, (list, tuple)) else [sheets]
    def mechkit_drawing():                                     # its name is printed in the title block
        return sheets
    for _ in range(len(sheets) * len(STANDARD_SCALES)):
        try:
            result = ed.eng_drawing(mechkit_drawing, out=str(out))()
            return Path(result[0]) if isinstance(result, (list, tuple)) else out
        except ValueError as e:                                # a sheet whose views run off the frame: next scale down
            m = re.match(r"sheet (\d+) .*off the frame", str(e))
            i = int(m.group(1)) - 1 if m else -1
            args = getattr(sheets[i], "mechkit_args", None) if 0 <= i < len(sheets) else None
            smaller = [k for k in STANDARD_SCALES if args and k < args["scale"]]
            if not smaller:
                raise
            sheets[i] = part_sheet(**dict(args, scale=smaller[0]))
    raise RuntimeError("drawings: no scale fits")
