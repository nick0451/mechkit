"""Stress pictures without a window (pyvista, off-screen)."""

from pathlib import Path

import numpy as np


def stress_picture(mesh, result, path, title="", exaggerate=None):
    """Save a PNG of the part coloured by von Mises stress, drawn in its deformed shape. Returns the path as text."""
    import pyvista as pv

    pv.OFF_SCREEN = True
    path = Path(path)
    corners = mesh.tets[:, :4] - 1
    cells = np.hstack([np.full((len(corners), 1), 4), corners]).ravel()
    grid = pv.UnstructuredGrid(cells, np.full(len(corners), pv.CellType.TETRA), mesh.nodes.copy())
    ev = result["element_von_mises"]
    vm = np.zeros(len(corners))
    vm[ev["ids"] - 1] = ev["vm"]
    grid.cell_data["von Mises (MPa)"] = vm
    u = np.zeros_like(mesh.nodes)
    u[result["displacements"]["ids"] - 1] = result["displacements"]["u"]
    peak = float(np.linalg.norm(u, axis=1).max())
    span = float(np.ptp(mesh.nodes, axis=0).max())
    scale = exaggerate if exaggerate is not None else (0.05 * span / peak if peak > 0 else 1.0)
    grid.points = mesh.nodes + u * scale
    plotter = pv.Plotter(off_screen=True, window_size=(1400, 900))
    plotter.add_mesh(grid, scalars="von Mises (MPa)", cmap="turbo", clim=(0.0, float(np.percentile(vm, 99.5)) or 1.0), show_edges=False,
                     scalar_bar_args={"title": "von Mises (MPa)"})
    plotter.add_mesh(pv.UnstructuredGrid(cells, np.full(len(corners), pv.CellType.TETRA), mesh.nodes.copy()).extract_feature_edges(
        boundary_edges=False, feature_edges=True, feature_angle=30), color="gray", line_width=1)
    plotter.add_text("%s   peak deflection %.3f mm (drawn x%.0f)" % (title, peak, scale), font_size=10)
    plotter.view_isometric()
    plotter.screenshot(str(path))
    plotter.close()
    return str(path)
