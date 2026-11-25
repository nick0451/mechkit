"""KiCad boards and schematics in a MechKit build: rule checks, the board as a bought-part style interface, exports.

KiCad's own command line does the work (`kicad-cli`, from the KiCad that is installed on the machine); text-to-cad's
`cad.kicad_pcb` / `cad.kicad_sch` (MIT, https://github.com/earthtojake/text-to-cad) run it headless in a private
folder, so the person's KiCad settings are neither read nor written, and turn its reports into results.

    find_kicad_cli()                 $MECHKIT_KICAD_CLI, $CAD_KICAD_CLI, the newest installed KiCad, or PATH
    check(board=, schematic=)        DRC and ERC -> {"drc": {...}, "erc": {...}, "status"}; write_report() saves it
    board_interface(board)           outline size, thickness and holes in mm, in the interface.json layout, so the
                                     mechanical design reads the board's real numbers (tag "stated": from the board file)
    export(board, kind, out)         gerbers, drill, pos, bom, step, pdf ... (ordering a board is the person's decision)

Fail closed: no KiCad, or a check that raises, is "not evaluated", never a pass. Editing and routing boards (which
need the library's own KiCad build) are not wrapped.
"""

import glob
import json
import os
import shutil
from pathlib import Path

from . import dfm


def find_kicad_cli():
    """Path of kicad-cli, or None."""
    names = [os.environ.get("MECHKIT_KICAD_CLI"), os.environ.get("CAD_KICAD_CLI")]
    installed = sorted(glob.glob("C:/Program Files/KiCad/*/bin/kicad-cli.exe"), reverse=True)
    names += installed + ["/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli", shutil.which("kicad-cli")]
    for n in names:
        if n and Path(n).is_file():
            return Path(n)
    return None


def _cad():
    """The library, told to use the installed KiCad. Raises RuntimeError when there is none."""
    cli = find_kicad_cli()
    if cli is None:
        raise RuntimeError("KiCad's kicad-cli was not found (install KiCad, or set MECHKIT_KICAD_CLI)")
    os.environ.setdefault("DO_NOT_TRACK", "1")
    os.environ["CAD_KICAD_CLI"] = str(cli)
    import cad
    import cad.kicad_pcb
    import cad.kicad_sch
    return cad, cli


def check(board=None, schematic=None):
    """Design rule check of a board and / or electrical rule check of a schematic."""
    out = {"checker": "KiCad kicad-cli via text-to-cad cad %s" % dfm.version()}
    try:
        cad, cli = _cad()
        out["kicad_cli"] = cli.parent.parent.name
    except RuntimeError as e:
        cad = None
        missing = {"status": "not evaluated", "reason": str(e), "errors": 0, "warnings": 0, "issues": [], "summary": "KiCad not found"}
    def run(path, fn):
        if not Path(path).is_file():                           # nothing was checked: not a failed design
            return {"status": "not evaluated", "reason": "file not found", "errors": 0, "warnings": 0, "issues": [], "summary": "file not found"}
        return dfm._guarded(lambda: fn(Path(path))) if cad else missing
    if board:
        out["drc"] = dict(run(board, lambda p: cad.kicad_pcb.drc(p)), file=Path(board).name)
    if schematic:
        out["erc"] = dict(run(schematic, lambda p: cad.kicad_sch.erc(p)), file=Path(schematic).name)
    statuses = [out[k]["status"] for k in ("drc", "erc") if k in out]
    out["status"] = "fail" if "fail" in statuses else ("pass" if statuses and all(s == "pass" for s in statuses) else "not evaluated")
    return out


def write_report(folder, report):
    folder = Path(folder)
    folder.mkdir(parents=True, exist_ok=True)
    tmp = folder / "electronics_report.json.tmp"
    tmp.write_text(json.dumps(report, indent=1, default=str), encoding="utf-8", newline="\n")
    tmp.replace(folder / "electronics_report.json")
    return folder / "electronics_report.json"


def board_interface(board, name=None):
    """A board's mechanical facts, in the layout of parts/purchased/<part>/interface.json. KiCad's frame: mm, y DOWN,
    origin as in the board file; `outline_min` / `outline_max` give the corners so a script can place it."""
    cad, _ = _cad()
    board = Path(board)
    view = cad.kicad_pcb.read(board)
    info = cad.kicad_pcb.inspect(board)
    pts = [p for loop in view.outline for p in loop]
    if not pts:
        raise ValueError("%s has no closed outline on Edge.Cuts" % board.name)
    xs, ys = [p[0] for p in pts], [p[1] for p in pts]
    source = "KiCad board file %s" % board.name

    def dim(value):
        return {"value": round(float(value), 4), "tag": "stated", "source": source}
    holes = []
    for h in view.holes:
        at = getattr(h, "at", None) or getattr(h, "position", None)
        d = getattr(h, "diameter", None) or getattr(h, "drill", None)
        holes.append({"x": round(float(at[0]), 4), "y": round(float(at[1]), 4), "diameter": round(float(d), 4),
                      "plated": bool(getattr(h, "plated", False))})
    return {"name": name or board.stem, "kind": "pcb", "frame": "KiCad board frame: mm, x right, y down",
            "dims": {"length_x": dim(max(xs) - min(xs)), "width_y": dim(max(ys) - min(ys)), "thickness": dim(info["thickness"])},
            "outline_min": [round(min(xs), 4), round(min(ys), 4)], "outline_max": [round(max(xs), 4), round(max(ys), 4)],
            "outline_loops": len(view.outline), "holes": holes, "counts": info.get("counts", {})}


def export(board, kind, out):
    """Write one of KiCad's outputs for a board (gerbers, drill, pos, bom, step, glb, pdf, dxf ...). Returns the files."""
    cad, _ = _cad()
    result = cad.kicad_pcb.export(Path(board), kind, Path(out))
    written = [Path(p) for p in result.written]
    if not written or any(not p.is_file() or p.stat().st_size == 0 for p in written):
        raise RuntimeError("KiCad wrote no usable %s output for %s" % (kind, Path(board).name))
    return written
