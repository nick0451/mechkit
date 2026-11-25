"""Slice print files for time and filament estimates, with the slicer already on the machine.

    estimates(project, version, printer=..., process=..., filament=...)   ->  exports/<version>/print_estimates.json

The slice is the slicer's own command line (Bambu Studio or OrcaSlicer: same flags). The one thing their command lines
need and do not do themselves is COMPLETE presets (each preset as saved is only its differences from a parent); that is
done by text-to-cad's `cad.orcaslicer.complete` (MIT, https://github.com/earthtojake/text-to-cad), given the slicer's
own profiles folder. Nothing is sent to a printer from here: sending a print is the person's action (gate G4).

The slicer is looked for in $MECHKIT_SLICER, then the usual install folders. `print_estimates.json` is what the
requirement checks print_time_max_h, filament_max_g and parts_fit_bed read. A file that does not slice is listed under
"problems", and those checks then answer "not evaluated": a failed slice is never a pass.
"""

import json
import os
import re
import shutil
import subprocess
import tempfile
from pathlib import Path

CANDIDATES = (
    "C:/Program Files/Bambu Studio/bambu-studio.exe",
    "C:/Program Files/OrcaSlicer/orca-slicer.exe",
    "/Applications/BambuStudio.app/Contents/MacOS/BambuStudio",
    "/Applications/OrcaSlicer.app/Contents/MacOS/OrcaSlicer",
)
TIMEOUT_S = 600


def find_slicer():
    """Path of the slicer's program, or None."""
    env = os.environ.get("MECHKIT_SLICER")
    for c in ([env] if env else []) + list(CANDIDATES) + [shutil.which("orca-slicer") or "", shutil.which("bambu-studio") or ""]:
        if c and Path(c).is_file():
            return Path(c)
    return None


def profiles_folder(slicer):
    """The slicer's built-in profiles folder (resources/profiles beside the program, or in the app bundle)."""
    for p in (slicer.parent / "resources" / "profiles", slicer.parent.parent / "Resources" / "profiles"):
        if p.is_dir():
            return p
    return None


def _seconds(text):
    """'1h 23m 45s' -> seconds."""
    total = 0
    for n, unit in re.findall(r"(\d+)\s*([dhms])", text or ""):
        total += int(n) * {"d": 86400, "h": 3600, "m": 60, "s": 1}[unit]
    return total


def _header(gcode, lines=900):
    head = {}
    with open(gcode, encoding="utf-8", errors="replace") as f:
        for _ in range(lines):
            line = f.readline()
            if not line:
                break
            if line.startswith(("; BambuStudio ", "; OrcaSlicer ")):
                head["slicer"] = line[2:].strip()
            m = re.match(r";\s*([^:=]+?)\s*[:=]\s*(.*)", line)
            if m and m.group(1) not in head:
                head[m.group(1).strip()] = m.group(2).strip()
    return head


def slice_file(stl, slicer, presets, bed_type="Textured PEI Plate"):
    """Slice one print file as it lies. -> {ok, seconds, filament_g, layers, settings, warning} or {ok: False, error}."""
    stl = Path(stl).resolve()
    work = Path(tempfile.mkdtemp(prefix="mechkit_slice_"))
    try:
        local = work / stl.name
        shutil.copy(stl, local)
        cmd = [str(slicer), "--slice", "0", "--load-settings", "%s;%s" % (presets["printer"], presets["process"]),
               "--load-filaments", ";".join(str(f) for f in presets["filaments"]), "--curr-bed-type", bed_type,
               "--outputdir", str(work), "--export-3mf", "out.3mf", str(local)]
        try:
            subprocess.run(cmd, cwd=str(work), capture_output=True, timeout=TIMEOUT_S, check=False)
        except subprocess.TimeoutExpired:
            return {"ok": False, "error": "the slicer timed out after %d s" % TIMEOUT_S}
        result_file, gcode = work / "result.json", work / "plate_1.gcode"
        if not result_file.is_file():
            return {"ok": False, "error": "the slicer wrote no result.json"}
        result = json.loads(result_file.read_text(encoding="utf-8"))
        if result.get("return_code") != 0 or not gcode.is_file():
            return {"ok": False, "error": "slicer: %s (code %s)" % (result.get("error_string"), result.get("return_code"))}
        head = _header(gcode)
        plate = (result.get("sliced_plates") or [{}])[0]
        total = re.search(r"total estimated time:\s*(.*)", head.get("model printing time", ""))
        seconds = _seconds(total.group(1) if total else head.get("model printing time", "")) or int(plate.get("total_predication") or 0)
        grams = float((head.get("total filament weight [g]") or "0").split(",")[0] or 0)
        if seconds <= 0 or grams <= 0:
            return {"ok": False, "error": "the slicer reported no time or no filament weight"}
        return {"ok": True, "seconds": seconds, "filament_g": round(grams, 2), "layers": int(head.get("total layer number", 0) or 0),
                "warning": plate.get("warning_message") or "",
                "settings": {k: head.get(k) for k in ("printer_model", "filament_type", "layer_height", "wall_loops",
                                                      "sparse_infill_density", "enable_support", "nozzle_temperature", "slicer")}}
    finally:
        shutil.rmtree(work, ignore_errors=True)


def _stl_size(path):
    """Bounding size (x, y, z) of a binary or text STL, as it lies."""
    import numpy as np
    data = Path(path).read_bytes()
    n = int.from_bytes(data[80:84], "little") if len(data) >= 84 else -1
    if len(data) == 84 + 50 * n:
        tri = np.frombuffer(data, dtype=np.dtype([("n", "<f4", 3), ("v", "<f4", (3, 3)), ("a", "<u2")]), count=n, offset=84)["v"].reshape(-1, 3)
    else:
        tri = np.array([[float(x) for x in m.groups()] for m in re.finditer(r"vertex\s+(\S+)\s+(\S+)\s+(\S+)", data.decode("ascii", "replace"))])
    if tri.size == 0:
        return None
    return [round(float(v), 2) for v in (tri.max(axis=0) - tri.min(axis=0))]


def estimates(project, version, printer, process, filament, bed_type="Textured PEI Plate", files=None, slicer=None):
    """Slice every STL of exports/<version> (or the given files) and write print_estimates.json there. Returns the dict."""
    os.environ.setdefault("DO_NOT_TRACK", "1")
    folder = Path(project) / "exports" / version
    stls = [Path(f) for f in files] if files else sorted(folder.glob("*.stl"))
    out = {"version": version, "printer": printer, "process": process, "filament": filament, "bed_type": bed_type,
           "files": [], "problems": [], "total_seconds": 0, "total_g": 0.0}
    slicer = Path(slicer) if slicer else find_slicer()
    if slicer is None:
        out["problems"].append("no slicer found (set MECHKIT_SLICER to Bambu Studio's or OrcaSlicer's program)")
    elif not stls:
        out["problems"].append("no STL files in %s" % folder)
    else:
        out["slicer"] = slicer.name
        work = Path(tempfile.mkdtemp(prefix="mechkit_presets_"))
        try:
            import cad.orcaslicer as oc
            prof = profiles_folder(slicer)
            done = oc.complete(printer=printer, process=process, filament=(filament,), out=work, profiles=(str(prof),) if prof else ())
            presets = {"printer": done.printer, "process": done.process, "filaments": done.filaments}
            for stl in stls:
                r = slice_file(stl, slicer, presets, bed_type)
                entry = {"file": stl.name, "size": _stl_size(stl)}
                if r["ok"]:
                    entry.update(seconds=r["seconds"], g=r["filament_g"], layers=r["layers"], warning=r["warning"], settings=r["settings"])
                    out["total_seconds"] += r["seconds"]
                    out["total_g"] = round(out["total_g"] + r["filament_g"], 2)
                else:
                    out["problems"].append("%s: %s" % (stl.name, r["error"]))
                out["files"].append(entry)
        except Exception as e:                                 # presets that cannot be completed: nothing was estimated
            out["problems"].append("presets: %s: %s" % (type(e).__name__, e))
        finally:
            shutil.rmtree(work, ignore_errors=True)
    folder.mkdir(parents=True, exist_ok=True)
    tmp = folder / "print_estimates.json.tmp"
    tmp.write_text(json.dumps(out, indent=1), encoding="utf-8", newline="\n")
    tmp.replace(folder / "print_estimates.json")
    return out
