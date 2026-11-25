"""Known-answer check for the simulation chain: a clamped beam with a force at its free end.

    uv run python -m mechkit.sim.benchmark            mesh + deck checks; solves and compares if CalculiX is installed

Beam 100 x 10 x 10 mm along X, clamped at x = 0, 10 N downward on the end face. Hand formula (bending + shear):
    deflection = F L^3 / (3 E I) + F L / (k G A),   k = 5/6
Pass = the solver's tip deflection within 2 % of that, two mesh sizes within 2 % of each other, the reaction equal
and opposite to the applied force, and the peak bending stress near 6 F L / (b h^2) at the clamp.
"""

import json
import sys
import tempfile
from pathlib import Path

import numpy as np

from . import ccx
from .mesh import box_mesh

L, B, H, F, E, NU = 100.0, 10.0, 10.0, 10.0, 2000.0, 0.35


def hand_deflection():
    inertia = B * H ** 3 / 12.0
    g = E / (2.0 * (1.0 + NU))
    return F * L ** 3 / (3.0 * E * inertia) + F * L / ((5.0 / 6.0) * g * B * H)


def build(size):
    mesh = box_mesh(L, B, H, size)
    case = ccx.StaticCase(mesh, ccx.Material("benchmark", E, NU), name="beam_%s" % str(size).replace(".", "p"))
    clamp = mesh.faces_where(lambda c, n: np.abs(c[:, 0]) < 1e-6)
    tip = mesh.faces_where(lambda c, n: np.abs(c[:, 0] - L) < 1e-6)
    case.fix(clamp)
    case.force(tip, (0.0, 0.0, -F))
    return mesh, case, tip


def main():
    checks = []

    def check(name, ok, detail=""):
        checks.append(bool(ok))
        print("  %-4s %s  %s" % ("ok" if ok else "FAIL", name, detail))

    print("mesh and input deck (no solver needed)")
    mesh, case, tip = build(2.5)
    check("mesh volume equals the block", abs(mesh.volume() - L * B * H) < 1e-6 * L * B * H, "%.3f mm3, %s" % (mesh.volume(), mesh.info))
    check("every element is the right way round", mesh.min_signed_volume() > 0, "smallest %.4g mm3" % mesh.min_signed_volume())
    check("tip face area", abs(mesh.area(tip) - B * H) < 1e-6, "%.4f mm2" % mesh.area(tip))
    check("nodal loads add up to the applied force", np.allclose(case.applied_force(), (0, 0, -F), atol=1e-9), str(case.applied_force()))
    mids = {}
    for tet in mesh.tets:                      # every mid-edge node must sit between the two corners CalculiX expects
        for k, (a, b) in enumerate(((0, 1), (1, 2), (2, 0), (0, 3), (1, 3), (2, 3))):
            mids[int(tet[4 + k])] = max(mids.get(int(tet[4 + k]), 0.0), float(np.linalg.norm(
                mesh.nodes[tet[4 + k] - 1] - (mesh.nodes[tet[a] - 1] + mesh.nodes[tet[b] - 1]) / 2)))
    check("mid-edge nodes are in CalculiX order", max(mids.values()) < 1e-9, "worst offset %.2e mm" % max(mids.values()))
    with tempfile.TemporaryDirectory() as tmp:
        text = case.write(tmp).read_text()
        check("deck has the element, support, material and load blocks", all(k in text for k in (
            "*ELEMENT, TYPE=C3D10", "*BOUNDARY", "*ELASTIC", "*CLOAD", "*END STEP")))

    solver = ccx.find_ccx()
    if solver is None:
        print("\nCalculiX is not installed yet: the solve-and-compare part was skipped.")
        print("%d checks, %d failed" % (len(checks), checks.count(False)))
        sys.exit(1 if False in checks else 0)

    print("\nsolve and compare with the hand formula (%s)" % solver.name)
    want = hand_deflection()
    stress_want = 6.0 * F * L / (B * H ** 2)
    out = Path(tempfile.mkdtemp(prefix="mechkit_beam_"))
    tips = {}
    for size in (2.5, 1.5):
        mesh, case, tip = build(size)
        r = case.run(out)
        u, ids = r["displacements"]["u"], r["displacements"]["ids"]
        tip_nodes = mesh.nodes_of(tip)
        tips[size] = float(-u[np.isin(ids, tip_nodes), 2].mean())
        err = (tips[size] - want) / want * 100
        check("size %.1f mm: tip deflection within 2 %% of %.4f mm" % (size, want), abs(err) <= 2.0, "%.4f mm (%+.2f %%), %d nodes" % (
            tips[size], err, mesh.info["nodes"]))
        check("size %.1f mm: reaction balances the load" % size, r["reaction_n"] is not None and abs(r["reaction_n"][2] - F) < 1e-3 * F, str(r["reaction_n"]))
        check("size %.1f mm: bending stress at the clamp is about %.0f MPa" % (size, stress_want),
              0.8 * stress_want <= r["p99_von_mises_mpa"] and r["max_von_mises_mpa"] <= 2.5 * stress_want,
              "99th percentile %.2f, peak %.2f MPa" % (r["p99_von_mises_mpa"], r["max_von_mises_mpa"]))
    a, b = tips[2.5], tips[1.5]
    check("the two mesh sizes agree within 2 %", abs(a - b) / b * 100 <= 2.0, "%.4f vs %.4f mm" % (a, b))
    (out / "benchmark.json").write_text(json.dumps({"hand_mm": want, "tips_mm": tips}, indent=1))
    print("\n%d checks, %d failed (files in %s)" % (len(checks), checks.count(False), out))
    sys.exit(1 if False in checks else 0)


if __name__ == "__main__":
    main()
