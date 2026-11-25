"""Motion checks: will it tip or slide when used (rigid-body simulation in MuJoCo), and does a mechanism collide
through its travel (forward kinematics).

    stability(parts, pushes, friction=0.5)      -> stability.json layout (what requirement stability_min_ratio reads)
    sweep(assembly, joint, values)              -> the overlaps at each joint value; first_collision(...)

MuJoCo (Apache-2.0, google-deepmind/mujoco; the `mujoco-core` package) simulates; the model is checked with MuJoCo's
own compiler through text-to-cad's `cad.mujoco.check`, and mechanisms are posed with `cad.build123d.posed` from
build123d's joints (MIT, https://github.com/earthtojake/text-to-cad).

stability: the thing stands on a floor at its lowest point, as one rigid body made of its parts (each a solid in mm
with its mass in grams; a part collides as its convex hull, which is exactly what decides tipping on a flat floor).
Each push is a steady force at a point; the force at which the thing stops holding still is found by bisection, with
whether it tips or slides. Inputs carry tags like every other number: masses and friction are "assumed" until weighed
or measured, and the report says so. An object that already moves with no push is a problem, not a result.
"""

import json
import math
import os
import shutil
import tempfile
from pathlib import Path

G = 9.81
STEP_S = 0.0005
SETTLE_S, PUSH_S = 0.3, 2.5
TILT_DEG, SLIDE_MM = 2.0, 1.0


def _model(parts, friction, work):
    """MJCF for one free rigid body on a floor. parts: {name: (solid mm, mass g)}. Returns (xml path, z offset mm)."""
    import build123d as bd
    zmin = min(s.bounding_box().min.Z for s, _ in parts.values())
    meshes, geoms = [], []
    for i, (name, (solid, grams)) in enumerate(parts.items()):
        if grams <= 0:
            raise ValueError("part %s needs a mass in grams" % name)
        bd.export_stl(solid, str(work / ("p%d.stl" % i)), tolerance=0.02)
        meshes.append('<mesh name="p%d" file="p%d.stl" scale="0.001 0.001 0.001"/>' % (i, i))
        geoms.append('<geom name="g%d" type="mesh" mesh="p%d" mass="%.9g" friction="%g 0.005 0.0001"/>' % (i, i, grams / 1000.0, friction))
    xml = '''<mujoco model="mechkit_stability">
 <compiler meshdir="." angle="radian"/>
 <option timestep="%g" cone="elliptic" impratio="10" gravity="0 0 -%g"/>
 <default><geom solref="0.004 1" condim="3"/></default>
 <asset>%s</asset>
 <worldbody>
  <geom name="floor" type="plane" size="5 5 0.1" friction="%g 0.005 0.0001"/>
  <body name="thing" pos="0 0 %.9g">
   <freejoint/>
   %s
  </body>
 </worldbody>
</mujoco>
''' % (STEP_S, G, "".join(meshes), friction, -zmin / 1000.0, "\n   ".join(geoms))
    path = work / "stability.xml"
    path.write_text(xml, encoding="utf-8")
    return path


def _trial(mujoco, model, at_local, direction, force):
    """Hold still, then push with a steady force. -> ('holds' | 'tips' | 'slides', tilt deg, slide mm)."""
    import numpy as np
    data = mujoco.MjData(model)
    body = model.body("thing").id
    mujoco.mj_forward(model, data)
    up0 = data.xmat[body].reshape(3, 3)[:, 2].copy()          # as placed, BEFORE settling: falling over while it
    pos0 = data.xpos[body].copy()                              # settles must count as moving
    for _ in range(int(SETTLE_S / STEP_S)):
        mujoco.mj_step(model, data)
    f = np.asarray(direction, dtype=float) * force
    tilt = slide = 0.0
    for i in range(int(PUSH_S / STEP_S)):
        data.qfrc_applied[:] = 0
        point = data.xpos[body] + data.xmat[body].reshape(3, 3) @ at_local
        mujoco.mj_applyFT(model, data, f, np.zeros(3), point, body, data.qfrc_applied)
        mujoco.mj_step(model, data)
        if i % 50 == 0:
            up = data.xmat[body].reshape(3, 3)[:, 2]
            tilt = math.degrees(math.acos(max(-1.0, min(1.0, float(up @ up0)))))
            slide = float(np.linalg.norm((data.xpos[body] - pos0)[:2])) * 1000.0
            if tilt > TILT_DEG:
                return "tips", tilt, slide
    if slide > SLIDE_MM:
        return "slides", tilt, slide
    return "holds", tilt, slide


def stability(parts, pushes, friction=0.5, friction_tag="assumed", mass_tag="assumed"):
    """parts: {name: (solid in mm, mass in g)} as the thing stands (Z up). pushes: [{"action": text, "at": (x, y, z) mm,
    "direction": (dx, dy, dz), "force_n": the force the action really takes}]. Returns the stability report:
    {"worst": {action, force_n, tips_at_n, mode, ratio}, "actions": [...], "inputs": {...}, "problems": [...]}."""
    os.environ.setdefault("DO_NOT_TRACK", "1")
    import mujoco
    import numpy as np
    work = Path(tempfile.mkdtemp(prefix="mechkit_motion_"))
    report = {"simulator": "MuJoCo %s" % mujoco.__version__, "actions": [], "problems": [],
              "inputs": {"mass_g": {"value": round(sum(g for _, g in parts.values()), 2), "tag": mass_tag},
                         "friction": {"value": friction, "tag": friction_tag}}}
    try:
        path = _model(parts, friction, work)
        try:
            import cad.mujoco as cm
            health = cm.check(path)
            report["model_check"] = health.status
            if health.status == "failed":
                report["problems"].append("MuJoCo refused the model: %s" % health.summary[:300])
                return report
        except ImportError:
            report["model_check"] = "not_checked"
        model = mujoco.MjModel.from_xml_path(str(path))
        weight = float(model.body_subtreemass[model.body("thing").id]) * G
        rest, tilt, slide = _trial(mujoco, model, np.zeros(3), (0, 0, 0), 0.0)
        if rest != "holds":
            report["problems"].append("it does not stand still with no push (%s: %.1f deg, %.1f mm)" % (rest, tilt, slide))
            return report
        for p in pushes:
            d = np.asarray(p["direction"], dtype=float)
            d = d / (np.linalg.norm(d) or 1.0)
            at = np.asarray(p["at"], dtype=float) / 1000.0           # the solids' own frame is the body frame (mm -> m)
            hi = max(20.0 * p["force_n"], 10.0 * weight)
            mode, _, _ = _trial(mujoco, model, at, d, hi)
            if mode == "holds":
                row = {"action": p["action"], "force_n": p["force_n"], "tips_at_n": round(hi, 3), "mode": "holds", "at_least": True}
            else:
                lo = 0.0
                for _ in range(14):
                    mid = (lo + hi) / 2
                    m, _, _ = _trial(mujoco, model, at, d, mid)
                    if m == "holds":
                        lo = mid
                    else:
                        hi, mode = mid, m
                row = {"action": p["action"], "force_n": p["force_n"], "tips_at_n": round(hi, 3), "mode": mode, "at_least": False}
            row["ratio"] = round(row["tips_at_n"] / p["force_n"], 3)
            report["actions"].append(row)
        if report["actions"]:
            report["worst"] = min(report["actions"], key=lambda r: r["ratio"])
        return report
    except Exception as e:                                     # a simulation that could not run reports no result
        report["problems"].append("%s: %s" % (type(e).__name__, e))
        return report
    finally:
        shutil.rmtree(work, ignore_errors=True)


def write_report(folder, report):
    """Write stability.json (whole, then swapped in). A report with problems carries no "worst", so the requirement
    check cannot pass on it."""
    folder = Path(folder)
    folder.mkdir(parents=True, exist_ok=True)
    tmp = folder / "stability.json.tmp"
    tmp.write_text(json.dumps(report, indent=1), encoding="utf-8", newline="\n")
    tmp.replace(folder / "stability.json")
    return folder / "stability.json"


def sweep(assembly, joint, values, min_volume=0.5, ignore=()):
    """Pose a build123d assembly (parts joined with build123d joints, each part labelled) at each value of one joint
    and list the overlaps: [{"value", "overlaps": [(a, b, mm3 or None)]}]. mm3 None = the overlap could not be computed
    (count it as a collision). ignore: pairs of labels allowed to overlap, e.g. a pin in its hole."""
    os.environ.setdefault("DO_NOT_TRACK", "1")
    import cad.build123d as cb

    from .kernel.b3d import GeometryCheckError, overlap_volume
    skip = {frozenset(p) for p in ignore}
    out = []
    for v in values:
        posed = cb.posed(assembly, {joint: v})
        leaves = [c for c in posed.children]
        found = []
        for i in range(len(leaves)):
            for j in range(i + 1, len(leaves)):
                a, b = leaves[i], leaves[j]
                if frozenset((a.label, b.label)) in skip:
                    continue
                try:
                    vol = overlap_volume(a, b)
                except GeometryCheckError:
                    found.append((a.label, b.label, None))
                    continue
                if vol > min_volume:
                    found.append((a.label, b.label, round(vol, 2)))
        out.append({"value": v, "overlaps": found})
    return out


def first_collision(rows):
    """The first joint value of a sweep at which anything overlaps, or None."""
    for r in rows:
        if r["overlaps"]:
            return r["value"]
    return None
