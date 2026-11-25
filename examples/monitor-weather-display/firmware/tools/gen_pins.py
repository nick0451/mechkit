"""Write include/pins.h from ../pinmap.json (the single source for pin numbers).

Runs automatically before every PlatformIO build (extra_scripts in platformio.ini), and by hand:
    python tools/gen_pins.py
"""

import json
from pathlib import Path

try:
    Import("env")  # noqa: F821 - provided by PlatformIO when run as a pre-build script
    ROOT = Path(env["PROJECT_DIR"])  # noqa: F821
except NameError:
    ROOT = Path(__file__).resolve().parents[1]


def generate():
    pinmap = json.loads((ROOT.parent / "pinmap.json").read_text(encoding="utf-8"))
    lines = ["// GENERATED from ../pinmap.json by tools/gen_pins.py. Do not edit: change pinmap.json instead.",
             "// Board: %s" % pinmap["board"]["name"], "#pragma once", ""]
    seen = {}
    for pin in pinmap["pins"]:
        if pin["gpio"] in seen:
            raise SystemExit("pinmap.json: GPIO%d is used by both %s and %s" % (pin["gpio"], seen[pin["gpio"]], pin["signal"]))
        seen[pin["gpio"]] = pin["signal"]
        note = " (%s)" % pin["notes"] if pin.get("notes") else ""
        lines.append("#define PIN_%-10s %2d   // -> %s%s" % (pin["signal"], pin["gpio"], pin["connects_to"], note))
    out = ROOT / "include" / "pins.h"
    out.parent.mkdir(exist_ok=True)
    text = "\n".join(lines) + "\n"
    if not out.exists() or out.read_text(encoding="utf-8") != text:
        out.write_text(text, encoding="utf-8", newline="\n")
    return out


generate()
