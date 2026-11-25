"""Load cases as data: where a part is held, where it is pushed, and what counts as passing.

`sim/loadcases.json` in a project (mm, N):

    {"parts": [{
        "name": "Bracket", "step": "work/bracket.step", "keep_bbox": [[...], [...]],
        "mesh_sizes": [3.0, 2.0], "material": "petg_printed_assumed", "layers": "in_plane",
        "cases": [{
            "name": "lean",  "min_safety_factor": 3.0, "max_deflection_mm": 1.0,
            "fix":   [{"type": "plane", "normal": [0, 0, 1], "offset": -49.5}],
            "loads": [{"force": [0, 29.3, 6.2], "on": {"type": "extreme", "direction": [0, 0.978, 0.208], "which": "min"}}]
        }]}]}

Selectors pick surface triangles of the mesh by geometry, so they work for any CAD source:
    plane     triangles lying in the plane  normal . x = offset  (tol, default 0.05 mm)
    extreme   triangles at the lowest ("min") or highest ("max") point along a direction, facing along it (tol 0.3 mm)
    cylinder  triangles on a cylinder: a point on its axis, the axis direction, its diameter (tol 0.1 mm);
              optional "span": [lo, hi] = only between these distances along the axis from the point
    box       every triangle whose centroid is inside [[min], [max]]
Any selector may add "box": [[min], [max]] to limit it to a region, and
"limit": {"direction": [..], "which": "min" | "max", "length": L} to keep only the part of the selection within L mm
of its own end along a direction (e.g. the rear 12 mm of a foot's contact face).
A part may name its "source": {"document", "component"}: `python -m mechkit sim <project> --refresh` then re-exports
that component from the open Fusion document before meshing (read-only, the active tab is not switched).

What is reported per case: peak deflection; peak stress with the elements touching the supports left out (a rigid
support creates an artificial stress spike there); the 99th-percentile stress; safety factors against the material's
strength along the layers and across them; and whether two mesh sizes agree (if not, the peak sits on a sharp corner
and the number is not trustworthy as a pass).
"""

import json
from pathlib import Path

import numpy as np

from . import ccx
from .mesh import step_mesh

KIT_ROOT = Path(__file__).resolve().parents[2]
CONVERGENCE_LIMIT = 0.15          # peak stress may differ this much between the two mesh sizes


def load_materials():
    return json.loads((KIT_ROOT / "mechkit" / "materials.json").read_text(encoding="utf-8"))["materials"]


def material_problem(name, m):
    """Why a material card cannot be used as it is tagged, or None. A 'calibrated' card must say where its numbers came
    from: calibration = {"date", "bars" (the measurements, as `python -m mechkit.calibration fit` prints them),
    "print_settings"}."""
    if m.get("tag") == "calibrated":
        c = m.get("calibration")
        missing = [k for k in ("date", "bars", "print_settings") if not (isinstance(c, dict) and c.get(k))]
        if missing:
            return "material '%s' is tagged calibrated but its calibration record lacks %s" % (name, ", ".join(missing))
    return None


def _sha256(path):
    import hashlib
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _unit(v):
    v = np.asarray(v, dtype=float)
    return v / np.linalg.norm(v)


def select(mesh, sel):
    """Indices of the surface triangles a selector picks."""
    c = mesh.tri_centroids()
    n, _ = mesh.tri_normals_areas()
    kind = sel["type"]
    if kind == "plane":
        d = _unit(sel["normal"])
        mask = (np.abs(c @ d - sel["offset"]) <= sel.get("tol", 0.05)) & (np.abs(n @ d) > 0.99)
    elif kind == "extreme":
        d = _unit(sel["direction"])
        corners = mesh.tri_corners() @ d                                   # (k, 3) heights of each triangle's corners
        level = corners.min() if sel.get("which", "min") == "min" else corners.max()
        mask = (np.abs(corners - level).max(axis=1) <= sel.get("tol", 0.3)) & (np.abs(n @ d) > 0.99)
    elif kind == "cylinder":
        a, p = _unit(sel["axis"]), np.asarray(sel["point"], dtype=float)
        w = c - p
        radial = w - np.outer(w @ a, a)
        dist = np.linalg.norm(radial, axis=1)
        tol = sel.get("tol", 0.1)
        # a flat triangle's centroid sits slightly inside the true cylinder: allow the sag of one element edge
        sag = (sel["d"] / 2) - np.sqrt(np.maximum((sel["d"] / 2) ** 2 - (mesh.size / 2) ** 2, 0))
        # the triangle must also FACE the axis (its normal runs along the radius): a flat face that merely passes the
        # axis at the right distance is not part of the cylinder (seen 2026-11-24: a lip's top face was picked up)
        radial_unit = radial / np.maximum(dist, 1e-12)[:, None]
        mask = (dist <= sel["d"] / 2 + tol) & (dist >= sel["d"] / 2 - tol - sag) & (np.abs(n @ a) < 0.3) & (np.abs(np.einsum("ij,ij->i", n, radial_unit)) > 0.7)
        if "span" in sel:                                   # optional: only between these two distances along the axis from `point`
            along = w @ a
            mask &= (along >= sel["span"][0]) & (along <= sel["span"][1])
    elif kind == "box":
        mask = np.ones(len(c), dtype=bool)
    else:
        raise ValueError("unknown selector type %r" % kind)
    if "box" in sel or kind == "box":
        lo, hi = np.asarray((sel.get("box") or [sel["min"], sel["max"]])[0], dtype=float), np.asarray((sel.get("box") or [sel["min"], sel["max"]])[1], dtype=float)
        mask &= np.all((c >= lo) & (c <= hi), axis=1)
    idx = np.nonzero(mask)[0]
    if "limit" in sel and len(idx):
        lim = sel["limit"]
        h = c[idx] @ _unit(lim["direction"])
        end = h.min() if lim.get("which", "min") == "min" else h.max()
        idx = idx[np.abs(h - end) <= lim["length"]]
    return idx


def run_case(mesh, material, case, workdir, name):
    sim = ccx.StaticCase(mesh, material, name=name)
    fixed_tris = np.unique(np.concatenate([select(mesh, s) for s in case["fix"]]))
    sim.fix(fixed_tris)
    for load in case["loads"]:
        sim.force(select(mesh, load["on"]), load["force"])
    r = sim.run(workdir)
    # peak stress away from the supports
    fixed_nodes = set(int(x) for x in mesh.nodes_of(fixed_tris))
    touching = np.array([i + 1 for i, tet in enumerate(mesh.tets) if fixed_nodes.intersection(int(x) for x in tet)])
    ev = r["element_von_mises"]
    free = ~np.isin(ev["ids"], touching)
    r["peak_stress_mpa"] = round(float(ev["vm"][free].max()), 3)
    r["peak_stress_element"] = int(ev["ids"][free][np.argmax(ev["vm"][free])])
    corners = mesh.nodes[mesh.tets[r["peak_stress_element"] - 1, :4] - 1]
    r["peak_stress_at"] = [round(float(x), 1) for x in corners.mean(axis=0)]          # where to look (mm, model coordinates)
    r["stress_at_supports_mpa"] = round(float(ev["vm"][~free].max()), 3) if (~free).any() else None
    return r


def run_part(part, project_root, out_dir, materials=None, pictures=True):
    """Run every case of one part on its mesh sizes. Returns the list of case results (plain data)."""
    materials = materials or load_materials()
    m = materials[part["material"]]
    bad = material_problem(part["material"], m)
    if bad:
        raise ValueError(bad)
    material = ccx.Material(part["material"], m["e_mpa"], m["nu"], m["strength_mpa"], m["tag"])
    across = m["strength_mpa"] * m["across_layers_factor"]
    project_root, out_dir = Path(project_root), Path(out_dir)
    sizes = sorted(part["mesh_sizes"], reverse=True)
    step_hash = _sha256(project_root / part["step"])            # binds every result to the exact geometry simulated
    meshes = {s: step_mesh(project_root / part["step"], s, keep_bbox=part.get("keep_bbox")) for s in sizes}
    results = []
    for case in part["cases"]:
        runs = {}
        for s in sizes:
            tag = "%s_%s_%s" % (part["name"], case["name"], str(s).replace(".", "p"))
            tag = "".join(ch if ch.isalnum() else "_" for ch in tag)
            runs[s] = run_case(meshes[s], material, case, out_dir / "work", tag)
        fine = runs[sizes[-1]]
        coarse = runs[sizes[0]]
        spread = abs(fine["peak_stress_mpa"] - coarse["peak_stress_mpa"]) / max(fine["peak_stress_mpa"], 1e-9) if len(sizes) > 1 else None
        converged = spread is None or spread <= CONVERGENCE_LIMIT
        layers = part.get("layers", "unknown")
        strength = m["strength_mpa"] if layers == "in_plane" else across
        sf = strength / fine["peak_stress_mpa"]
        res = {
            "part": part["name"], "case": case["name"], "layers": layers, "step": Path(part["step"]).as_posix(), "step_sha256": step_hash,
            "material": {"name": part["material"], "tag": m["tag"], "e_mpa": m["e_mpa"], "strength_mpa": m["strength_mpa"], "strength_used_mpa": strength,
                         "calibration": m.get("calibration")},
            "applied_force_n": fine["applied_force_n"], "reaction_n": fine["reaction_n"],
            "max_deflection_mm": fine["max_displacement_mm"], "peak_stress_mpa": fine["peak_stress_mpa"], "peak_stress_at": fine["peak_stress_at"],
            "p99_stress_mpa": fine["p99_von_mises_mpa"], "stress_at_supports_mpa": fine["stress_at_supports_mpa"],
            "safety_factor": round(sf, 2), "safety_factor_along_layers": round(m["strength_mpa"] / fine["peak_stress_mpa"], 2),
            "safety_factor_across_layers": round(across / fine["peak_stress_mpa"], 2),
            "mesh": {str(s): {"nodes": meshes[s].info["nodes"], "peak_stress_mpa": runs[s]["peak_stress_mpa"],
                              "max_deflection_mm": runs[s]["max_displacement_mm"]} for s in sizes},
            "mesh_spread": None if spread is None else round(spread, 3), "converged": converged, "setup": fine["setup"],
            "repeat_check": sorted(set(runs[s]["repeat_check"] for s in sizes)),
        }
        problems = []
        if "min_safety_factor" in case and sf < case["min_safety_factor"]:
            problems.append("safety factor %.2f is below %.2f" % (sf, case["min_safety_factor"]))
        if "max_deflection_mm" in case and fine["max_displacement_mm"] > case["max_deflection_mm"]:
            problems.append("deflection %.3f mm is above %.3f mm" % (fine["max_displacement_mm"], case["max_deflection_mm"]))
        balance = np.asarray(fine["reaction_n"]) + np.asarray(fine["applied_force_n"]) if fine["reaction_n"] else None     # reaction = -load
        if balance is None or np.abs(balance).max() > 1e-3 * max(1.0, np.abs(fine["applied_force_n"]).max()):
            problems.append("reaction does not balance the applied force (check the supports)")
        res["problems"] = problems
        res["warnings"] = [r for r in res["repeat_check"] if r.startswith("SOLVER")] + ([] if converged else ["peak stress changed %.0f %% between mesh sizes: it sits on a sharp corner; treat the safety factor as a lower bound" % (spread * 100)]) + \
            (["material is '%s': good for ranking, not for approval" % m["tag"]] if m["tag"] != "calibrated" else [])
        if pictures:
            from . import picture
            res["picture"] = picture.stress_picture(meshes[sizes[-1]], fine, out_dir / ("%s.png" % "".join(
                ch if ch.isalnum() else "_" for ch in "%s_%s" % (part["name"], case["name"]))), title="%s: %s" % (part["name"], case["name"]))
        results.append(res)
    for scratch in (out_dir / "work").glob("*"):          # solver scratch is large (tens of MB per run) and can be rebuilt
        if scratch.suffix in (".frd", ".dat", ".12d", ".cvg", ".sta"):
            scratch.unlink(missing_ok=True)
    return results


def run_file(loadcases_path, out_dir=None, pictures=True):
    """Run a project's loadcases.json; writes sim_report.json (and pictures) into out_dir. Returns the report."""
    path = Path(loadcases_path).resolve()
    project_root = path.parent.parent                       # <project>/sim/loadcases.json
    out_dir = Path(out_dir) if out_dir else path.parent / "reports"
    out_dir.mkdir(parents=True, exist_ok=True)
    data = json.loads(path.read_text(encoding="utf-8"))
    cases = []
    for part in data["parts"]:
        cases += run_part(part, project_root, out_dir, pictures=pictures)
    try:                                                       # a path inside the project, never an absolute one: reports get shared
        source = Path(path).resolve().relative_to(Path(project_root).resolve()).as_posix()
    except ValueError:
        source = Path(path).name
    report = {"source": source, "solver": ccx.find_ccx().name, "cases": cases,
              "problems": ["%s / %s: %s" % (c["part"], c["case"], p) for c in cases for p in c["problems"]]}
    tmp = out_dir / "sim_report.json.tmp"                      # written whole, then swapped in: never a half-written report
    tmp.write_text(json.dumps(report, indent=1), encoding="utf-8")
    tmp.replace(out_dir / "sim_report.json")
    return report


def print_report(report):
    print("%-26s %-14s %9s %9s %7s %7s %-9s" % ("part", "case", "defl mm", "peak MPa", "SF", "SF x", "mesh"))
    for c in report["cases"]:
        print("%-26s %-14s %9.3f %9.2f %7.1f %7.1f %-9s" % (c["part"][:26], c["case"][:14], c["max_deflection_mm"], c["peak_stress_mpa"],
              c["safety_factor_along_layers"], c["safety_factor_across_layers"], "ok" if c["converged"] else "CORNER"))
        print("      peak stress at x %.1f, y %.1f, z %.1f" % tuple(c["peak_stress_at"]))
        for w in c["warnings"]:
            print("      note: " + w)
        for p in c["problems"]:
            print("      PROBLEM: " + p)
    print("SF = strength along the layers / peak stress; SF x = across the layers. %d problem(s)." % len(report["problems"]))
