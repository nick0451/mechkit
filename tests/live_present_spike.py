"""Spike: which Fusion API features does the presentation sender depend on, and do they behave as assumed?

    uv run python tests/live_present_spike.py        (Fusion open, add-in running; opens ONE new unsaved document)

Everything happens in a new, unsaved scratch document (the scope guard always allows those). Nothing is saved.
Each experiment is tried on its own and reported, so one failure does not hide the others. Close the scratch
document without saving afterwards.
"""

import json
import sys
from pathlib import Path

KIT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(KIT))
from mechkit.present import fusion, manifest  # noqa: E402

def _example():
    """The worked example: your own working copy beside the kit if there is one, else the copy in examples/."""
    for p in (KIT.parent / "Monitor weather display", KIT / "examples" / "monitor-weather-display"):
        if (p / "exports").is_dir():
            return p
    return KIT / "examples" / "monitor-weather-display"


MWD = _example()

CODE = r"""
import json, traceback
STEP, STEP2, KIT_VOL = __STEP__, __STEP2__, __VOL__
P3, V3 = adsk.core.Point3D.create, adsk.core.Vector3D.create
out = {}
def trial(name, fn):
    try:
        out[name] = fn()
    except Exception as e:
        out[name] = 'FAILED: %s: %s' % (type(e).__name__, e)

doc = app.documents.add(adsk.core.DocumentTypes.FusionDesignDocumentType)
design = adsk.fusion.Design.cast(doc.products.itemByProductType('DesignProductType'))
root = design.rootComponent
out['document'] = doc.name
trial('orientation', lambda: 'y-up' if app.preferences.generalPreferences.defaultModelingOrientation ==
      adsk.core.DefaultModelingOrientations.YUpModelingOrientation else 'z-up')
def direct():
    design.designType = adsk.fusion.DesignTypes.DirectDesignType
    return design.designType == adsk.fusion.DesignTypes.DirectDesignType
trial('direct_mode', direct)
grp = {}
def make_group():
    o = root.occurrences.addNewComponent(adsk.core.Matrix3D.create())
    o.component.name = 'Assembled'
    grp['occ'] = o
    return o.component.name
trial('group', make_group)
imp = {}
def do_import():
    g = grp['occ'].component
    before = g.occurrences.count
    opts = app.importManager.createSTEPImportOptions(STEP)
    opts.isViewFit = False
    r = app.importManager.importToTarget(opts, g)
    new = [g.occurrences.item(i) for i in range(before, g.occurrences.count)]
    imp['occ'] = new[0] if new else None
    res = {'returned': bool(r), 'new_occurrences': len(new), 'bodies_in_group_itself': g.bRepBodies.count}
    if new:
        c = new[0].component
        bodies = [c.bRepBodies.item(i) for i in range(c.bRepBodies.count)]
        t = new[0].transform2.translation
        res.update(component_name=c.name, bodies=len(bodies), nested=c.occurrences.count,
                   body_names=[b.name for b in bodies], volume_mm3=round(sum(b.volume for b in bodies) * 1000, 2),
                   kit_volume_mm3=KIT_VOL, translation_mm=[round(t.x * 10, 4), round(t.y * 10, 4), round(t.z * 10, 4)])
        if bodies:
            bb = bodies[0].boundingBox
            res['bbox_mm'] = [[round(bb.minPoint.x * 10, 3), round(bb.minPoint.y * 10, 3), round(bb.minPoint.z * 10, 3)],
                              [round(bb.maxPoint.x * 10, 3), round(bb.maxPoint.y * 10, 3), round(bb.maxPoint.z * 10, 3)]]
    return res
trial('import_step', do_import)
def second_import():
    g = grp['occ'].component
    before = g.occurrences.count
    opts = app.importManager.createSTEPImportOptions(STEP2)
    opts.isViewFit = False
    app.importManager.importToTarget(opts, g)
    return {'new_occurrences': g.occurrences.count - before}
trial('import_second', second_import)
def props():
    c = imp['occ'].component
    c.name = 'Pod (renamed)'
    c.description = 'A description with punctuation: 4.0 mm; "quoted".'
    c.partNumber = 'MWD-P2'
    return {'name': c.name, 'description': c.description, 'part_number': c.partNumber}
trial('component_properties', props)
def libs():
    return [app.materialLibraries.item(i).name for i in range(app.materialLibraries.count)]
trial('libraries', libs)
def appearance():
    lib = app.materialLibraries.itemByName('Fusion Appearance Library') or app.materialLibraries.itemByName('Fusion 360 Appearance Library')
    base = lib.appearances.itemByName('Plastic - Matte (Yellow)')
    res = {'library': lib.name, 'base_found': base is not None}
    base = base or lib.appearances.item(0)
    ap = design.appearances.addByCopy(base, 'kit #b0343a')
    prop = adsk.core.ColorProperty.cast(ap.appearanceProperties.itemByName('Color'))
    res['color_property'] = prop is not None
    if prop:
        prop.value = adsk.core.Color.create(0xb0, 0x34, 0x3a, 255)
    else:
        res['properties'] = [ap.appearanceProperties.item(i).name for i in range(ap.appearanceProperties.count)]
    b = imp['occ'].component.bRepBodies.item(0)
    b.appearance = ap
    res['applied'] = b.appearance.name
    return res
trial('appearance', appearance)
def materials():
    lib = app.materialLibraries.itemByName('Fusion Material Library') or app.materialLibraries.itemByName('Fusion 360 Material Library')
    found = {n: lib.materials.itemByName(n) is not None for n in ('PETG', 'PET Plastic', 'Plastic', 'Brass', 'Steel', 'ABS Plastic')}
    plastics = [lib.materials.item(i).name for i in range(lib.materials.count) if 'PET' in lib.materials.item(i).name.upper()]
    first = [n for n in ('PETG', 'PET Plastic', 'ABS Plastic') if found[n]]
    setres = None
    if first:
        imp['occ'].component.material = lib.materials.itemByName(first[0])
        setres = imp['occ'].component.material.name
    return {'library': lib.name, 'found': found, 'names_with_PET': plastics, 'set_on_component': setres}
trial('material', materials)
def opacity():
    b = imp['occ'].component.bRepBodies.item(0)
    b.opacity = 0.25
    v = b.opacity
    b.opacity = 1.0
    return round(v, 3)
trial('opacity', opacity)
def second_group():
    m = adsk.core.Matrix3D.create()
    m.setWithArray([-1, 0, 0, 20.0,   0, 0, 1, 0,   0, 1, 0, 0,   0, 0, 0, 1])
    o = root.occurrences.addNewComponent(m)
    o.component.name = 'Exploded'
    grp['ex'] = o
    t = adsk.core.Matrix3D.create()
    t.translation = V3(0, 3.0, 0.5)
    c = o.component.occurrences.addExistingComponent(imp['occ'].component, t)
    tr = c.transform2.translation
    bb = c.boundingBox
    return {'child_translation_mm': [round(tr.x * 10, 3), round(tr.y * 10, 3), round(tr.z * 10, 3)],
            'group_translation_mm': round(o.transform2.translation.x * 10, 3),
            'child_box_min_mm': [round(bb.minPoint.x * 10, 2), round(bb.minPoint.y * 10, 2), round(bb.minPoint.z * 10, 2)]}
trial('turned_group_with_moved_copy', second_group)
def trace():
    ec = grp['ex'].component
    sk = ec.sketches.add(ec.xYConstructionPlane)
    a, b = P3(0, 0, 0), P3(1.0, 3.0, 2.0)
    ln = sk.sketchCurves.sketchLines.addByTwoPoints(sk.modelToSketchSpace(a), sk.modelToSketchSpace(b))
    e = ln.endSketchPoint.worldGeometry
    return {'end_world_mm': [round(e.x * 10, 3), round(e.y * 10, 3), round(e.z * 10, 3)], 'is_3d': abs(ln.endSketchPoint.geometry.z) > 1e-6}
trial('trace_line_3d', trace)
lab = {}
def label_plane():
    ec = grp['ex'].component
    u, v = V3(0.6, 0.8, 0.0), V3(0.0, 0.0, 1.0)
    plane = adsk.core.Plane.createUsingDirections(P3(1.0, 2.0, 3.0), u, v)
    pin = ec.constructionPlanes.createInput()
    pin.setByPlane(plane)
    cp = ec.constructionPlanes.add(pin)
    sk = ec.sketches.add(cp)
    lab['sk'] = sk
    return {'sketch_x': [round(c, 3) for c in (sk.xDirection.x, sk.xDirection.y, sk.xDirection.z)],
            'sketch_y': [round(c, 3) for c in (sk.yDirection.x, sk.yDirection.y, sk.yDirection.z)],
            'wanted_x': [0.6, 0.8, 0.0], 'wanted_y': [0.0, 0.0, 1.0],
            'origin_mm': [round(sk.origin.x * 10, 2), round(sk.origin.y * 10, 2), round(sk.origin.z * 10, 2)]}
trial('label_plane', label_plane)
def text():
    sk = lab['sk']
    sk.sketchCurves.sketchCircles.addByCenterRadius(P3(0, 0, 0), 0.5)
    tin = sk.sketchTexts.createInput2('12', 0.5)
    tin.setAsMultiLine(P3(-0.5, -0.5, 0), P3(0.5, 0.5, 0), adsk.core.HorizontalAlignments.CenterHorizontalAlignment,
                       adsk.core.VerticalAlignments.MiddleVerticalAlignment, 0)
    t = sk.sketchTexts.add(tin)
    return {'text': t.text, 'height_mm': round(t.height * 10, 2), 'input_attributes': [a for a in dir(tin) if not a.startswith('_')]}
trial('sketch_text', text)
def views():
    vp = app.activeViewport
    cam = vp.camera
    res = {'camera_attributes': [a for a in dir(cam) if not a.startswith('_')]}
    cam.isSmoothTransition = False
    cam.isFitView = False
    cam.cameraType = adsk.core.CameraTypes.OrthographicCameraType
    cam.eye = P3(30, 20, 15)
    cam.target = P3(0, 0, 0)
    cam.upVector = V3(0, 1, 0)
    try:
        cam.setExtents(20.0, 20.0)
        res['setExtents'] = True
    except Exception as e:
        res['setExtents'] = 'FAILED: %s' % e
    vp.camera = cam
    vp.refresh()
    adsk.doEvents()
    nv = design.namedViews.add(vp.camera, 'Spike view')
    res['named_views'] = [design.namedViews.item(i).name for i in range(design.namedViews.count)]
    res['has_itemByName'] = design.namedViews.itemByName('Spike view') is not None
    c2 = nv.camera
    res['stored_eye_mm'] = [round(c2.eye.x * 10, 1), round(c2.eye.y * 10, 1), round(c2.eye.z * 10, 1)]
    res['stored_type_is_ortho'] = c2.cameraType == adsk.core.CameraTypes.OrthographicCameraType
    nv.deleteMe()
    res['after_delete'] = design.namedViews.count
    return res
trial('named_views', views)
def limits():
    lim = app.data.personalUseLimits
    return [lim.editableFileCount, lim.maxEditableFileCount] if lim else None
trial('editable_documents', limits)
def hub():
    h = app.data.activeHub
    return {'hub': h.name, 'projects': [p.name for p in h.dataProjects]}
trial('cloud', hub)
mcp_result = out
"""


def main():
    data = manifest.load(manifest.find(MWD))
    folder = Path(data["folder"])
    pod = [e for e in data["parts"] if e["key"] == "Pod"][0]
    code = (CODE.replace("__STEP__", repr(str(folder / "Pod.step").replace("\\", "/")))
            .replace("__STEP2__", repr(str(folder / "Bolt_M3x10_cap.step").replace("\\", "/"))).replace("__VOL__", repr(pod["volume_mm3"])))
    fc = fusion._client()
    print("add-in:", fc.health())
    fc.run(code, "Presentation spike (scratch document)", exit_on_error=False, rollback_on_error=False)
    res = fc.last_result
    if not res or not res.get("ok"):
        sys.exit("spike script failed: %s" % ((res or {}).get("error") or "no result"))
    out = KIT / "work" / "present_spike.json"
    out.parent.mkdir(exist_ok=True)
    out.write_text(json.dumps(res["value"], indent=1), encoding="utf-8")
    print(json.dumps(res["value"], indent=1))
    print("\nkit bbox of Pod:", pod["bbox"])
    print("written", out, "\nClose the scratch document in Fusion WITHOUT saving.")


if __name__ == "__main__":
    main()
