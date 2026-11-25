"""Get geometry out of an open Fusion document for analysis (read-only: files are written, the model is not changed,
and the user's active tab is not switched: the document may be a background tab).

    from mechkit import fusion_export
    info = fusion_export.component_step("My build_Assembly", "Bracket", "out/bracket.step")
    info["bodies"]  ->  [{"name", "bbox": [[min], [max]] (mm), "volume_mm3"}]

OPTIONAL and experimental: needs the client of a separate Fusion add-in (`fusion_client.py`, not part of MechKit; see
MECHKIT_FUSION_CLIENT below). A component is exported as one STEP file with
all its bodies; `mechkit.sim.mesh.step_mesh(..., keep_bbox=...)` then meshes just the body you want.
"""

import os
import sys
from pathlib import Path

KIT_ROOT = Path(__file__).resolve().parents[1]
FUSION_CLIENT_ENV = "MECHKIT_FUSION_CLIENT"       # folder that holds fusion_client.py (the Fusion add-in's client: NOT part of this kit)
FUSION_TOOLS = Path(os.environ[FUSION_CLIENT_ENV]) if os.environ.get(FUSION_CLIENT_ENV) else KIT_ROOT.parent / "Fusion Designs"

EXPORT_CODE = r"""
name, out, wanted = __NAME__, __OUT__, __DOC__
doc = None
for d in app.documents:                      # works on a background tab: the user's active tab is left alone
    if d.isSaved and d.dataFile.name == wanted:
        doc = d
if doc is None:
    raise RuntimeError('document is not open in Fusion: ' + wanted)
design = adsk.fusion.Design.cast(doc.products.itemByProductType('DesignProductType'))
root = design.rootComponent
occ = None
for i in range(root.occurrences.count):
    o = root.occurrences.item(i)
    if not o.isReferencedComponent and o.component.name == name:
        occ = o
if occ is None:
    raise RuntimeError('component not found: ' + name)
options = design.exportManager.createSTEPExportOptions(out, occ.component)
ok = design.exportManager.execute(options)
bodies = []
for i in range(occ.bRepBodies.count):
    b = occ.bRepBodies.item(i)
    bb = b.boundingBox
    bodies.append({'name': b.name, 'volume_mm3': round(b.volume * 1000, 3), 'solid': bool(b.isSolid),
                   'bbox': [[round(bb.minPoint.x * 10, 4), round(bb.minPoint.y * 10, 4), round(bb.minPoint.z * 10, 4)],
                            [round(bb.maxPoint.x * 10, 4), round(bb.maxPoint.y * 10, 4), round(bb.maxPoint.z * 10, 4)]]})
mcp_result = {'exported': bool(ok), 'file': out, 'component': name, 'bodies': bodies, 'active_tab': app.activeDocument.name,
              'document': doc.name, 'version': doc.dataFile.versionNumber if doc.isSaved else None, 'modified': bool(doc.isModified)}
"""


def _client():
    """The Fusion add-in's Python client. It is not part of this kit: this bridge is optional and experimental."""
    if not (FUSION_TOOLS / "fusion_client.py").is_file():
        raise RuntimeError("the Fusion bridge needs fusion_client.py (the client of a separate Fusion add-in, not included with "
                           "MechKit). Looked in %s; set %s to the folder that holds it." % (FUSION_TOOLS, FUSION_CLIENT_ENV))
    if str(FUSION_TOOLS) not in sys.path:
        sys.path.insert(0, str(FUSION_TOOLS))
    import fusion_client
    return fusion_client


def component_step(document, component, out_path):
    """Export one custom component of the open assembly as STEP. Returns the add-in script's result dict."""
    fc = _client()
    out = Path(out_path).resolve()
    out.parent.mkdir(parents=True, exist_ok=True)
    code = EXPORT_CODE.replace("__NAME__", repr(component)).replace("__OUT__", repr(str(out))).replace("__DOC__", repr(document))
    import contextlib
    import io
    with contextlib.redirect_stdout(io.StringIO()):
        fc.run(code, "Export %s as STEP (read-only)" % component, exit_on_error=False)
    res = fc.last_result
    if not res or not res.get("ok") or not res["value"]["exported"] or not out.is_file():
        raise RuntimeError("STEP export failed: %s" % ((res or {}).get("error") or "no result"))
    return res["value"]
