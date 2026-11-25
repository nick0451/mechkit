"""Project spin-up with the folder gate.

Every new idea starts here. The gate: BEFORE anything is created, the user confirms where the work lives:

    own        its own folder under `Claude Project/`, with its own CLAUDE.md and state.md
    inside     a part folder inside an existing project (it shares that project's assembly, parts and notes)
    shared     a small one-off printed part: a folder under `Claude Project/small parts/`

    python -m mechkit propose --name "Desk fan mount" --purchased 2 --custom 3 --firmware
    python -m mechkit new --name "Desk fan mount" --where own --confirmed "user, 2026-11-23: own folder" [--firmware]
                          [--cloud-folder "Admin Project/Desk fan mount"]
    python -m mechkit new --name "Cable clip" --where inside --project "Desk lamp" --confirmed "..."

`propose` only recommends (with its reasons); it creates nothing. `new` refuses to run without --confirmed, which
holds the user's answer in their words; it is written into the new state.md as gate G0.
"""

import json
import re
from datetime import date
from pathlib import Path

KIT_ROOT = Path(__file__).resolve().parents[1]
PROJECTS_ROOT = KIT_ROOT.parent                     # .../Claude Project
TEMPLATES = Path(__file__).resolve().parent / "templates"
SHARED_FOLDER = "small parts"
SCOPE_CONFIG = Path.home() / ".fusion-mcp" / "config.json"
OWN_DIRS = ["parts/purchased", "parts/custom", "assembly", "sim", "tests", "exports", "renders", "logs"]


def slug(name):
    return re.sub(r"[^a-z0-9]+", "_", name.lower()).strip("_")


def propose(name, purchased=0, custom=1, firmware=False, part_of=None, revisions_expected=True):
    """Recommend where a new piece of work should live. Returns {"where", "project", "reasons", "alternatives"}."""
    reasons = []
    if part_of:
        where = "inside"
        reasons.append("it attaches to the existing build '%s' and should be checked against that assembly" % part_of)
        if purchased or firmware:
            reasons.append("note: it brings %s; if it grows into its own assembly, give it its own folder instead" % (
                " and ".join(x for x in ("%d bought part(s)" % purchased if purchased else "", "firmware" if firmware else "") if x)))
    elif purchased or firmware or custom > 1:
        where = "own"
        if purchased:
            reasons.append("%d bought part(s) need their own reference models and interface files" % purchased)
        if custom > 1:
            reasons.append("%d printed parts form an assembly with its own checks" % custom)
        if firmware:
            reasons.append("firmware needs its own build, pin map and tests")
    elif revisions_expected:
        where = "own"
        reasons.append("a single part, but with a brief, requirements and revisions worth tracking on their own")
    else:
        where = "shared"
        reasons.append("a single one-off printed part with nothing bought and no firmware")
    options = {"own": "own folder '%s' under Claude Project (own CLAUDE.md + state.md)" % name,
               "inside": "a part folder inside an existing project",
               "shared": "a folder under '%s' (shared CLAUDE.md, own state.md)" % SHARED_FOLDER}
    return {"name": name, "where": where, "project": part_of, "reasons": reasons,
            "alternatives": {k: v for k, v in options.items() if k != where}, "recommended": options[where]}


def _render(template, values):
    text = (TEMPLATES / template).read_text(encoding="utf-8")
    for key, value in values.items():
        text = text.replace("{{%s}}" % key, str(value))
    left = re.findall(r"\{\{(\w+)\}\}", text)
    if left:
        raise KeyError("template %s has unfilled fields: %s" % (template, sorted(set(left))))
    return text


def _write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        raise FileExistsError("%s already exists; nothing was overwritten" % path)
    path.write_text(text, encoding="utf-8", newline="\n")


def add_scope_folder(cloud_folder, config=SCOPE_CONFIG):
    """Allow the Fusion add-in's scope guard to work in a build's cloud folder (keeps the existing ones)."""
    data = {}
    if config.is_file():
        data = json.loads(config.read_text(encoding="utf-8"))
    scope = data.setdefault("scope", {"enabled": True, "folders": []})
    if cloud_folder not in scope["folders"]:
        scope["folders"].append(cloud_folder)
    config.parent.mkdir(parents=True, exist_ok=True)
    config.write_text(json.dumps(data, indent=1), encoding="utf-8")
    return scope["folders"]


def new(name, where, confirmed, project=None, firmware=False, cloud_folder=None, goal="(write the goal here)", root=PROJECTS_ROOT,
        scope_config=SCOPE_CONFIG):
    """Create the folder and its starting files. Returns {"folder", "created", "gate"}."""
    if not confirmed or len(confirmed.strip()) < 8:
        raise PermissionError("Gate G0: the user must confirm where this lives first. Pass confirmed='<their answer and the date>'.")
    if where not in ("own", "inside", "shared"):
        raise ValueError("where must be own, inside or shared")
    root = Path(root)
    today = date.today().isoformat()
    gate = "| G0 folder | %s | %s | %s |" % (today, {"own": "own folder", "inside": "inside '%s'" % project, "shared": "shared '%s'" % SHARED_FOLDER}[where], confirmed.strip())
    values = {"NAME": name, "SLUG": slug(name), "DATE": today, "GOAL": goal, "GATE_ROW": gate, "KIT": "../mechkit",
              "FIRMWARE_LINE": "yes (firmware/, pinmap.json)" if firmware else "none",
              "CLOUD_FOLDER": cloud_folder or "(not created yet)"}
    created = []

    if where == "inside":
        if not project or not (root / project).is_dir():
            raise FileNotFoundError("existing project folder not found: %s" % (root / str(project)))
        folder = root / project / "parts" / "custom" / slug(name)
        _write(folder / "brief.md", _render("brief.md", values))
        _write(folder / "requirements.json", _render("requirements.json", values))
        created = ["brief.md", "requirements.json"]
        note = "\n## New part: %s (%s)\n- Folder: parts/custom/%s (brief.md, requirements.json)\n- Gate log:\n\n| Gate | Date | Decision | Confirmed by |\n|---|---|---|---|\n%s\n" % (
            name, today, slug(name), gate)
        state = root / project / "state.md"
        if state.is_file():
            state.write_text(state.read_text(encoding="utf-8").rstrip("\n") + "\n" + note, encoding="utf-8", newline="\n")
            created.append("../../../state.md (section appended)")
        return {"folder": str(folder), "created": created, "gate": gate}

    if where == "shared":
        base = root / SHARED_FOLDER
        if not (base / "CLAUDE.md").exists():
            _write(base / "CLAUDE.md", _render("CLAUDE.shared.md", values))
            created.append("../CLAUDE.md")
        folder = base / slug(name)
        files = {"state.md": "state.md", "brief.md": "brief.md", "requirements.json": "requirements.json", "project.json": "project.json"}
    else:
        folder = root / name
        files = {"CLAUDE.md": "CLAUDE.md", "state.md": "state.md", "brief.md": "brief.md", "requirements.json": "requirements.json",
                 "project.json": "project.json"}
    if folder.exists() and any(folder.iterdir()):
        raise FileExistsError("%s already exists and is not empty" % folder)
    for target, template in files.items():
        _write(folder / target, _render(template, values))
        created.append(target)
    for d in OWN_DIRS if where == "own" else ["exports", "renders"]:
        (folder / d).mkdir(parents=True, exist_ok=True)
    if firmware:
        _write(folder / "pinmap.json", _render("pinmap.json", values))
        _write(folder / "firmware" / "platformio.ini", _render("platformio.ini", values))
        _write(folder / "firmware" / "src" / "main.cpp", _render("main.cpp", values))
        created += ["pinmap.json", "firmware/platformio.ini", "firmware/src/main.cpp"]
    scope = None
    if cloud_folder:
        scope = add_scope_folder(cloud_folder, scope_config)
    return {"folder": str(folder), "created": created, "gate": gate, "scope_folders": scope}
