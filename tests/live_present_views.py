"""Live: redo only the named views of an existing presentation document and take their pictures (nothing is saved).

    uv run python tests/live_present_views.py [PROJECT_FOLDER]
"""
import json
import sys
from pathlib import Path

KIT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(KIT))
from mechkit.present import fusion, manifest  # noqa: E402

project = Path(sys.argv[1] if len(sys.argv) > 1 else KIT / "examples" / "monitor-weather-display").resolve()
data = manifest.load(manifest.find(project))
fusion.view_extents(data)
data["labels"] = fusion.label_layout(data)
fc = fusion._client()
print(json.dumps(fusion._run(fc, fusion.VIEWS, data, "Presentation: named views", data["document"]), indent=1))
out = KIT / "work" / "present_views"
out.mkdir(parents=True, exist_ok=True)
for f in fusion.shots(fc, data, out, data["document"]):
    print(f)
