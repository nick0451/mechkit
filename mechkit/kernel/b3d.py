"""Headless geometry with build123d (OpenCascade): helpers shared by part definitions. Lengths in mm.

A part definition is a plain function  build(params, inputs) -> solid.  It can run without Fusion, many at once.
`body_info(solid, name)` describes a solid in the same layout as the Fusion model dump
(a JSON dump of bodies, boxes and round faces), so checks can read geometry from either CAD source.
"""

from pathlib import Path

import build123d as bd


def prism_x(points_yz, x0, width, holes_yz=()):
    """Extrude a polygon drawn in the YZ plane (list of (y, z)) along +X from x0 by width. holes_yz: inner polygons."""
    def wire(pts):
        return bd.Wire.make_polygon([bd.Vector(x0, y, z) for (y, z) in pts], close=True)
    face = bd.Face(wire(points_yz), [wire(h) for h in holes_yz])
    return bd.Solid.extrude(face, bd.Vector(width, 0, 0))


def hole_z(solid, x, y, z_top, depth, diameter):
    """Cut a round hole along -Z from z_top."""
    cutter = bd.Pos(x, y, z_top - depth / 2) * bd.Cylinder(diameter / 2, depth + 0.02)
    return solid - cutter


def union(*solids):
    out = solids[0]
    for s in solids[1:]:
        out = out + s
    return out


class GeometryCheckError(RuntimeError):
    """A geometric check could not be computed. Callers must treat it as a failed check, never as a pass."""


def overlap_volume(a, b):
    """Volume shared by two solids, in mm3. Raises GeometryCheckError when it cannot be computed: an invalid solid or a
    failed boolean is never reported as 'no overlap'."""
    for s in (a, b):
        if not s.is_valid:
            raise GeometryCheckError("a solid is not valid geometry")
    try:
        common = a & b
        return float(common.volume) if common is not None else 0.0
    except Exception as e:
        raise GeometryCheckError("the intersection failed: %s" % e) from e


def edges_along_x_near(solid, points_yz, tol=0.05):
    """Edges parallel to X whose (y, z) position is within tol of one of the given points."""
    found = []
    for e in solid.edges():
        a, b = e.position_at(0), e.position_at(1)
        if abs(a.Y - b.Y) > 1e-6 or abs(a.Z - b.Z) > 1e-6 or abs(a.X - b.X) < 1e-6:
            continue
        if any(abs(a.Y - y) <= tol and abs(a.Z - z) <= tol for (y, z) in points_yz):
            found.append(e)
    return found


def body_info(solid, name):
    """Volume, area, bounding box and round faces of a solid, in the model-dump layout."""
    bb = solid.bounding_box()
    cyl = []
    for f in solid.faces():
        if f.geom_type != bd.GeomType.CYLINDER:
            continue
        axis = f.axis_of_rotation
        a = [axis.direction.X, axis.direction.Y, axis.direction.Z]
        k = max(range(3), key=lambda i: abs(a[i]))
        if a[k] < 0:
            a = [-c for c in a]
        fb = f.bounding_box()
        lo = [fb.min.X, fb.min.Y, fb.min.Z][k] * a[k]
        hi = [fb.max.X, fb.max.Y, fb.max.Z][k] * a[k]
        cyl.append({"o": [round(axis.position.X, 4), round(axis.position.Y, 4), round(axis.position.Z, 4)], "a": [round(c, 6) for c in a],
                    "r": round(f.radius, 4), "lo": round(min(lo, hi), 4), "hi": round(max(lo, hi), 4), "k": k})
    return {"name": name, "solid": bool(solid.is_valid), "volume_mm3": round(solid.volume, 2), "area_mm2": round(solid.area, 2),
            "bbox": [[round(bb.min.X, 4), round(bb.min.Y, 4), round(bb.min.Z, 4)], [round(bb.max.X, 4), round(bb.max.Y, 4), round(bb.max.Z, 4)]],
            "cyl": cyl}


def save_step(solid, path):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    bd.export_step(solid, str(path))
    return path


def save_stl(solid, path, tolerance=0.02):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    bd.export_stl(solid, str(path), tolerance=tolerance)
    return path
