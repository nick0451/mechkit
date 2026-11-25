"""Send a presentation manifest to Fusion: one document `<Project>_Presentation`, rebuilt from scratch every time.

    from mechkit.present import manifest, fusion
    report = fusion.send(manifest.load(path), shots_dir)        # needs Fusion open with the add-in running

What it builds (direct-modelling document, no timeline):
    Assembled   every item as its own component: name, description, part number, material, colour
    Exploded    the same components again, moved apart, standing beside the assembled group; trace lines; numbered labels
    named views one per manifest view

Frames: the kit's world is Z-up with the front toward +Y. The two groups carry the turn into Fusion's frame (front
toward the "Front" view, right way up for the document's own up axis), so the parts inside them keep kit coordinates.

Nothing is read back into the design. The document is a throwaway picture of the kit's output: never edit it by hand.
OPTIONAL and experimental: needs the client of a separate Fusion add-in (`fusion_client.py`, not part of MechKit),
found through MECHKIT_FUSION_CLIENT, as `mechkit/fusion_export.py` does.
"""

import json
import os
import sys
from pathlib import Path

from . import layout

KIT_ROOT = Path(__file__).resolve().parents[2]
FUSION_CLIENT_ENV = "MECHKIT_FUSION_CLIENT"       # folder that holds fusion_client.py (the Fusion add-in's client: NOT part of this kit)
FUSION_TOOLS = Path(os.environ[FUSION_CLIENT_ENV]) if os.environ.get(FUSION_CLIENT_ENV) else KIT_ROOT.parent / "Fusion Designs"
MARK = ("mechkit", "presentation")          # attribute on the root component: which project this document presents
LABEL_R, LABEL_REACH, LABEL_TEXT_H = 5.0, 30.0, 5.0      # mm


def _client():
    """The Fusion add-in's Python client. It is not part of this kit: this bridge is optional and experimental."""
    if not (FUSION_TOOLS / "fusion_client.py").is_file():
        raise RuntimeError("the Fusion bridge needs fusion_client.py (the client of a separate Fusion add-in, not included with "
                           "MechKit). Looked in %s; set %s to the folder that holds it." % (FUSION_TOOLS, FUSION_CLIENT_ENV))
    if str(FUSION_TOOLS) not in sys.path:
        sys.path.insert(0, str(FUSION_TOOLS))
    import fusion_client
    return fusion_client


# ------------------------------------------------------------------------------------------------ scripts run inside Fusion
COMMON = r"""
import json, math
DATA = json.loads(__DATA__)
DOC, PROJECT = DATA['document'], DATA['project']
P3, V3 = adsk.core.Point3D.create, adsk.core.Vector3D.create

def the_design():
    doc = app.activeDocument
    design = adsk.fusion.Design.cast(doc.products.itemByProductType('DesignProductType'))
    a = design.rootComponent.attributes.itemByName('mechkit', 'presentation')
    if a is None or a.value != PROJECT:
        raise RuntimeError('active document %r is not the presentation of %r: nothing was changed' % (doc.name, PROJECT))
    return doc, design

def group(root, name):
    for i in range(root.occurrences.count):
        o = root.occurrences.item(i)
        if o.component.name == name:
            return o
    return None

def frame(design):
    a = design.rootComponent.attributes.itemByName('mechkit', 'up')
    return a.value if a else 'y'

def to_fusion(v, up):
    # kit (x right-to-left seen from the front, y toward the user, z up) -> Fusion frame, in the same units
    return (-v[0], v[2], v[1]) if up == 'y' else (-v[0], -v[1], v[2])

def group_matrix(up, offset_mm):
    m = adsk.core.Matrix3D.create()
    o = to_fusion(offset_mm, up)
    if up == 'y':
        cells = [-1, 0, 0, o[0] * 0.1,   0, 0, 1, o[1] * 0.1,   0, 1, 0, o[2] * 0.1,   0, 0, 0, 1]
    else:
        cells = [-1, 0, 0, o[0] * 0.1,   0, -1, 0, o[1] * 0.1,   0, 0, 1, o[2] * 0.1,   0, 0, 0, 1]
    m.setWithArray(cells)
    return m

def all_bodies(comp, out=None):
    out = [] if out is None else out
    for i in range(comp.bRepBodies.count):
        out.append(comp.bRepBodies.item(i))
    for i in range(comp.occurrences.count):
        all_bodies(comp.occurrences.item(i).component, out)
    return out
"""

PREPARE = COMMON + r"""
# find the presentation document (open tab, else cloud file, else a new one), make it the active tab and empty it
state, doc = None, None
for d in app.documents:
    if d.isSaved and d.dataFile.name == DOC:
        doc, state = d, 'open'
if doc is None:
    parts = DATA['cloud_folder'].split('/')
    proj = [p for p in app.data.activeHub.dataProjects if p.name == parts[0]]
    folder = proj[0].rootFolder if proj else None
    for name in parts[1:]:
        folder = folder.dataFolders.itemByName(name) if folder else None
    if folder:
        files = folder.dataFiles
        for i in range(files.count):
            if files.item(i).name == DOC:
                doc, state = app.documents.open(files.item(i), True), 'reopened'
if doc is None:
    doc, state = app.documents.add(adsk.core.DocumentTypes.FusionDesignDocumentType), 'new'
if app.activeDocument != doc:
    doc.activate()
design = adsk.fusion.Design.cast(doc.products.itemByProductType('DesignProductType'))
root = design.rootComponent
if state != 'new':
    a = root.attributes.itemByName('mechkit', 'presentation')
    if a is None or a.value != PROJECT:
        raise RuntimeError('%r exists but was not made by the kit for %r: refusing to empty it' % (DOC, PROJECT))
    if doc.dataFile.isReadOnly:
        raise RuntimeError('%r is read-only: make it editable in the Data Panel first' % DOC)
if design.designType != adsk.fusion.DesignTypes.DirectDesignType:
    design.designType = adsk.fusion.DesignTypes.DirectDesignType
for i in range(root.occurrences.count - 1, -1, -1):
    root.occurrences.item(i).deleteMe()
for coll in (root.sketches, root.constructionPlanes):
    for i in range(coll.count - 1, -1, -1):
        try:
            coll.item(i).deleteMe()
        except Exception:
            pass
nv = design.namedViews
for i in range(nv.count - 1, -1, -1):
    try:
        nv.item(i).deleteMe()
    except Exception:
        pass
root.attributes.add('mechkit', 'presentation', PROJECT)
if root.attributes.itemByName('mechkit', 'up') is None:
    yup = app.preferences.generalPreferences.defaultModelingOrientation == adsk.core.DefaultModelingOrientations.YUpModelingOrientation
    root.attributes.add('mechkit', 'up', 'y' if yup else 'z')
mcp_result = {'state': state, 'document': doc.name, 'up': frame(design), 'saved': bool(doc.isSaved)}
"""

IMPORT = COMMON + r"""
doc, design = the_design()
root, up = design.rootComponent, frame(design)
asm = root.occurrences.addNewComponent(adsk.core.Matrix3D.create())      # turned at the very end (see EXPLODE)
asm.component.name = 'Assembled'
asm.component.description = '%s %s as assembled. Built by the kit: do not edit, rebuild.' % (PROJECT, DATA['version'])

def library(names):
    for n in names:
        lib = app.materialLibraries.itemByName(n)
        if lib:
            return lib
    return None
ap_lib = library(['Fusion Appearance Library', 'Fusion 360 Appearance Library'])
mat_lib = library(['Fusion Material Library', 'Fusion 360 Material Library'])
MATERIALS = {'PETG': ['PETG', 'PET Plastic', 'Plastic'], 'Brass': ['Brass'], 'Steel': ['Steel']}
notes, colours = [], {}

def colour(hexc):
    if hexc in colours:
        return colours[hexc]
    ap = design.appearances.itemByName('kit ' + hexc)
    if ap is None and ap_lib:
        base = ap_lib.appearances.itemByName('Plastic - Matte (Yellow)') or ap_lib.appearances.item(0)
        ap = design.appearances.addByCopy(base, 'kit ' + hexc)
        prop = adsk.core.ColorProperty.cast(ap.appearanceProperties.itemByName('Color'))
        if prop:
            prop.value = adsk.core.Color.create(int(hexc[1:3], 16), int(hexc[3:5], 16), int(hexc[5:7], 16), 255)
        else:
            notes.append('appearance has no Color property; %s left as the library default' % hexc)
    colours[hexc] = ap
    return ap

def material(name):
    if not name or not mat_lib:
        return None
    for n in MATERIALS.get(name, [name]):
        m = mat_lib.materials.itemByName(n)
        if m:
            return m
    notes.append('no library material for %r' % name)
    return None

im = app.importManager
made = []
for e in DATA['parts']:
    before = asm.component.occurrences.count
    opts = im.createSTEPImportOptions(DATA['folder'].replace('\\', '/') + '/' + e['step'])
    opts.isViewFit = False
    im.importToTarget(opts, asm.component)
    new = [asm.component.occurrences.item(i) for i in range(before, asm.component.occurrences.count)]
    if len(new) != 1:
        raise RuntimeError('%s: the import made %d components, expected 1' % (e['key'], len(new)))
    occ = new[0]
    comp = occ.component
    comp.name = e['name']
    comp.description = e['description']
    comp.partNumber = e['part_number'] or e['key']
    occ.attributes.add('mechkit', 'key', e['key'])
    if comp.occurrences.count:                       # the STEP came in wrapped in a child component: lift its bodies up
        try:
            for b in [x for x in all_bodies(comp) if x.parentComponent != comp]:
                b.moveToComponent(occ)
            for i in range(comp.occurrences.count - 1, -1, -1):
                comp.occurrences.item(i).deleteMe()
        except Exception as ex:
            notes.append('%s: left nested as imported (%s)' % (e['key'], ex))
    bodies = all_bodies(comp)
    ap, mat = colour(e['colour']), material(e['material'])
    if mat:
        try:
            comp.material = mat
        except Exception as ex:
            notes.append('%s: material not set (%s)' % (e['key'], ex))
    for n, b in enumerate(bodies):
        b.name = e['key'] if len(bodies) == 1 else '%s_%d' % (e['key'], n + 1)
        if ap:
            b.appearance = ap
        if e.get('opacity', 1.0) < 1.0:
            b.opacity = e['opacity']
    t = occ.transform2.translation
    lo = [min(getattr(b.boundingBox.minPoint, a) for b in bodies) * 10 for a in 'xyz'] if bodies else [0, 0, 0]
    hi = [max(getattr(b.boundingBox.maxPoint, a) for b in bodies) * 10 for a in 'xyz'] if bodies else [0, 0, 0]
    made.append({'key': e['key'], 'bodies': len(bodies), 'volume_mm3': round(sum(b.volume for b in bodies) * 1000, 2),
                 'moved_mm': round(max(abs(t.x), abs(t.y), abs(t.z)) * 10, 4), 'nested': comp.occurrences.count,
                 'bbox': [[round(c, 3) for c in lo], [round(c, 3) for c in hi]]})
mcp_result = {'made': made, 'notes': sorted(set(notes)), 'up': up}
"""

EXPLODE = COMMON + r"""
doc, design = the_design()
root, up = design.rootComponent, frame(design)
asm = group(root, 'Assembled')
# Seen live (2026-11-25): inside a group that is already turned or moved, Fusion applies the group's own transform to
# what is added (a copy's position, a construction plane). So both groups are filled while they still sit unturned at
# the origin, and are turned and moved as the last step.
ex = root.occurrences.addNewComponent(adsk.core.Matrix3D.create())
ex.component.name = 'Exploded'
ex.component.description = '%s %s taken apart. The numbers match the parts table. Built by the kit: do not edit, rebuild.' % (PROJECT, DATA['version'])
by_key = {}
for i in range(asm.component.occurrences.count):
    o = asm.component.occurrences.item(i)
    a = o.attributes.itemByName('mechkit', 'key')
    if a:
        by_key[a.value] = o.component
placed = 0
for e in DATA['parts']:
    if e['kind'] == 'reference':
        continue
    m = adsk.core.Matrix3D.create()
    d = e['explode']
    m.translation = V3(d[0] * 0.1, d[1] * 0.1, d[2] * 0.1)
    o = ex.component.occurrences.addExistingComponent(by_key[e['key']], m)
    o.attributes.add('mechkit', 'key', e['key'])
    placed += 1
ec = ex.component
# trace lines: from where each part seats to where it is shown
sk = ec.sketches.add(ec.xYConstructionPlane)
sk.name = 'Trace_Lines'
lines = sk.sketchCurves.sketchLines
traces = 0
for e in DATA['parts']:
    d = e['explode']
    if e['kind'] == 'reference' or not any(d):
        continue
    c = e['centre']
    lines.addByTwoPoints(sk.modelToSketchSpace(P3(c[0] * 0.1, c[1] * 0.1, c[2] * 0.1)),
                         sk.modelToSketchSpace(P3((c[0] + d[0]) * 0.1, (c[1] + d[1]) * 0.1, (c[2] + d[2]) * 0.1)))
    traces += 1
# labels: a flat sheet square to the 'Exploded' view, in front of the parts; leaders run back to each part
L = DATA['labels']
labels, label_note = 0, ''
if L:
    try:
        o, u, v = L['origin'], L['right'], L['up']
        # Seen live (2026-11-25): setByPlane reads the plane in ROOT space even inside a moved component, while the
        # sketch on it reports its axes in the component's own space. So try the root-space form first, check what
        # came out, and fall back to the component-space form.
        gm = ex.transform2
        def attempt(in_root):
            po, pu, pv = P3(o[0] * 0.1, o[1] * 0.1, o[2] * 0.1), V3(*u), V3(*v)
            if in_root:
                po.transformBy(gm); pu.transformBy(gm); pv.transformBy(gm)
            pin = ec.constructionPlanes.createInput()
            pin.setByPlane(adsk.core.Plane.createUsingDirections(po, pu, pv))
            cp = ec.constructionPlanes.add(pin)
            sk2 = ec.sketches.add(cp)
            sx, sy, so = sk2.xDirection, sk2.yDirection, sk2.origin
            ax = (sx.x * u[0] + sx.y * u[1] + sx.z * u[2], sx.x * v[0] + sx.y * v[1] + sx.z * v[2])
            ay = (sy.x * u[0] + sy.y * u[1] + sy.z * u[2], sy.x * v[0] + sy.y * v[1] + sy.z * v[2])
            nrm = (u[1] * v[2] - u[2] * v[1], u[2] * v[0] - u[0] * v[2], u[0] * v[1] - u[1] * v[0])
            off = abs((so.x * 10 - o[0]) * nrm[0] + (so.y * 10 - o[1]) * nrm[1] + (so.z * 10 - o[2]) * nrm[2])
            return cp, sk2, ax, ay, (ax[0] > 0.99 and ay[1] > 0.99 and off < 0.01)
        cp, ls, ax, ay, upright = attempt(True)
        if not upright:
            ls.deleteMe(); cp.deleteMe()
            cp, ls, ax, ay, upright = attempt(False)
        cp.name = 'Label_Plane'
        cp.isLightBulbOn = False
        ls.name = 'Labels'
        def on_plane(x, y):
            return P3((o[0] + u[0] * x + v[0] * y) * 0.1, (o[1] + u[1] * x + v[1] * y) * 0.1, (o[2] + u[2] * x + v[2] * y) * 0.1)
        r, h = L['r'], L['text_h']
        for b in L['balloons']:
            centre = ls.modelToSketchSpace(on_plane(b['x'], b['y']))
            ls.sketchCurves.sketchCircles.addByCenterRadius(centre, r * 0.1)
            a = b['anchor']
            ls.sketchCurves.sketchLines.addByTwoPoints(ls.modelToSketchSpace(on_plane(b['edge_x'], b['edge_y'])),
                                                       ls.modelToSketchSpace(P3(a[0] * 0.1, a[1] * 0.1, a[2] * 0.1)))
            if upright:
                tin = ls.sketchTexts.createInput2(str(b['label']), h * 0.1)
                tin.setAsMultiLine(P3(centre.x - r * 0.1, centre.y - r * 0.1, 0), P3(centre.x + r * 0.1, centre.y + r * 0.1, 0),
                                   adsk.core.HorizontalAlignments.CenterHorizontalAlignment, adsk.core.VerticalAlignments.MiddleVerticalAlignment, 0)
                ls.sketchTexts.add(tin)
            labels += 1
        if not upright:
            label_note = 'label sketch came out turned (x %s, y %s): balloons and leaders drawn, numbers left out' % (
                [round(c, 2) for c in ax], [round(c, 2) for c in ay])
    except Exception as exn:
        label_note = 'labels not drawn: %s' % exn
asm.transform2 = group_matrix(up, [0, 0, 0])
ex.transform2 = group_matrix(up, DATA['exploded_offset'])
mcp_result = {'placed': placed, 'traces': traces, 'labels': labels, 'label_note': label_note}
"""

VIEWS = COMMON + r"""
doc, design = the_design()
up = frame(design)
vp = app.activeViewport
made, notes = [], []
ORTHO = adsk.core.CameraTypes.OrthographicCameraType
for v in DATA['views']:
    for i in range(design.namedViews.count - 1, -1, -1):        # (itemByName raises when there is no such view)
        if design.namedViews.item(i).name == v['name']:
            design.namedViews.item(i).deleteMe()
    off = DATA['exploded_offset'] if v['group'] == 'exploded' else [0, 0, 0]
    eye = to_fusion([v['from'][i] + off[i] for i in range(3)], up)      # same direction as the manifest's view, aimed at the group's middle
    tgt = to_fusion([v['centre'][i] + off[i] for i in range(3)], up)
    upv = to_fusion(v['up'], up)
    # Seen live: a perspective camera keeps the previous zoom and moves the eye instead, and setExtents only sticks once
    # the viewport itself is orthographic. So: no perspective, and the picture size is set in a second step.
    cam = vp.camera
    cam.isSmoothTransition = False
    cam.isFitView = False
    cam.cameraType = ORTHO
    cam.eye = P3(eye[0] * 0.1, eye[1] * 0.1, eye[2] * 0.1)
    cam.target = P3(tgt[0] * 0.1, tgt[1] * 0.1, tgt[2] * 0.1)
    cam.upVector = V3(*upv)
    vp.camera = cam
    adsk.doEvents()
    cam = vp.camera
    cam.isSmoothTransition = False
    cam.isFitView = False
    cam.setExtents(v['extent'] * 0.1, v['extent'] * 0.1)
    vp.camera = cam
    vp.refresh()
    adsk.doEvents()
    got = vp.camera.getExtents()
    if abs(got[1] - v['extent'] * 0.1) > 0.05 * v['extent'] * 0.1 and abs(got[2] - v['extent'] * 0.1) > 0.05 * v['extent'] * 0.1:
        notes.append('%s: picture size came out %.0f x %.0f mm, asked for %.0f' % (v['name'], got[1] * 10, got[2] * 10, v['extent']))
    design.namedViews.add(vp.camera, v['name'])
    made.append(v['name'])
mcp_result = {'views': made, 'notes': notes}
"""

SAVE = COMMON + r"""
doc, design = the_design()
desc = '%s %s presentation, built by mechkit. Do not edit: rebuild with `mechkit present`.' % (PROJECT, DATA['version'])
if doc.isSaved:
    ok, how = doc.save(desc), 'new version'
else:
    parts = DATA['cloud_folder'].split('/')
    proj = [p for p in app.data.activeHub.dataProjects if p.name == parts[0]]
    if not proj:
        raise RuntimeError('cloud project not found in the active hub: ' + parts[0])
    folder = proj[0].rootFolder
    for name in parts[1:]:
        nxt = folder.dataFolders.itemByName(name)
        folder = nxt if nxt else folder.dataFolders.add(name)
    files = folder.dataFiles
    if any(files.item(i).name == DOC for i in range(files.count)):
        raise RuntimeError('%r already exists in %s but is not open: open it and run again' % (DOC, DATA['cloud_folder']))
    ok, how = doc.saveAs(DOC, folder, desc, ''), 'first save'
lim = app.data.personalUseLimits
mcp_result = {'saved': bool(ok), 'how': how, 'editable': [lim.editableFileCount, lim.maxEditableFileCount] if lim else None}
"""

VERIFY = COMMON + r"""
doc, design = the_design()
root = design.rootComponent
out = {'document': doc.name, 'direct': design.designType == adsk.fusion.DesignTypes.DirectDesignType, 'groups': {}, 'up': frame(design),
       'views': [design.namedViews.item(i).name for i in range(design.namedViews.count)]}
for gname in ('Assembled', 'Exploded'):
    g = group(root, gname)
    items = {}
    if g:
        for i in range(g.component.occurrences.count):
            o = g.component.occurrences.item(i)
            a = o.attributes.itemByName('mechkit', 'key')
            c = o.component
            bodies = all_bodies(c)
            bb = g.childOccurrences.item(i).boundingBox          # through the group: where it really sits in the document
            items[a.value if a else c.name] = {'name': c.name, 'description': c.description, 'part_number': c.partNumber,
                                               'volume_mm3': round(sum(b.volume for b in bodies) * 1000, 2), 'solid': all(b.isSolid for b in bodies),
                                               'box': [[round(bb.minPoint.x * 10, 3), round(bb.minPoint.y * 10, 3), round(bb.minPoint.z * 10, 3)],
                                                       [round(bb.maxPoint.x * 10, 3), round(bb.maxPoint.y * 10, 3), round(bb.maxPoint.z * 10, 3)]]}
    out['groups'][gname] = items
mcp_result = out
"""


# ------------------------------------------------------------------------------------------------ kit side
def label_layout(data):
    """Where the numbered balloons go: on a flat sheet square to the first exploded view, in front of the parts.

    Returned (kit frame of the exploded group, mm): origin / right / up of the sheet, and per balloon its centre (x, y) on
    the sheet, the point on its rim where the leader starts, the part's centre (anchor) and its number.
    """
    views = [v for v in data["views"] if v["group"] == "exploded"]
    shown = [e for e in data["parts"] if e["kind"] != "reference" and e["count"] > 0]
    if not views or not shown:
        return None
    view = views[0]
    right, up, toward = layout.camera_basis(view["eye"], view["target"], view["up"])
    anchors = [[e["centre"][i] + e["explode"][i] for i in range(3)] for e in shown]
    box = data["exploded_bbox"]
    corners = [[box[a][0], box[b][1], box[c][2]] for a in (0, 1) for b in (0, 1) for c in (0, 1)]
    near = max(sum(c[i] * toward[i] for i in range(3)) for c in corners) + 15.0      # sheet 15 mm in front of the nearest part
    centre = [(box[0][i] + box[1][i]) / 2 for i in range(3)]
    depth = sum(centre[i] * toward[i] for i in range(3))
    origin = [centre[i] + toward[i] * (near - depth) for i in range(3)]
    pts = [layout.project(a, origin, right, up) for a in anchors]
    spots = layout.place_balloons(pts, LABEL_R, LABEL_REACH)
    balloons = []
    for e, a, p, s in zip(shown, anchors, pts, spots):
        dx, dy = p[0] - s[0], p[1] - s[1]
        n = (dx * dx + dy * dy) ** 0.5 or 1.0
        balloons.append({"label": e["label"], "key": e["key"], "x": round(s[0], 3), "y": round(s[1], 3),
                         "edge_x": round(s[0] + dx / n * LABEL_R, 3), "edge_y": round(s[1] + dy / n * LABEL_R, 3), "anchor": [round(c, 3) for c in a]})
    return {"origin": origin, "right": right, "up": up, "r": LABEL_R, "text_h": LABEL_TEXT_H, "balloons": balloons, "view": view["name"]}


def view_extents(data):
    """Give every view the middle of its group (`centre`) and the width of its picture in mm (`extent`): the group's size
    seen from that side, plus room for the balloons on exploded views. Views are drawn without perspective."""
    for v in data["views"]:
        exploded = v["group"] == "exploded"
        box = data["exploded_bbox"] if exploded else data["assembled_bbox"]
        corners = [[box[a][0], box[b][1], box[c][2]] for a in (0, 1) for b in (0, 1) for c in (0, 1)]
        right, up, _ = layout.camera_basis(v["eye"], v["target"], v["up"])
        xs = [sum(c[i] * right[i] for i in range(3)) for c in corners]
        ys = [sum(c[i] * up[i] for i in range(3)) for c in corners]
        margin = 2 * (LABEL_REACH + 2 * LABEL_R) if exploded else 20.0
        v["extent"] = round(max(max(xs) - min(xs), max(ys) - min(ys)) + margin, 1)
        v["centre"] = [round((box[0][i] + box[1][i]) / 2, 3) for i in range(3)]
        v["from"] = [round(v["eye"][i] + v["centre"][i] - v["target"][i], 3) for i in range(3)]


def to_fusion(v, up):
    """A kit-frame vector or point in the Fusion document's frame (same rule as the scripts)."""
    return (-v[0], v[2], v[1]) if up == "y" else (-v[0], -v[1], v[2])


def expected_box(entry, up, offset, exploded):
    """Where an item's bounding box should be in the Fusion document (mm, root space)."""
    d = [entry["explode"][i] + offset[i] for i in range(3)] if exploded else [0.0, 0.0, 0.0]
    a = to_fusion([entry["bbox"][0][i] + d[i] for i in range(3)], up)
    b = to_fusion([entry["bbox"][1][i] + d[i] for i in range(3)], up)
    return [[min(a[i], b[i]) for i in range(3)], [max(a[i], b[i]) for i in range(3)]]


def scope_allows(cloud_folder):
    """(allowed, message): is the cloud folder inside the add-in's scope guard list (~/.fusion-mcp/config.json)?"""
    cfg = Path.home() / ".fusion-mcp" / "config.json"
    try:
        scope = json.loads(cfg.read_text(encoding="utf-8")).get("scope", {})
    except (OSError, ValueError):
        return True, "no scope guard configured"
    if not scope.get("enabled"):
        return True, "scope guard is off"
    folders = [str(f).strip("/") for f in scope.get("folders", [])]
    ok = any(cloud_folder == f or cloud_folder.startswith(f + "/") for f in folders)
    return ok, ("in scope" if ok else "%r is not in the scope guard list of %s (it has %s): add it first" % (cloud_folder, cfg, folders))


def _run(fc, code, data, name, document=None):
    fc.run(code.replace("__DATA__", repr(json.dumps(data))), name, exit_on_error=False, document=document)
    res = fc.last_result
    if not res or not res.get("ok"):
        err = (res or {}).get("error") or {}
        raise RuntimeError("%s failed: %s" % (name, err.get("message") or "no result (is Fusion running with the add-in?)"))
    return res["value"]


def check(data, made, seen):
    """Compare what Fusion holds with the manifest: list of problems (empty = good)."""
    problems = []
    want = {e["key"]: e for e in data["parts"]}
    got = {m["key"]: m for m in made}
    for key, e in want.items():
        m = got.get(key)
        if not m:
            problems.append("%s: not imported" % key)
            continue
        if abs(m["volume_mm3"] - e["volume_mm3"]) > max(0.001 * e["volume_mm3"], 0.05):
            problems.append("%s: volume in Fusion %.2f mm3, in the kit %.2f" % (key, m["volume_mm3"], e["volume_mm3"]))
        if m.get("bbox") and max(abs(m["bbox"][a][i] - e["bbox"][a][i]) for a in (0, 1) for i in range(3)) > 0.02:
            problems.append("%s: sits at %s in Fusion, at %s in the kit" % (key, m["bbox"], e["bbox"]))
        if m.get("nested"):
            problems.append("%s: still wrapped in a child component" % key)
        if m["moved_mm"] > 0.001:
            problems.append("%s: Fusion placed the import %.3f mm away from the origin" % (key, m["moved_mm"]))
    asm, exp = seen["groups"].get("Assembled", {}), seen["groups"].get("Exploded", {})
    if sorted(asm) != sorted(want):
        problems.append("Assembled group holds %s, expected %s" % (sorted(asm), sorted(want)))
    shown = sorted(k for k, e in want.items() if e["kind"] != "reference")
    if sorted(exp) != shown:
        problems.append("Exploded group holds %s, expected %s" % (sorted(exp), shown))
    for gname, items, exploded in (("Assembled", asm, False), ("Exploded", exp, True)):
        for key, c in items.items():
            e = want.get(key)
            if not e or "box" not in c:
                continue
            ex_box = expected_box(e, seen.get("up", "z"), data["exploded_offset"], exploded)
            off = max(abs(c["box"][a][i] - ex_box[a][i]) for a in (0, 1) for i in range(3))
            if off > 0.05:
                problems.append("%s in the %s group is %.2f mm from where it belongs" % (key, gname, off))
    for key, c in asm.items():
        e = want.get(key)
        if e and (c["name"] != e["name"] or c["description"] != e["description"]):
            problems.append("%s: name or description did not stick" % key)
        if not c["solid"]:
            problems.append("%s: not a solid body in Fusion" % key)
    if sorted(seen["views"]) != sorted(v["name"] for v in data["views"]):
        problems.append("named views are %s, expected %s" % (seen["views"], [v["name"] for v in data["views"]]))
    if not seen["direct"]:
        problems.append("document is not in direct-modelling mode")
    return problems


SHOW = COMMON + r"""
doc, design = the_design()
nv = design.namedViews.itemByName(DATA['view'])
vp = app.activeViewport
cam = nv.camera
cam.isSmoothTransition = False
vp.camera = cam
vp.refresh()
adsk.doEvents()
mcp_result = {'view': nv.name}
"""


def shots(fc, data, out_dir, document=None, notes=None):
    """A picture of each named view as Fusion shows it: fusion_<version>_<view>.png. Returns the files written."""
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    files = []
    for v in data["views"]:
        png = out_dir / ("fusion_%s_%s.png" % (data["version"], v["name"].lower().replace(" ", "_")))
        try:
            _run(fc, SHOW, dict(data, view=v["name"]), "Presentation: show view %s" % v["name"], document)
            fc.shot(png, fit=False, width=1600, height=1100, restore_camera=False)
            files.append(png)
        except Exception as e:              # pictures are a convenience; the document itself is already checked
            if notes is not None:
                notes.append("no picture of view %s: %s" % (v["name"], e))
    return files


def send(data, shots_dir=None, save=True, min_free_slots=2):
    """Build (or rebuild) the presentation document. Returns a report dict; report["problems"] empty = good."""
    fc = _client()
    data = dict(data)
    data["views"] = [dict(v) for v in data["views"]]
    view_extents(data)
    data["labels"] = label_layout(data)
    report = {"document": data["document"], "problems": [], "notes": []}
    h = fc.health()
    if h.get("paused"):
        raise RuntimeError("the add-in's job queue is paused (Claude panel in Fusion): resume it first")
    ok, msg = scope_allows(data["cloud_folder"])
    if not ok:
        raise RuntimeError(msg)
    prep = _run(fc, PREPARE, data, "Presentation: open and empty the document")
    report["state"] = prep["state"]
    if prep["state"] == "new" and save:
        slots = fc.editable_slots()
        if slots and slots[1] - slots[0] < min_free_slots:
            raise RuntimeError("only %d editable document slot(s) free of %d: not creating another saved document" % (slots[1] - slots[0], slots[1]))
    doc = data["document"] if prep["saved"] else None
    imp = _run(fc, IMPORT, data, "Presentation: import parts", doc)
    exp = _run(fc, EXPLODE, data, "Presentation: exploded group and labels", doc)
    views = _run(fc, VIEWS, data, "Presentation: named views", doc)
    report["notes"] += imp["notes"] + views["notes"] + ([exp["label_note"]] if exp["label_note"] else [])
    report.update(up=imp["up"], placed=exp["placed"], traces=exp["traces"], labels=exp["labels"])
    seen = _run(fc, VERIFY, data, "Presentation: read back", doc)
    report["problems"] = check(data, imp["made"], seen)
    # pictures first: straight after a FIRST save the upload is still running and the scope guard cannot yet tell which
    # cloud folder the document is in, so every script is refused for a moment
    if shots_dir:
        report["shots"] = [str(f) for f in shots(fc, data, shots_dir, doc, report["notes"])]
    if save and not report["problems"]:
        report["save"] = _run(fc, SAVE, data, "Presentation: save", doc)
    return report
