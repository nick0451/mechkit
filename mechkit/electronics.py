"""KiCad boards and schematics in a MechKit build: rule checks, board design edits, the board as design input for the
mechanical parts, and the package of files a board manufacturer takes.

KiCad does the work; text-to-cad's `cad.kicad_pcb` / `cad.kicad_sch` / `cad.kicad` (MIT, Copyright (c) 2026 Thompson
Labs LLC, https://github.com/earthtojake/text-to-cad) run it headless in a private folder, so the person's KiCad
settings are neither read nor written, and turn its reports into results.

Which KiCad runs:
- CHECKS and EXPORTS need only a `kicad-cli`: $MECHKIT_KICAD_CLI, else kicode's when the `kicad` extra is installed,
  else the KiCad installed on the machine.
- EDITS (edit_board, edit_schematic, route) need the `kicad` extra (`uv sync --extra kicad`): kicode, an unofficial
  packaging of a KiCad NIGHTLY (GPL-3.0-or-later, about 73 MB), because only the nightly has the API an edit uses.
  A file an edit saves is in the nightly's format, which a stable KiCad app refuses to open: `stable_copy` writes a
  downgraded copy for looking at in the stable app (edit_board refreshes it by default). The nightly-format file
  stays the source; never edit the copy.

    check(board=, schematic=)        DRC and ERC -> {"drc": {...}, "erc": {...}, "status"}; write_report() saves it
    board_interface(board)           outline size, thickness and holes in mm, in the interface.json layout
    edit_board(path) / edit_schematic(path)     `with` blocks handing over KiPy's open document (see references/pcb/)
    route(board, connections, ...)   the library's router, inside an edit_board block
    export(board, kind, out)         one of KiCad's outputs (gerbers, drill, pos, bom, step, dxf, pdf ...)
    fab_package(board, out)          what a fab takes: gerbers + drill zipped, placement and BOM for assembly, and a
                                     manifest binding the files to the exact board revision and its rule checks
    render(board, out_png)           a picture of the board by KiCad's own renderer
    stable_copy(board)               a copy a stable KiCad app opens

Gates: a DRC or ERC error (or a check that could not run) BLOCKS fab_package unless the person said to go ahead, and the
manifest then records their words and every error. Ordering boards and parts is the person's decision (G2).
"""

import contextlib
import csv
import glob
import hashlib
import json
import os
import shutil
import subprocess
import tempfile
import zipfile
from pathlib import Path

from . import dfm

KICAD_EXTRA_HINT = "board edits need the kicad extra: run `uv sync --extra kicad` (kicode, a KiCad nightly, GPL, about 73 MB)"


def have_editor():
    """Whether kicode (the KiCad nightly an edit needs) is installed."""
    import importlib.util
    return importlib.util.find_spec("kicode") is not None


def _kicode_cli():
    if not have_editor():
        return None
    try:
        import kicode
        p = Path(kicode.executable())
        return p if p.is_file() else None
    except Exception:
        return None


def find_kicad_cli():
    """Path of the kicad-cli used for checks and exports, or None."""
    names = [os.environ.get("MECHKIT_KICAD_CLI"), _kicode_cli()]
    names += sorted(glob.glob("C:/Program Files/KiCad/*/bin/kicad-cli.exe"), reverse=True)
    names += ["/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli", shutil.which("kicad-cli")]
    for n in names:
        if n and Path(n).is_file():
            return Path(n)
    return None


def find_stable_kicad_cli():
    """An installed (stable) KiCad's kicad-cli, or None: used only to confirm a stable copy opens."""
    for n in sorted(glob.glob("C:/Program Files/KiCad/*/bin/kicad-cli.exe"), reverse=True) + [
            "/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli", shutil.which("kicad-cli") or ""]:
        if n and Path(n).is_file():
            return Path(n)
    return None


def _cad():
    """The library, told which KiCad to use. Raises RuntimeError when there is none."""
    cli = find_kicad_cli()
    if cli is None:
        raise RuntimeError("KiCad's kicad-cli was not found (install KiCad, `uv sync --extra kicad`, or set MECHKIT_KICAD_CLI)")
    os.environ.setdefault("DO_NOT_TRACK", "1")
    if cli == _kicode_cli():
        os.environ.pop("CAD_KICAD_CLI", None)                  # the library's own default: kicode's
    else:
        os.environ["CAD_KICAD_CLI"] = str(cli)
    import cad
    import cad.kicad_pcb
    import cad.kicad_sch
    return cad, cli


def kicad_version(cli=None):
    cli = cli or find_kicad_cli()
    if cli is None:
        return None
    try:
        return subprocess.run([str(cli), "version"], capture_output=True, text=True, timeout=60).stdout.strip() or None
    except Exception:
        return None


# ------------------------------------------------------------------------------------------------ checks
def check(board=None, schematic=None):
    """Design rule check of a board and / or electrical rule check of a schematic."""
    out = {"checker": "KiCad kicad-cli via text-to-cad cad %s" % dfm.version()}
    try:
        cad, cli = _cad()
        out["kicad"] = kicad_version(cli)
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


# ------------------------------------------------------------------------------------------------ the board as design input
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
    holes = [{"x": round(float(h.at[0]), 4), "y": round(float(h.at[1]), 4), "diameter": round(float(h.diameter), 4), "part": h.part}
             for h in view.holes]
    return {"name": name or board.stem, "kind": "pcb", "frame": "KiCad board frame: mm, x right, y down",
            "dims": {"length_x": dim(max(xs) - min(xs)), "width_y": dim(max(ys) - min(ys)), "thickness": dim(info["thickness"])},
            "outline_min": [round(min(xs), 4), round(min(ys), 4)], "outline_max": [round(max(xs), 4), round(max(ys), 4)],
            "outline_loops": len(view.outline), "holes": holes, "counts": info.get("counts", {})}


# ------------------------------------------------------------------------------------------------ edits
def _need_editor():
    if not have_editor():
        raise RuntimeError(KICAD_EXTRA_HINT)
    os.environ.setdefault("DO_NOT_TRACK", "1")
    os.environ.pop("CAD_KICAD_CLI", None)                      # an edit runs the nightly's own kicad-cli
    import cad.kicad
    import cad.kicad_pcb
    import cad.kicad_sch
    import cad
    return cad


@contextlib.contextmanager
def edit_board(path, stable="10.0"):
    """`with edit_board("x.kicad_pcb") as b:` hands over KiPy's open Board (a board not there yet is made: 2 layers,
    1.6 mm); saved at the end only if the block changed it, not at all if it raised. Import KiPy's names from
    `kicode`, never `kipy`. After a save, a copy the stable KiCad app opens is refreshed in `<folder>/kicad-<stable>/`
    (stable=None to skip)."""
    cad = _need_editor()
    path = Path(path)
    before = _sha256(path) if path.is_file() else None
    with cad.kicad_pcb.edit(path) as board:
        yield board
    if stable and path.is_file() and _sha256(path) != before:
        stable_copy(path, target=stable)


@contextlib.contextmanager
def edit_schematic(path):
    """`with edit_schematic("x.kicad_sch") as s:` hands over KiPy's open Schematic, saved like edit_board's."""
    cad = _need_editor()
    with cad.kicad_sch.edit(Path(path)) as sch:
        yield sch


def route(board, connections=None, **options):
    """The library's router on a board an edit_board block has open: copper for the connections named, in that order
    (options: layers, width, clearance, vias, via_cost). Returns its `Routed` result. Check with DRC afterwards."""
    cad = _need_editor()
    return cad.kicad.route(board, connections, **options)


def run_kicad_cli(args, cli=None, timeout=600):
    """Run kicad-cli with private settings (never the person's KiCad settings). Returns the CompletedProcess."""
    cad, found = _cad()
    from cad.kicad import _program
    with _program.private_run("mechkit-kicad-") as (_folder, env):
        return subprocess.run([str(cli or found)] + [str(a) for a in args], capture_output=True, text=True, env=env, timeout=timeout)


def stable_copy(board, target="10.0", out=None):
    """A copy of the board's project in a stable KiCad's file format, for LOOKING at in that app: written to
    `<board folder>/kicad-<target>/` (or `out`). Returns the copied board's path. Needs the nightly (kicad extra)."""
    _need_editor()
    board = Path(board)
    project = board.with_suffix(".kicad_pro")
    if not project.is_file():
        raise FileNotFoundError("%s has no project file beside it (an edit makes one)" % board.name)
    out = Path(out) if out else board.parent / ("kicad-%s" % target)
    work = Path(tempfile.mkdtemp(prefix="mechkit_kicad_copy_"))   # KiCad refuses a destination inside the project
    try:
        r = run_kicad_cli(["project", "downgrade", "--target", target, "-o", work / "copy", project], cli=_kicode_cli())
        if r.returncode != 0 or next((work / "copy").rglob(board.name), None) is None:
            raise RuntimeError("KiCad could not write a %s copy of %s: %s" % (target, board.name, (r.stdout + r.stderr).strip()[-300:]))
        shutil.rmtree(out, ignore_errors=True)
        shutil.move(str(work / "copy"), str(out))
    finally:
        shutil.rmtree(work, ignore_errors=True)
    (out / "READ-ONLY-COPY.txt").write_text(
        "A copy of ../%s in KiCad %s's file format, for viewing in that app.\nThe source is the file one folder up; "
        "changes made here are overwritten at the next edit.\n" % (board.name, target), encoding="utf-8")
    return next(out.rglob(board.name))


def render(board, out_png, side="top", width=1600, height=1200):
    """A picture of the board by KiCad's own 3D renderer. Returns the path."""
    out = Path(out_png)
    out.parent.mkdir(parents=True, exist_ok=True)
    r = run_kicad_cli(["pcb", "render", "--side", side, "--width", width, "--height", height, "--background", "opaque", "-o", out, board])
    if r.returncode != 0 or not out.is_file() or out.stat().st_size == 0:
        raise RuntimeError("KiCad wrote no picture of %s: %s" % (Path(board).name, (r.stdout + r.stderr).strip()[-300:]))
    return out


# ------------------------------------------------------------------------------------------------ outputs for a manufacturer
def export(board, kind, out):
    """Write one of KiCad's outputs for a board (gerbers, drill, pos, bom, step, glb, pdf, dxf, odb, ipc2581) into the
    folder `out`. Returns the files written. Raises when KiCad wrote nothing usable."""
    cad, _ = _cad()
    result = cad.kicad_pcb.export(Path(board), kind, Path(out))
    written = [Path(p) for p in result.written]
    if not written or any(not p.is_file() or p.stat().st_size == 0 for p in written):
        raise RuntimeError("KiCad wrote no usable %s output for %s" % (kind, Path(board).name))
    return written


def _sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def jlc_placement(pos_csv, out_csv):
    """KiCad's placement file with the column names JLCPCB's assembly reads (Designator, Mid X, Mid Y, Layer,
    Rotation; mm and degrees). Values are copied, not changed: check rotations in the fab's preview. Returns rows."""
    with open(pos_csv, newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    need = {"Ref", "PosX", "PosY", "Rot", "Side"}
    if rows and not need <= set(rows[0]):
        raise ValueError("%s is not KiCad's placement file (columns %s)" % (Path(pos_csv).name, sorted(rows[0])))
    with open(out_csv, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["Designator", "Val", "Package", "Mid X", "Mid Y", "Rotation", "Layer"])
        for r in rows:
            w.writerow([r["Ref"], r.get("Val", ""), r.get("Package", ""), r["PosX"], r["PosY"], r["Rot"],
                        {"top": "Top", "bottom": "Bottom"}.get(r["Side"].strip().lower(), r["Side"])])
    return len(rows)


def fab_package(board, out, schematic=None, go_ahead=""):
    """The files a board manufacturer takes, from the saved board, bound to it by a manifest:

        <out>/<board>-gerbers.zip      gerbers + drill files (what a fab's upload takes)
        <out>/gerbers/, <out>/drill/   the same files unzipped, for a Gerber viewer
        <out>/assembly/                KiCad's placement file, the same with JLCPCB's column names, and the BOM when
                                       the schematic is beside the board
        <out>/fab_manifest.json        board file + sha256, KiCad version, DRC / ERC results, every file with its sha256

    A DRC or ERC error, or a check that could not run, blocks the package (PermissionError) unless `go_ahead` carries
    the person's own words and date; the manifest then records them and every error. The folder is written whole and
    swapped in. Nothing is sent anywhere: ordering is the person's decision (gate G2)."""
    board, out = Path(board).resolve(), Path(out).resolve()
    if schematic is None and board.with_suffix(".kicad_sch").is_file():
        schematic = board.with_suffix(".kicad_sch")
    checks = check(board=board, schematic=schematic)
    blocked = [k for k in ("drc", "erc") if k in checks and checks[k]["status"] != "pass"]
    if blocked and len((go_ahead or "").strip()) < 8:
        lines = ["%s %s: %s" % (k.upper(), checks[k]["status"], checks[k].get("reason") or "; ".join(
            "%s at %s" % (i["code"], i["location"]) for i in checks[k]["issues"] if i["severity"] == "error")[:300]) for k in blocked]
        raise PermissionError("fabrication files are blocked by the rule checks:\n  " + "\n  ".join(lines) +
                              "\nFix them, or pass go_ahead='<the person's answer and the date>' to write the files anyway.")
    staging = out.with_name(out.name + ".staging")
    shutil.rmtree(staging, ignore_errors=True)
    staging.mkdir(parents=True)
    try:
        gerbers = export(board, "gerbers", staging / "gerbers")
        drill = export(board, "drill", staging / "drill")
        names = [p.name for p in gerbers]
        missing = [what for what, key in (("board outline (Edge.Cuts)", "Edge_Cuts"), ("copper", "_Cu")) if not any(key in n for n in names)]
        if missing:
            raise RuntimeError("the gerber set has no %s: not a usable package" % " and no ".join(missing))
        advisory = [what for what, key in (("solder mask", "_Mask"), ("silkscreen", "_Silkscreen")) if not any(key in n for n in names)]
        with zipfile.ZipFile(staging / ("%s-gerbers.zip" % board.stem), "w", zipfile.ZIP_DEFLATED) as z:
            for p in sorted(gerbers + drill):
                z.write(p, p.name)
        notes = ["no %s layer in the gerber set" % a for a in advisory]
        try:
            pos = export(board, "pos", staging / "assembly")
            n = jlc_placement(pos[0], staging / "assembly" / ("%s-cpl-jlcpcb.csv" % board.stem))
            if n == 0:
                notes.append("the placement file lists no parts")
        except RuntimeError as e:
            notes.append("no placement file: %s" % e)
        if schematic:
            try:
                export(board, "bom", staging / "assembly")
            except Exception as e:
                notes.append("no BOM: %s" % str(e)[:200])
        else:
            notes.append("no schematic beside the board: no BOM")
        files = [{"path": p.relative_to(staging).as_posix(), "bytes": p.stat().st_size, "sha256": _sha256(p)}
                 for p in sorted(staging.rglob("*")) if p.is_file()]
        manifest = {"about": "Fabrication package written by mechkit.electronics.fab_package. Rebuild after any board change.",
                    "board": {"file": board.name, "sha256": _sha256(board)},
                    "schematic": {"file": Path(schematic).name, "sha256": _sha256(schematic)} if schematic else None,
                    "kicad": checks.get("kicad"), "checker": checks["checker"],
                    "checks": {k: {f: checks[k][f] for f in ("status", "errors", "warnings", "reason", "issues")} for k in ("drc", "erc") if k in checks},
                    "go_ahead": go_ahead.strip() if blocked else None, "blocked_by": blocked, "notes": notes, "files": files}
        (staging / "fab_manifest.json").write_text(json.dumps(manifest, indent=1, default=str), encoding="utf-8", newline="\n")
    except Exception:
        shutil.rmtree(staging, ignore_errors=True)
        raise
    old = out.with_name(out.name + ".old")
    shutil.rmtree(old, ignore_errors=True)
    if out.exists():
        out.rename(old)
    staging.rename(out)
    shutil.rmtree(old, ignore_errors=True)
    return manifest


def package_is_current(out, board):
    """Whether a fab package was made from the board as it is now, and its files are unchanged: (True, "") or
    (False, why). Check this before anything is ordered."""
    out = Path(out)
    m = out / "fab_manifest.json"
    if not m.is_file():
        return False, "no fab_manifest.json in %s" % out.name
    data = json.loads(m.read_text(encoding="utf-8"))
    if not Path(board).is_file() or _sha256(board) != data["board"]["sha256"]:
        return False, "the board changed after the package was made: make it again"
    for f in data["files"]:
        p = out / f["path"]
        if not p.is_file() or _sha256(p) != f["sha256"]:
            return False, "%s is missing or was changed after the package was made" % f["path"]
    return True, ""
