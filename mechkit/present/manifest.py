"""The presentation manifest: what to show, written by a project's build next to its print files. Lengths in mm.

    from mechkit.present import manifest
    items = [manifest.item("Pod", solid, label=2, kind="printed", description="...", colour="#2b2d31", explode=(0, 46, 8)), ...]
    views = [manifest.view("Front", eye, target), manifest.view("Exploded", eye, target, group="exploded")]
    path = manifest.write(project_dir, "v0p9", "Monitor weather display", items, views)

An ITEM is one physical thing in its assembled position (world frame). Items that are the same kind of thing share a
`label` number and a `part` name (three M3 bolts = three items, one row in the parts table).
`kind`: printed | bought | hardware | reference (reference = context only, e.g. the monitor: no label, not exploded).
`explode`: how far the item moves in the exploded view, as a world vector.

`steps` (optional): the assembly order, as  manifest.step("Title", "What to do.", add=[item keys]) . Every item that is
not a reference must be added in exactly one step. The viewer's assembly guide is made from it.
A step may say how its picture is taken: `view=(eye, target)` (only the direction matters) and `pull={key: (dx, dy, dz)}`,
how far each named item is drawn away from its seat, in mm, ALONG THE WAY IT GOES ON (which is often not its direction in
the overall exploded view: an insert that is pressed in from behind is pulled backward). Items not named stay seated.
`guide` (optional): the printed guide's other pages, made with manifest.guide(...): tools, consumables, print settings,
wiring, commissioning.

Written to  exports/<version>/presentation/manifest.json  with one STEP file per item beside it.
"""

import json
import re
from pathlib import Path

KINDS = ("printed", "bought", "hardware", "reference")
MADE = {"printed": "3D printed", "bought": "bought", "hardware": "hardware", "reference": "not part of the build"}


def item(key, solid, label, kind, description, colour, name=None, part=None, part_number="", material="", explode=(0.0, 0.0, 0.0),
         count=1, opacity=1.0):
    """One thing to show. key: unique, file-safe. name: shown on the component (default key). part: parts-table name (default name).
    count: how many this item adds to its row's quantity (0 for a second piece of something already counted)."""
    return {"key": key, "solid": solid, "label": int(label), "kind": kind, "description": description, "colour": colour,
            "name": name or key, "part": part or name or key, "part_number": part_number, "material": material,
            "explode": [float(c) for c in explode], "count": int(count), "opacity": float(opacity)}


def view(name, eye, target, group="assembled", up=(0.0, 0.0, 1.0)):
    """A named view. group: assembled | exploded (exploded views are given relative to the exploded group's own position)."""
    return {"name": name, "eye": [float(c) for c in eye], "target": [float(c) for c in target], "up": [float(c) for c in up], "group": group}


def step(title, text, add, view=None, pull=None):
    """One assembly step: the items (keys) that go on in this step, and what to do with them.

    view: (eye, target) or (eye, target, up): where the step's picture is taken from. pull: {key: (dx, dy, dz)} mm."""
    out = {"title": title, "text": text, "add": list(add), "view": None, "pull": None}
    if view is not None:
        out["view"] = {"eye": [float(c) for c in view[0]], "target": [float(c) for c in view[1]],
                       "up": [float(c) for c in (view[2] if len(view) > 2 else (0.0, 0.0, 1.0))]}
    if pull is not None:
        out["pull"] = {k: [float(c) for c in v] for k, v in pull.items()}
    return out


def guide(tools=(), consumables=(), printing=None, wiring=None, commissioning=(), notes=()):
    """The printed guide's pages besides the steps. Everything is optional; leave out what a project does not have.

    tools, consumables: [(name, note)]                       note may be ""
    printing: {"settings": [(name, value)], "parts": [(part, how it lies on the bed)], "note": str}
    wiring:   {"title": str, "from": str, "to": str, "wires": [{"from": pin, "to": pad, "signal": str, "note": str}],
               "notes": [str]}                               drawn as a diagram and a table
    commissioning: [{"title": str, "text": str, "checks": [str]}]     after assembly: firmware, tests, inspection
    notes: [str]                                             printed on the "before you start" page
    """
    def pairs(rows, a, b):
        return [{a: r[0], b: r[1] if len(r) > 1 else ""} for r in rows]
    out = {"tools": pairs(tools, "name", "note"), "consumables": pairs(consumables, "name", "note"), "printing": None, "wiring": None,
           "commissioning": [{"title": c["title"], "text": c.get("text", ""), "checks": list(c.get("checks", []))} for c in commissioning],
           "notes": list(notes)}
    if printing:
        out["printing"] = {"settings": pairs(printing.get("settings", []), "name", "value"),
                           "parts": pairs(printing.get("parts", []), "part", "orientation"), "note": printing.get("note", "")}
    if wiring:
        out["wiring"] = {"title": wiring.get("title", "Wiring"), "from": wiring["from"], "to": wiring["to"],
                         "wires": [{"from": w["from"], "to": w["to"], "signal": w.get("signal", ""), "note": w.get("note", "")} for w in wiring["wires"]],
                         "notes": list(wiring.get("notes", []))}
    return out


def _box(solid):
    bb = solid.bounding_box()
    return [[round(bb.min.X, 4), round(bb.min.Y, 4), round(bb.min.Z, 4)], [round(bb.max.X, 4), round(bb.max.Y, 4), round(bb.max.Z, 4)]]


def _union_box(boxes):
    return [[min(b[0][i] for b in boxes) for i in range(3)], [max(b[1][i] for b in boxes) for i in range(3)]]


def moved_box(entry):
    d = entry["explode"]
    return [[entry["bbox"][0][i] + d[i] for i in range(3)], [entry["bbox"][1][i] + d[i] for i in range(3)]]


def exploded_overlaps(items, min_volume=0.5):
    """Pairs of items that still run into each other after their explode moves: [(key, key, mm3)]. Needs the solids.
    mm3 is None when the overlap could not be computed: treat that as a problem, not as clear."""
    import build123d as bd

    from ..kernel.b3d import GeometryCheckError, overlap_volume

    shown = [(it["key"], bd.Pos(*it["explode"]) * it["solid"]) for it in items if it["kind"] != "reference"]
    boxes = [s.bounding_box() for _, s in shown]
    found = []
    for i in range(len(shown)):
        for j in range(i + 1, len(shown)):
            a, b = boxes[i], boxes[j]
            if (a.max.X <= b.min.X or b.max.X <= a.min.X or a.max.Y <= b.min.Y or b.max.Y <= a.min.Y
                    or a.max.Z <= b.min.Z or b.max.Z <= a.min.Z):
                continue
            try:
                vol = overlap_volume(shown[i][1], shown[j][1])
            except GeometryCheckError:
                found.append((shown[i][0], shown[j][0], None))
                continue
            if vol > min_volume:
                found.append((shown[i][0], shown[j][0], round(vol, 2)))
    return found


def validate(data):
    """Problems in a manifest dict (empty list = usable)."""
    problems = []
    keys = [e["key"] for e in data["parts"]]
    for k in sorted({k for k in keys if keys.count(k) > 1}):
        problems.append("key used twice: %s" % k)
    by_label = {}
    for e in data["parts"]:
        if not re.fullmatch(r"[A-Za-z0-9_\-]+", e["key"]):
            problems.append("key is not file-safe: %r" % e["key"])
        if e["kind"] not in KINDS:
            problems.append("%s: unknown kind %r" % (e["key"], e["kind"]))
        if not re.fullmatch(r"#[0-9a-fA-F]{6}", e["colour"]):
            problems.append("%s: colour must be #rrggbb" % e["key"])
        if e["kind"] == "reference":
            if e["label"] != 0 or any(e["explode"]):
                problems.append("%s: a reference item has label 0 and no explode move" % e["key"])
            continue
        if e["label"] < 1:
            problems.append("%s: needs a label number" % e["key"])
        if not e["description"].strip():
            problems.append("%s: needs a description" % e["key"])
        if e["volume_mm3"] <= 0:
            problems.append("%s: empty solid" % e["key"])
        by_label.setdefault(e["label"], set()).add(e["part"])
    for label, parts in sorted(by_label.items()):
        if len(parts) > 1:
            problems.append("label %d is used for different parts: %s" % (label, ", ".join(sorted(parts))))
    if by_label and sorted(by_label) != list(range(1, len(by_label) + 1)):
        problems.append("label numbers must run 1..%d without gaps (found %s)" % (len(by_label), sorted(by_label)))
    steps = data.get("steps") or []
    if steps:
        added = [k for s in steps for k in s["add"]]
        for k in sorted(set(added)):
            if k not in keys:
                problems.append("a step adds %r, which is not an item" % k)
            elif added.count(k) > 1:
                problems.append("%s is added in more than one step" % k)
        refs = {e["key"] for e in data["parts"] if e["kind"] == "reference"}
        for k in sorted(set(added) & refs):
            problems.append("%s is a reference item: it does not belong in a step" % k)
        for k in keys:
            if k not in refs and k not in added:
                problems.append("%s is not added in any step" % k)
        for n, s in enumerate(steps, 1):
            if not s["title"].strip() or not s["add"]:
                problems.append("step %d needs a title and at least one item" % n)
            for k in sorted((s.get("pull") or {})):
                if k not in keys:
                    problems.append("step %d pulls %r, which is not an item" % (n, k))
                elif k in refs:
                    problems.append("step %d pulls the reference item %s" % (n, k))
            v = s.get("view")
            if v and [round(c, 6) for c in v["eye"]] == [round(c, 6) for c in v["target"]]:
                problems.append("step %d: the view's eye and target are the same point" % n)
    g = data.get("guide")
    if g:
        w = g.get("wiring")
        if w and not w["wires"]:
            problems.append("guide: wiring is given but lists no wires")
        for c in g.get("commissioning", []):
            if not c["title"].strip():
                problems.append("guide: a commissioning section has no title")
    names = [v["name"] for v in data["views"]]
    if len(set(names)) != len(names):
        problems.append("view names must be unique")
    for v in data["views"]:
        if v["group"] not in ("assembled", "exploded"):
            problems.append("view %s: unknown group %r" % (v["name"], v["group"]))
    return problems


def table(data):
    """Parts table rows, one per label: {label, part, qty, kind, made, material, part_number, description}."""
    rows = {}
    for e in data["parts"]:
        if e["kind"] == "reference":
            continue
        r = rows.setdefault(e["label"], {"label": e["label"], "part": e["part"], "qty": 0, "kind": e["kind"], "made": MADE[e["kind"]],
                                         "material": e["material"], "part_number": e["part_number"], "description": e["description"]})
        r["qty"] += e["count"]
    return [rows[k] for k in sorted(rows)]


def write(project_dir, version, title, items, views, cloud_folder=None, gap=60.0, steps=None, guide=None):
    """Save every item's STEP file and the manifest. Returns the manifest path. Raises ValueError on a bad manifest.
    Everything is written into a staging folder first and swapped in at the end: a failed or interrupted write leaves
    the previous presentation untouched, never a mix of old and new files."""
    import shutil

    import build123d as bd

    final = Path(project_dir) / "exports" / version / "presentation"
    out = final.with_name("presentation.staging")
    if out.exists():
        shutil.rmtree(out)
    out.mkdir(parents=True)
    parts = []
    for it in items:
        solid = it["solid"]
        bd.export_step(solid, str(out / ("%s.step" % it["key"])))
        c = solid.center()
        e = {k: v for k, v in it.items() if k != "solid"}
        e.update(step="%s.step" % it["key"], volume_mm3=round(solid.volume, 2), bbox=_box(solid),
                 centre=[round(c.X, 4), round(c.Y, 4), round(c.Z, 4)], bodies=len(solid.solids()))
        parts.append(e)
    assembled = _union_box([e["bbox"] for e in parts])
    shown = [e for e in parts if e["kind"] != "reference"]
    exploded = _union_box([moved_box(e) for e in shown]) if shown else assembled
    # The exploded group stands clear of the assembled one so both can be seen in one document: along whichever axis
    # the named views look along LEAST. (Seen live: a level offset put one group in front of the other in some view;
    # views are drawn without perspective, so distance does not get anything out of the way.)
    look = [0.0, 0.0, 0.0]
    for v in views:
        f = [v["target"][i] - v["eye"][i] for i in range(3)]
        n = sum(c * c for c in f) ** 0.5 or 1.0
        look = [look[i] + abs(f[i]) / n for i in range(3)]
    axis = min(range(3), key=lambda i: look[i])
    offset = [0.0, 0.0, 0.0]
    offset[axis] = round(assembled[1][axis] - exploded[0][axis] + gap, 3)
    data = {"about": "Presentation manifest written by mechkit.present.manifest (mm, world frame of the build). Do not edit: rebuild.",
            "project": title, "version": version, "document": "%s_Presentation" % title,
            "cloud_folder": cloud_folder or "Admin Project/%s" % title, "up": [0.0, 0.0, 1.0],
            "assembled_bbox": assembled, "exploded_bbox": exploded, "exploded_offset": offset, "parts": parts, "views": list(views),
            "steps": list(steps or []), "guide": guide}
    data["table"] = table(data)
    problems = validate(data)
    if problems:
        shutil.rmtree(out, ignore_errors=True)
        raise ValueError("presentation manifest is not usable:\n  " + "\n  ".join(problems))
    (out / "manifest.json").write_text(json.dumps(data, indent=1), encoding="utf-8", newline="\n")
    old = final.with_name("presentation.old")
    if old.exists():
        shutil.rmtree(old)
    if final.exists():
        final.rename(old)
    out.rename(final)
    shutil.rmtree(old, ignore_errors=True)
    return final / "manifest.json"


def find(project_dir, version=None):
    """Path of a project's manifest: the given version, else the newest revision that has one (by revision name, see
    mechkit.revisions; file times are not used)."""
    from .. import revisions

    exports = Path(project_dir) / "exports"
    if version:
        return exports / version / "presentation" / "manifest.json"
    found = [d / "presentation" / "manifest.json" for _, d in revisions.folders(project_dir) if (d / "presentation" / "manifest.json").is_file()]
    if not found:
        raise FileNotFoundError("no presentation manifest under %s: run the project's build first" % exports)
    return found[0]


def load(path):
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    problems = validate(data)
    if problems:
        raise ValueError("presentation manifest is not usable:\n  " + "\n  ".join(problems))
    data["folder"] = str(Path(path).parent)
    return data
