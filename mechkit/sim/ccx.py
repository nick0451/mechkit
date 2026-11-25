"""Write a CalculiX input deck for a linear static case, run the solver, read the results. Units: mm, N, MPa.

    case = StaticCase(mesh, material=Material("PETG assumed", e_mpa=2000, nu=0.35))
    case.fix(tri_idx)                              # clamp the nodes of these surface triangles
    case.force(tri_idx, (0, 0, -10))               # total force in N, spread evenly over these triangles
    result = case.run(workdir)                     # needs the CalculiX solver (see find_ccx)
    result["max_displacement_mm"], result["max_von_mises_mpa"], result["reaction_n"]

A force is applied as a uniform traction. On a 6-node triangle the work-equivalent nodal forces of a uniform traction
are: nothing on the 3 corner nodes and one third of the triangle's share on each mid-edge node.
"""

import os
import subprocess
from dataclasses import dataclass
from pathlib import Path

import numpy as np

KIT_ROOT = Path(__file__).resolve().parents[2]
CCX_ENV = "MECHKIT_CCX"
CCX_TIMEOUT_S = 1800


@dataclass
class Material:
    name: str
    e_mpa: float                # Young's modulus
    nu: float                   # Poisson's ratio
    yield_mpa: float = 0.0      # 0 = unknown (no safety factor reported)
    tag: str = "assumed"        # assumed | calibrated


def find_ccx():
    """Path of the CalculiX solver: $MECHKIT_CCX, else the newest ccx*.exe under <mechkit>/tools/ccx. None if absent."""
    env = os.environ.get(CCX_ENV)
    if env and Path(env).is_file():
        return Path(env)
    found = sorted((KIT_ROOT / "tools" / "ccx").rglob("ccx*.exe"), key=lambda p: ("static" in p.name.lower(), p.stat().st_mtime))
    return found[-1] if found else None         # a statically linked build is preferred (it needs no extra DLLs)


class StaticCase:
    def __init__(self, mesh, material, name="case"):
        self.mesh, self.material, self.name = mesh, material, name
        self.fixed = np.array([], dtype=int)            # node ids
        self.loads = {}                                 # node id -> force vector
        self.notes = []

    def fix(self, tri_idx):
        if len(tri_idx) == 0:
            raise ValueError("fix(): the selection is empty")
        self.fixed = np.union1d(self.fixed, self.mesh.nodes_of(tri_idx))
        self.notes.append("fixed %d surface triangles (%.1f mm2)" % (len(tri_idx), self.mesh.area(tri_idx)))

    def force(self, tri_idx, total_n):
        """Spread a total force vector (N) over the triangles as a uniform traction."""
        if len(tri_idx) == 0:
            raise ValueError("force(): the selection is empty")
        total = np.asarray(total_n, dtype=float)
        _, areas = self.mesh.tri_normals_areas()
        area = areas[tri_idx].sum()
        for t in tri_idx:
            share = total * (areas[t] / area) / 3.0
            for node in self.mesh.tris[t, 3:]:          # mid-edge nodes only
                self.loads[int(node)] = self.loads.get(int(node), np.zeros(3)) + share
        self.notes.append("force %s N over %d surface triangles (%.1f mm2)" % (list(np.round(total, 4)), len(tri_idx), area))

    def applied_force(self):
        return np.sum(list(self.loads.values()), axis=0) if self.loads else np.zeros(3)

    # ------------------------------------------------------------------ input deck
    def write(self, workdir):
        """Write <name>.inp into workdir; returns its path."""
        if len(self.fixed) == 0:
            raise ValueError("no support: the part would fly away (call fix())")
        if not self.loads:
            raise ValueError("no load (call force())")
        workdir = Path(workdir)
        workdir.mkdir(parents=True, exist_ok=True)
        m = self.mesh
        lines = ["*HEADING", "mechkit static case: %s (mm, N, MPa)" % self.name, "*NODE, NSET=NALL"]
        lines += ["%d, %.9g, %.9g, %.9g" % (i + 1, *xyz) for i, xyz in enumerate(m.nodes)]
        lines.append("*ELEMENT, TYPE=C3D10, ELSET=EALL")
        lines += ["%d, %s" % (i + 1, ", ".join(str(int(n)) for n in tet)) for i, tet in enumerate(m.tets)]
        lines.append("*NSET, NSET=FIXED")
        fixed = [str(int(n)) for n in self.fixed]
        lines += [", ".join(fixed[i:i + 12]) for i in range(0, len(fixed), 12)]
        lines += ["*MATERIAL, NAME=MAT", "*ELASTIC", "%.9g, %.9g" % (self.material.e_mpa, self.material.nu),
                  "*SOLID SECTION, ELSET=EALL, MATERIAL=MAT", "*STEP", "*STATIC", "*BOUNDARY", "FIXED, 1, 3, 0.0", "*CLOAD"]
        for node in sorted(self.loads):
            for axis in range(3):
                if abs(self.loads[node][axis]) > 0:
                    lines.append("%d, %d, %.9g" % (node, axis + 1, self.loads[node][axis]))
        lines += ["*NODE PRINT, NSET=NALL", "U", "*NODE PRINT, NSET=FIXED, TOTALS=ONLY", "RF", "*EL PRINT, ELSET=EALL", "S",
                  "*NODE FILE", "U", "*EL FILE", "S", "*END STEP", ""]
        path = workdir / (self.name + ".inp")
        path.write_text("\n".join(lines), encoding="ascii")
        return path

    # ------------------------------------------------------------------ run + results
    def _solve(self, ccx, inp, threads):
        env = {**os.environ, "OMP_NUM_THREADS": str(threads), "PATH": str(ccx.parent) + os.pathsep + os.environ.get("PATH", "")}
        dat = inp.parent / (self.name + ".dat")
        dat.unlink(missing_ok=True)                      # never read a result left over from an earlier run
        proc = subprocess.run([str(ccx), "-i", self.name], cwd=str(inp.parent), env=env, capture_output=True, text=True,
                              errors="replace", timeout=CCX_TIMEOUT_S, check=False)
        (inp.parent / (self.name + ".log")).write_text(proc.stdout + proc.stderr, encoding="utf-8")
        if proc.returncode != 0 or not dat.is_file() or "*ERROR" in proc.stdout:
            tail = (proc.stdout + proc.stderr)[-600:]
            raise RuntimeError("CalculiX failed (exit %s); end of its log:\n%s" % (proc.returncode, tail))
        return read_dat(dat)

    def run(self, workdir, threads=1, verify=True):
        """Solve and read the results.

        verify=True solves twice and requires the same answer. Reason (seen 2026-11-23 with ccx 2.24 for Windows,
        4 threads): one run in about a dozen returned a different, wrong answer for an identical input deck. One
        thread is the default for the same reason; these models solve in seconds either way.
        """
        ccx = find_ccx()
        if ccx is None:
            raise FileNotFoundError("CalculiX solver not found: set %s or put ccx*.exe under %s" % (CCX_ENV, KIT_ROOT / "tools" / "ccx"))
        inp = self.write(workdir)
        result = self._solve(ccx, inp, threads)
        result["repeat_check"] = "not run"
        if verify:
            def key(r):
                return (r["max_displacement_mm"], r["max_von_mises_mpa"])

            def same(a, b):
                return all(abs(x - y) <= 1e-6 * max(abs(x), abs(y), 1e-12) for x, y in zip(key(a), key(b), strict=True))
            second = self._solve(ccx, inp, threads)
            if same(result, second):
                result["repeat_check"] = "two runs agree"
            else:
                third = self._solve(ccx, inp, threads)
                if same(second, third):
                    result = third
                elif not same(result, third):
                    raise RuntimeError("CalculiX gave three different answers for %s: %s, %s, %s" % (self.name, key(result), key(second), key(third)))
                result["repeat_check"] = "SOLVER DISAGREED WITH ITSELF once (answers %s vs %s); the answer two of three runs gave was kept" % (
                    key(result), key(second))
        result.update(case=self.name, solver=str(ccx.name), mesh=self.mesh.info, material=vars(self.material), setup=self.notes,
                      applied_force_n=[round(float(x), 6) for x in self.applied_force()])
        if self.material.yield_mpa > 0 and result["max_von_mises_mpa"] > 0:
            result["safety_factor"] = round(self.material.yield_mpa / result["max_von_mises_mpa"], 3)
        return result


def von_mises(s):
    """s: (n, 6) stresses xx, yy, zz, xy, xz, yz -> (n,) von Mises."""
    xx, yy, zz, xy, xz, yz = s.T
    return np.sqrt(0.5 * ((xx - yy) ** 2 + (yy - zz) ** 2 + (zz - xx) ** 2) + 3.0 * (xy ** 2 + xz ** 2 + yz ** 2))


def read_dat(path):
    """Read displacements, total reaction force and integration-point stresses from a CalculiX .dat file."""
    disp, stress, stress_elem, reaction = {}, [], [], None
    block = None
    for line in Path(path).read_text(encoding="utf-8", errors="replace").splitlines():
        text = line.strip()
        if not text:
            continue
        low = text.lower()
        if low.startswith("displacements"):
            block = "u"
            continue
        if low.startswith("stresses"):
            block = "s"
            continue
        if low.startswith("total force"):
            block = "rf"
            continue
        if low.startswith(("forces", "strains", "total ")):
            block = None
            continue
        parts = text.split()
        try:
            values = [float(x) for x in parts]
        except ValueError:
            block = None
            continue
        if block == "u" and len(values) == 4:
            disp[int(values[0])] = values[1:]
        elif block == "s" and len(values) == 8:
            stress.append(values[2:])
            stress_elem.append(int(values[0]))
        elif block == "rf" and len(values) == 3:
            reaction = values
    if not disp:
        raise RuntimeError("no displacements in %s" % path)
    ids = np.array(sorted(disp))
    u = np.array([disp[i] for i in ids])
    mag = np.linalg.norm(u, axis=1)
    worst = int(np.argmax(mag))
    out = {"max_displacement_mm": round(float(mag[worst]), 6), "max_displacement_node": int(ids[worst]),
           "max_displacement_vector_mm": [round(float(x), 6) for x in u[worst]],
           "reaction_n": None if reaction is None else [round(x, 6) for x in reaction],
           "displacements": {"ids": ids, "u": u}}
    if stress:
        vm = von_mises(np.array(stress))
        elem = np.array(stress_elem)
        ids_e = np.unique(elem)
        peak = np.zeros(ids_e.max() + 1)
        np.maximum.at(peak, elem, vm)                    # highest integration-point value in each element
        out["element_von_mises"] = {"ids": ids_e, "vm": peak[ids_e]}
        out["max_von_mises_mpa"] = round(float(vm.max()), 4)
        out["p99_von_mises_mpa"] = round(float(np.percentile(vm, 99)), 4)      # less sensitive to one sharp corner
    else:
        out["max_von_mises_mpa"] = 0.0
    return out
