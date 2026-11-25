"""Solid meshes for CalculiX, made with gmsh. Lengths in mm.

    mesh = box_mesh(100, 10, 10, size=2.5)            a plain block (benchmarks)
    mesh = step_mesh("part.step", size=2.0)           any solid exported from Fusion or build123d

A Mesh holds second-order tetrahedra (10 nodes, CalculiX type C3D10) and the 6-node triangles on the outer surface.
Surface regions for supports and loads are picked with plain geometric tests on the triangles (`faces_where`), so the
same load case works whichever program made the geometry.
"""

from dataclasses import dataclass, field
from pathlib import Path

import gmsh
import numpy as np

# gmsh orders the last two edge nodes of a 10-node tetrahedron the other way round from CalculiX / Abaqus
GMSH_TO_CCX_TET10 = [0, 1, 2, 3, 4, 5, 6, 7, 9, 8]


@dataclass
class Mesh:
    nodes: np.ndarray                 # (n, 3) coordinates, mm; row i is node id i + 1
    tets: np.ndarray                  # (m, 10) node ids (1-based), CalculiX C3D10 order
    tris: np.ndarray                  # (k, 6) surface triangles: 3 corner ids then 3 mid-edge ids (1-based)
    size: float = 0.0
    source: str = ""
    info: dict = field(default_factory=dict)

    # ------------------------------------------------------------------ geometry of the surface triangles
    def tri_corners(self):
        return self.nodes[self.tris[:, :3] - 1]                     # (k, 3, 3)

    def tri_centroids(self):
        return self.tri_corners().mean(axis=1)

    def tri_normals_areas(self):
        c = self.tri_corners()
        n = np.cross(c[:, 1] - c[:, 0], c[:, 2] - c[:, 0])
        length = np.linalg.norm(n, axis=1)
        return n / length[:, None], length / 2.0

    def faces_where(self, test):
        """Indices of surface triangles whose (centroid, unit normal) satisfy test(c, n) -> bool array."""
        normals, _ = self.tri_normals_areas()
        return np.nonzero(test(self.tri_centroids(), normals))[0]

    def area(self, tri_idx):
        return float(self.tri_normals_areas()[1][tri_idx].sum())

    def nodes_of(self, tri_idx):
        """All node ids (corner + mid-edge) of the given surface triangles."""
        return np.unique(self.tris[tri_idx])

    def volume(self):
        """Volume from the corner nodes (exact for straight-sided elements)."""
        p = self.nodes[self.tets[:, :4] - 1]
        return float(np.einsum("ij,ij->i", np.cross(p[:, 1] - p[:, 0], p[:, 2] - p[:, 0]), p[:, 3] - p[:, 0]).sum() / 6.0)

    def min_signed_volume(self):
        p = self.nodes[self.tets[:, :4] - 1]
        return float((np.einsum("ij,ij->i", np.cross(p[:, 1] - p[:, 0], p[:, 2] - p[:, 0]), p[:, 3] - p[:, 0]) / 6.0).min())


def _collect(size, source):
    """Read nodes, 10-node tetrahedra and 6-node surface triangles out of the current gmsh model."""
    tags, coords, _ = gmsh.model.mesh.getNodes()
    order = np.argsort(tags)
    tags, coords = np.asarray(tags)[order], np.asarray(coords).reshape(-1, 3)[order]
    renumber = {int(t): i + 1 for i, t in enumerate(tags)}          # gmsh tags can have gaps: make them 1..n
    remap = np.vectorize(renumber.__getitem__)
    tet_tags, tet_nodes = gmsh.model.mesh.getElementsByType(11)      # 11 = 10-node tetrahedron
    tri_tags, tri_nodes = gmsh.model.mesh.getElementsByType(9)       # 9 = 6-node triangle
    if len(tet_tags) == 0:
        raise RuntimeError("gmsh produced no solid elements (is the geometry a closed solid?)")
    tets = remap(np.asarray(tet_nodes).reshape(-1, 10))[:, GMSH_TO_CCX_TET10]
    tris = remap(np.asarray(tri_nodes).reshape(-1, 6))
    mesh = Mesh(nodes=coords, tets=tets, tris=tris, size=size, source=source)
    mesh.info = {"nodes": int(len(coords)), "tets": int(len(tets)), "surface_triangles": int(len(tris)), "size_mm": size}
    return mesh


def _generate(size):
    gmsh.option.setNumber("General.Terminal", 0)
    gmsh.option.setNumber("Mesh.MeshSizeMax", size)
    gmsh.option.setNumber("Mesh.MeshSizeMin", size * 0.25)
    gmsh.option.setNumber("Mesh.ElementOrder", 2)
    gmsh.option.setNumber("Mesh.SecondOrderLinear", 1)      # straight edges: mid nodes exactly at mid-edge
    gmsh.option.setNumber("Mesh.Algorithm3D", 1)            # Delaunay
    gmsh.model.mesh.generate(3)


def box_mesh(lx, ly, lz, size, origin=(0.0, 0.0, 0.0)):
    """A block lx x ly x lz (mm) with one corner at `origin`."""
    gmsh.initialize()
    try:
        gmsh.model.add("box")
        gmsh.model.occ.addBox(*origin, lx, ly, lz)
        gmsh.model.occ.synchronize()
        _generate(size)
        return _collect(size, "box %g x %g x %g" % (lx, ly, lz))
    finally:
        gmsh.finalize()


def built_mesh(build, size, name="built", step_out=None):
    """Mesh a solid made by `build(occ)` with gmsh's own geometry kernel (tests, simple shapes).

    build(occ) creates the solid(s) with gmsh.model.occ calls. step_out: also save the geometry as a STEP file.
    """
    gmsh.initialize()
    try:
        gmsh.model.add(name)
        build(gmsh.model.occ)
        gmsh.model.occ.synchronize()
        if step_out is not None:
            gmsh.option.setNumber("General.Terminal", 0)
            gmsh.write(str(step_out))
        _generate(size)
        return _collect(size, name)
    finally:
        gmsh.finalize()


def step_mesh(path, size, curved=False, keep_bbox=None, bbox_tol=0.05):
    """Mesh the solids of a STEP file (units are taken as mm). curved=True lets mid nodes follow curved faces.

    keep_bbox=[[xmin, ymin, zmin], [xmax, ymax, zmax]]: mesh only the solid whose bounding box matches (a component
    exported from Fusion holds all its bodies; `fusion_export.component_step` returns each body's box).
    """
    path = Path(path)
    if not path.is_file():
        raise FileNotFoundError(path)
    gmsh.initialize()
    try:
        gmsh.model.add(path.stem)
        gmsh.option.setString("Geometry.OCCTargetUnit", "MM")
        gmsh.model.occ.importShapes(str(path))
        gmsh.model.occ.synchronize()
        solids = gmsh.model.getEntities(3)
        if not solids:
            raise RuntimeError("%s holds no solid body" % path.name)
        if keep_bbox is not None:
            want = list(keep_bbox[0]) + list(keep_bbox[1])
            match = [s for s in solids if max(abs(a - b) for a, b in zip(gmsh.model.getBoundingBox(*s), want, strict=True)) <= bbox_tol + 2e-7 * 1e3]
            if len(match) != 1:
                boxes = [[round(x, 2) for x in gmsh.model.getBoundingBox(*s)] for s in solids]
                raise RuntimeError("%d solids match the wanted box %s; solids in the file: %s" % (len(match), want, boxes))
            gmsh.model.occ.remove([s for s in solids if s != match[0]], recursive=True)
            gmsh.model.occ.synchronize()
        gmsh.option.setNumber("General.Terminal", 0)
        gmsh.option.setNumber("Mesh.MeshSizeMax", size)
        gmsh.option.setNumber("Mesh.MeshSizeMin", size * 0.2)
        gmsh.option.setNumber("Mesh.MeshSizeFromCurvature", 12)
        gmsh.option.setNumber("Mesh.ElementOrder", 2)
        gmsh.option.setNumber("Mesh.SecondOrderLinear", 0 if curved else 1)
        gmsh.option.setNumber("Mesh.Algorithm3D", 1)
        gmsh.model.mesh.generate(3)
        return _collect(size, path.name)
    finally:
        gmsh.finalize()
