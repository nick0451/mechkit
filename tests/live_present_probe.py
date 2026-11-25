"""Live diagnostic for the presentation document: where things are, what the named views hold, one fitted picture."""
import json
import sys
from pathlib import Path

KIT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(KIT))
from mechkit.present import fusion  # noqa: E402

DOC = "Monitor weather display_Presentation"
CODE = r"""
doc = app.activeDocument
design = adsk.fusion.Design.cast(doc.products.itemByProductType('DesignProductType'))
root = design.rootComponent
out = {'doc': doc.name, 'groups': [], 'views': []}
def box(bb):
    return [[round(bb.minPoint.x * 10, 1), round(bb.minPoint.y * 10, 1), round(bb.minPoint.z * 10, 1)],
            [round(bb.maxPoint.x * 10, 1), round(bb.maxPoint.y * 10, 1), round(bb.maxPoint.z * 10, 1)]]
for i in range(root.occurrences.count):
    o = root.occurrences.item(i)
    out['groups'].append({'name': o.component.name, 'visible': o.isLightBulbOn, 'box_mm': box(o.boundingBox),
                          'transform': [round(v, 3) for v in o.transform2.asArray()], 'children': o.childOccurrences.count})
for i in range(design.namedViews.count):
    nv = design.namedViews.item(i)
    c = nv.camera
    ortho = c.cameraType == adsk.core.CameraTypes.OrthographicCameraType
    ext = c.getExtents() if ortho else []
    out['views'].append({'name': nv.name, 'eye_mm': [round(c.eye.x * 10, 1), round(c.eye.y * 10, 1), round(c.eye.z * 10, 1)],
                         'target_mm': [round(c.target.x * 10, 1), round(c.target.y * 10, 1), round(c.target.z * 10, 1)],
                         'up': [round(c.upVector.x, 2), round(c.upVector.y, 2), round(c.upVector.z, 2)],
                         'ortho': c.cameraType == adsk.core.CameraTypes.OrthographicCameraType,
                         'extents': [round(v, 3) if isinstance(v, float) else v for v in ext], 'viewExtents': round(c.viewExtents, 3),
                         'angle': round(c.perspectiveAngle, 4)})
c = app.activeViewport.camera
out['viewport'] = {'eye_mm': [round(c.eye.x * 10, 1), round(c.eye.y * 10, 1), round(c.eye.z * 10, 1)], 'viewExtents': round(c.viewExtents, 3),
                   'size': [app.activeViewport.width, app.activeViewport.height]}
mcp_result = out
"""

fc = fusion._client()
fc.run(CODE, "Presentation diagnostic (read-only)", exit_on_error=False, document=DOC)
res = fc.last_result
print(json.dumps(res["value"] if res and res.get("ok") else res, indent=1))
png = KIT / "work" / "present_fit.png"
print(fc.shot(png, view="iso_top_right", fit=True, width=1600, height=1100, document=DOC))
