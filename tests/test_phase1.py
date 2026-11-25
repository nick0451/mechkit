"""Phase 1 tests: face selectors, load cases from a STEP file, pass / fail judgement, calibration maths.

    uv run python tests/test_phase1.py

Needs the CalculiX solver (tools/ccx) but not Fusion. Works in a temporary folder.
"""

import json
import shutil
import sys
import tempfile
from pathlib import Path

import numpy as np

KIT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(KIT))
from mechkit import calibration, requirements  # noqa: E402
from mechkit.sim import ccx, loadcase  # noqa: E402
from mechkit.sim.mesh import built_mesh, step_mesh  # noqa: E402

results = []


def check(name, cond, detail=""):
    results.append(bool(cond))
    print("  %-4s %s  %s" % ("ok" if cond else "FAIL", name, detail if not cond or detail else ""))


def main():
    if ccx.find_ccx() is None:
        print("skipped: the CalculiX solver was not found (set MECHKIT_CCX or put it under tools/ccx; see the README)")
        print("\n0 checks, 0 failed")
        sys.exit(0)
    tmp = Path(tempfile.mkdtemp(prefix="mechkit_phase1_"))
    project = tmp / "proj"
    (project / "sim" / "geometry").mkdir(parents=True)
    try:
        print("selectors (block 60 x 20 x 10 with a 6 mm hole along Z at x=45, y=10)")

        def plate(occ):
            box = occ.addBox(0, 0, 0, 60, 20, 10)
            hole = occ.addCylinder(45, 10, -1, 0, 0, 12, 3.0)
            occ.cut([(3, box)], [(3, hole)])
        mesh = built_mesh(plate, 2.0, step_out=project / "sim" / "geometry" / "plate.step")
        area = lambda sel: mesh.area(loadcase.select(mesh, sel))
        check("plane picks the whole end face", abs(area({"type": "plane", "normal": [1, 0, 0], "offset": 0.0}) - 200.0) < 1e-6)
        check("plane + box picks half of it", abs(area({"type": "plane", "normal": [1, 0, 0], "offset": 0.0, "box": [[-1, -1, -1], [1, 10.0001, 11]]}) - 100.0) < 12.0)
        top = np.pi * 9.0
        check("extreme max along Z picks the top face (minus the hole)", abs(area({"type": "extreme", "direction": [0, 0, 1], "which": "max"}) - (1200.0 - top)) < 3.0,   # straight-edged triangles make the round hole slightly smaller
              "%.2f" % area({"type": "extreme", "direction": [0, 0, 1], "which": "max"}))
        lim = area({"type": "extreme", "direction": [0, 0, 1], "which": "max", "limit": {"direction": [1, 0, 0], "which": "min", "length": 10.0}})
        check("limit keeps the first 10 mm of that face", 150.0 < lim < 250.0, "%.1f" % lim)
        cyl = area({"type": "cylinder", "point": [45, 10, 0], "axis": [0, 0, 1], "d": 6.0})
        check("cylinder picks the hole wall", abs(cyl - np.pi * 6.0 * 10.0) / (np.pi * 60.0) < 0.06, "%.1f vs %.1f" % (cyl, np.pi * 60.0))
        check("a selector that matches nothing is refused by the case", _raises(ValueError, lambda: ccx.StaticCase(
            mesh, ccx.Material("m", 2000, 0.35)).fix(loadcase.select(mesh, {"type": "plane", "normal": [1, 0, 0], "offset": 999.0}))))

        print("STEP round trip")
        m2 = step_mesh(project / "sim" / "geometry" / "plate.step", 2.0)
        check("the STEP file meshes to the same volume", abs(m2.volume() - mesh.volume()) < 1e-3 * mesh.volume(), "%.2f vs %.2f" % (m2.volume(), mesh.volume()))

        print("load cases: a beam 100 x 10 x H, clamped at x = 0, 10 N down on the end")

        def beam(h):
            def build(occ):
                occ.addBox(0, 0, 0, 100, 10, h)
            return build
        for h in (10.0, 3.0):
            built_mesh(beam(h), 3.0, step_out=project / "sim" / "geometry" / ("beam_%g.step" % h))
        materials = {"test_assumed": {"tag": "assumed", "e_mpa": 2000.0, "nu": 0.35, "strength_mpa": 40.0, "across_layers_factor": 0.5},
                     "test_calibrated": {"tag": "calibrated", "e_mpa": 2000.0, "nu": 0.35, "strength_mpa": 40.0, "across_layers_factor": 0.5,
                                         "calibration": {"date": "2026-11-25", "bars": {"flat": {"weight_g": 200, "sag_mm": 4.1}},
                                                         "print_settings": "test: 0.2 mm layers, 3 walls"}},
                     "test_calibrated_unbacked": {"tag": "calibrated", "e_mpa": 2000.0, "nu": 0.35, "strength_mpa": 40.0, "across_layers_factor": 0.5}}

        def part(h, material, layers="in_plane"):
            return {"name": "beam %g" % h, "step": "sim/geometry/beam_%g.step" % h, "mesh_sizes": [3.0, 2.0], "material": material, "layers": layers,
                    "cases": [{"name": "tip", "min_safety_factor": 3.0, "max_deflection_mm": 5.0,
                               "fix": [{"type": "plane", "normal": [1, 0, 0], "offset": 0.0}],
                               "loads": [{"force": [0, 0, -10.0], "on": {"type": "plane", "normal": [1, 0, 0], "offset": 100.0}}]}]}
        out = project / "sim" / "reports"
        thick = loadcase.run_part(part(10.0, "test_assumed"), project, out, materials, pictures=True)[0]
        hand = 10.0 * 100.0 ** 3 / (3 * 2000.0 * 10.0 * 10.0 ** 3 / 12) + 10.0 * 100.0 / ((5 / 6) * (2000.0 / 2.7) * 100.0)
        check("thick beam deflection within 3 % of the hand formula", abs(thick["max_deflection_mm"] - hand) / hand < 0.03,
              "%.4f vs %.4f mm" % (thick["max_deflection_mm"], hand))
        check("thick beam passes (safety factor about 40 / 6)", thick["problems"] == [] and 5.0 < thick["safety_factor"] < 9.0, thick["safety_factor"])
        check("the two mesh sizes agree and the solver repeated itself", thick["converged"] and thick["repeat_check"] == ["two runs agree"], thick["repeat_check"])
        check("an assumed material is flagged in the warnings", any("assumed" in w for w in thick["warnings"]))
        check("a stress picture was written", Path(thick["picture"]).is_file() and Path(thick["picture"]).stat().st_size > 20000)
        thin = loadcase.run_part(part(3.0, "test_assumed"), project, out, materials, pictures=False)[0]
        check("NEGATIVE: the 3 mm beam fails both limits", len(thin["problems"]) == 2 and thin["safety_factor"] < 1.0 and thin["max_deflection_mm"] > 5.0, thin["problems"])
        across = loadcase.run_part(part(10.0, "test_assumed", "across"), project, out, materials, pictures=False)[0]
        check("loading across the layers halves the safety factor", abs(across["safety_factor"] - thick["safety_factor"] / 2) < 0.02, across["safety_factor"])

        print("requirements: strength counts only when the material is calibrated")
        req = [{"id": "S1", "text": "strong enough", "check": {"type": "strength_min_safety_factor", "min": 3.0}}]
        out.mkdir(parents=True, exist_ok=True)
        (out / "sim_report.json").write_text(json.dumps({"cases": [thick]}, default=str))
        r = requirements.evaluate(req, [out], project)[0]
        check("assumed material + safety factor 6.7 -> 'not evaluated', not a pass", r["status"] == "not evaluated" and "calibrate" in r["detail"], r)
        check("NEGATIVE: a card tagged calibrated without a calibration record is refused by the simulation",
              _raises(ValueError, lambda: loadcase.run_part(part(10.0, "test_calibrated_unbacked"), project, out, materials, pictures=False)))
        cal = loadcase.run_part(part(10.0, "test_calibrated"), project, out, materials, pictures=False)[0]
        check("each result records the STEP file and its sha256", cal["step"] == "sim/geometry/beam_10.step" and len(cal["step_sha256"]) == 64)
        (out / "sim_report.json").write_text(json.dumps({"cases": [cal]}, default=str))
        check("calibrated material -> pass", requirements.evaluate(req, [out], project)[0]["status"] == "pass")
        r = requirements.evaluate(req, [out])[0]
        check("without the project folder the geometry cannot be confirmed -> 'not evaluated'", r["status"] == "not evaluated", r)

        def report_with(**change):
            c = json.loads(json.dumps(cal, default=str))
            for k, v in change.items():
                if k == "material":
                    c["material"].update(v)
                else:
                    c[k] = v
            (out / "sim_report.json").write_text(json.dumps({"cases": [c]}, default=str))
            return requirements.evaluate(req, [out], project)[0]
        r = report_with(converged=False)
        check("NEGATIVE: mesh sizes disagree -> 'not evaluated'", r["status"] == "not evaluated" and "mesh" in r["detail"], r)
        r = report_with(warnings=["SOLVER: did not converge"])
        check("NEGATIVE: a solver warning -> 'not evaluated'", r["status"] == "not evaluated" and "solver" in r["detail"], r)
        r = report_with(problems=["reaction does not balance the applied force (check the supports)"])
        check("NEGATIVE: a case with a problem fails even with a high safety factor", r["status"] == "fail" and "reaction" in r["detail"], r)
        r = report_with(material={"calibration": None})
        check("NEGATIVE: a report whose calibrated material has no record -> 'not evaluated'", r["status"] == "not evaluated" and "record" in r["detail"], r)
        r = report_with(step_sha256=None)
        check("NEGATIVE: a result without a geometry hash -> 'not evaluated'", r["status"] == "not evaluated" and "geometry" in r["detail"], r)
        (out / "sim_report.json").write_text(json.dumps({"cases": [cal]}, default=str))
        step = project / "sim" / "geometry" / "beam_10.step"
        step.write_bytes(step.read_bytes() + b"\n")
        r = requirements.evaluate(req, [out], project)[0]
        check("NEGATIVE: the STEP file changed after the simulation -> 'not evaluated'", r["status"] == "not evaluated" and "changed" in r["detail"], r)
        (out / "sim_report.json").write_text(json.dumps({"cases": [thin]}, default=str))
        check("the thin beam -> fail, whatever the tag", requirements.evaluate(req, [out], project)[0]["status"] == "fail")

        print("calibration maths")
        f = 0.2 * 9.81
        sag = f * 90.0 ** 3 / (3 * 1900.0 * (10 * 4 ** 3 / 12))
        check("modulus recovered from a sag", abs(calibration.modulus_from_sag(200, sag, 4, 10) - 1900.0) < 1e-6)
        fit = calibration.fit(flat=(200, sag), edge=(1000, 9.81 * 90.0 ** 3 / (3 * 1700.0 * (4 * 10 ** 3 / 12))), upright_break_g=600, flat_break_g=1500)
        check("fit keeps the lower stiffness and the strength ratio", fit["e_mpa"] == 1700 and abs(fit["across_layers_factor"] - 0.4) < 1e-9, fit)
        files = calibration.make(tmp / "bars")
        sizes = {Path(p).name: Path(p).stat().st_size for p in files}
        check("three bar STLs (12 triangles each) and the instructions", all(sizes[n] == 84 + 12 * 50 for n in ("bar_flat.stl", "bar_on_edge.stl", "bar_upright.stl"))
              and sizes["README.md"] > 500, sizes)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    print("\n%d checks, %d failed" % (len(results), results.count(False)))
    sys.exit(1 if False in results else 0)


def _raises(exc, fn):
    try:
        fn()
    except exc:
        return True
    return False


if __name__ == "__main__":
    main()
