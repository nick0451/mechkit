"""Phase 0 tests: project spin-up with the folder gate, and the requirements checker. No Fusion, no solver.

    uv run python tests/test_phase0.py

Everything is created in a temporary folder; the real `Claude Project` folders and ~/.fusion-mcp are not touched.
The requirements checker is also run (read-only) on a real project's newest export when MECHKIT_TEST_EXPORT_PROJECT
names one (a project folder with stability / print-estimate reports); skipped otherwise.
"""

import json
import os
import shutil
import sys
import tempfile
from pathlib import Path

KIT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(KIT))
from mechkit import project, requirements, revisions  # noqa: E402

results = []


def check(name, cond, detail=""):
    results.append(bool(cond))
    print("  %-4s %s%s" % ("ok" if cond else "FAIL", name, "" if cond else "   <-- " + str(detail)[:300]))


def raises(exc, fn):
    try:
        fn()
    except exc:
        return True
    return False


def main():
    print("where should it live? (recommendation only)")
    p = project.propose("Fan mount", purchased=2, custom=3, firmware=True)
    check("bought parts + several printed parts + firmware -> own folder, with 3 reasons", p["where"] == "own" and len(p["reasons"]) == 3, p)
    p = project.propose("Cable clip", part_of="Desk lamp")
    check("attaches to an existing build -> inside that project", p["where"] == "inside" and p["project"] == "Desk lamp", p)
    p = project.propose("Hook", revisions_expected=False)
    check("one-off printed part, nothing bought -> shared small-parts folder", p["where"] == "shared", p)
    p = project.propose("Bracket")
    check("single part with a brief worth tracking -> own folder", p["where"] == "own" and set(p["alternatives"]) == {"inside", "shared"}, p)

    tmp = Path(tempfile.mkdtemp(prefix="mechkit_phase0_"))
    cfg = tmp / "home" / ".fusion-mcp" / "config.json"
    cfg.parent.mkdir(parents=True)
    cfg.write_text(json.dumps({"scope": {"enabled": True, "folders": ["Admin Project/Existing build"]}, "other": 1}))
    try:
        print("the gate")
        check("no confirmation -> nothing is created", raises(PermissionError, lambda: project.new("Fan mount", "own", "", root=tmp, scope_config=cfg))
              and not (tmp / "Fan mount").exists())
        check("a one-word confirmation is not accepted", raises(PermissionError, lambda: project.new("Fan mount", "own", "ok", root=tmp, scope_config=cfg)))

        print("own folder")
        r = project.new("Fan mount", "own", "user, 2026-11-23: give it its own folder", firmware=True, cloud_folder="Admin Project/Fan mount",
                        goal="Hold a 120 mm fan on the desk edge", root=tmp, scope_config=cfg)
        folder = Path(r["folder"])
        expected = ["CLAUDE.md", "state.md", "brief.md", "requirements.json", "project.json", "pinmap.json", "firmware/platformio.ini", "firmware/src/main.cpp"]
        check("CLAUDE.md, state.md, brief, requirements, project and firmware files exist", all((folder / f).is_file() for f in expected), r["created"])
        check("working folders exist", all((folder / d).is_dir() for d in project.OWN_DIRS))
        state = (folder / "state.md").read_text(encoding="utf-8")
        claude = (folder / "CLAUDE.md").read_text(encoding="utf-8")
        check("state.md records gate G0 with the user's words", "| G0 folder |" in state and "give it its own folder" in state and "own folder" in state)
        check("CLAUDE.md names the build, its goal, the gates and the kit", all(x in claude for x in ("Fan mount", "Hold a 120 mm fan", "| G3 |", "../mechkit")))
        check("no template field left unfilled", not any("{{" in (folder / f).read_text(encoding="utf-8") for f in expected))
        pj = json.loads((folder / "project.json").read_text(encoding="utf-8"))
        rq = json.loads((folder / "requirements.json").read_text(encoding="utf-8"))
        check("project.json and requirements.json are valid and named", pj["name"] == "Fan mount" and pj["cloud_folder"] == "Admin Project/Fan mount"
              and rq["project"] == "Fan mount" and len(rq["requirements"]) >= 3)
        scope = json.loads(cfg.read_text())
        check("the build's cloud folder was added to the Fusion scope; the old one and other settings kept",
              scope["scope"]["folders"] == ["Admin Project/Existing build", "Admin Project/Fan mount"] and scope["other"] == 1, scope)
        check("creating it again refuses and overwrites nothing", raises(FileExistsError, lambda: project.new(
            "Fan mount", "own", "user, 2026-11-23: again", root=tmp, scope_config=cfg)) and "give it its own folder" in (folder / "state.md").read_text(encoding="utf-8"))
        res, reports = requirements.check_project(folder)
        check("a fresh project: nothing fails, nothing passes silently", reports is None and all(x["status"] in ("not evaluated", "manual") for x in res), res)

        print("inside an existing project")
        host = tmp / "Host build"
        host.mkdir()
        (host / "state.md").write_text("# Project state\n\nexisting notes\n", encoding="utf-8")
        r = project.new("Cable clip", "inside", "user, 2026-11-23: part of Host build", project="Host build", root=tmp, scope_config=cfg)
        part = host / "parts" / "custom" / "cable_clip"
        hs = (host / "state.md").read_text(encoding="utf-8")
        check("part folder with brief + requirements inside the host", (part / "brief.md").is_file() and (part / "requirements.json").is_file())
        check("host state.md keeps its notes and gains the new part + gate", "existing notes" in hs and "New part: Cable clip" in hs and "| G0 folder |" in hs)
        check("no CLAUDE.md is created inside a host project", not (part / "CLAUDE.md").exists())
        check("an unknown host project is refused", raises(FileNotFoundError, lambda: project.new("X part", "inside", "user, 2026-11-23: yes", project="Nope", root=tmp)))

        print("shared small-parts folder")
        r = project.new("Hook", "shared", "user, 2026-11-23: small parts is fine", root=tmp, scope_config=cfg)
        r2 = project.new("Peg", "shared", "user, 2026-11-23: small parts is fine", root=tmp, scope_config=cfg)
        shared = tmp / project.SHARED_FOLDER
        check("one shared CLAUDE.md, one state.md per part", (shared / "CLAUDE.md").is_file() and (shared / "hook" / "state.md").is_file()
              and (shared / "peg" / "state.md").is_file() and "../CLAUDE.md" in r["created"] and "../CLAUDE.md" not in r2["created"])
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    print("check exit codes: unchecked is never success")
    rs = lambda *s: [{"status": x} for x in s]  # noqa: E731
    check("all pass -> 0", requirements.exit_code(rs("pass", "pass")) == 0)
    check("any fail -> 1", requirements.exit_code(rs("pass", "fail", "not evaluated")) == 1)
    check("NEGATIVE: not evaluated -> 2, not 0", requirements.exit_code(rs("pass", "not evaluated")) == 2)
    check("NEGATIVE: waiting for a person -> 2, not 0", requirements.exit_code(rs("pass", "manual")) == 2)

    print("which revision is newest (by name, never by file time)")
    tmp = Path(tempfile.mkdtemp(prefix="mechkit_rev_"))
    try:
        for name in ("v0p9", "v0p10", "v0p2", "notes"):
            (tmp / "exports" / name).mkdir(parents=True)
        (tmp / "exports" / "v0p9" / "touched").write_text("newest file time")
        check("v0p10 is newer than v0p9 and v0p2", revisions.newest(tmp).name == "v0p10", revisions.newest(tmp))
        check("export_v26 style names count too", revisions.key("export_v26") > revisions.key("export_v9"))
        check("unnumbered folders come last", [n for n, _ in revisions.folders(tmp)][-1] == "notes")
        check("requirements use the same rule", requirements.newest_export(tmp).name == "v0p10")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    print("overlap checks fail closed")
    from mechkit.kernel import b3d
    import build123d as bd
    check("two boxes sharing a 0.5 mm cube -> 0.125 mm3", abs(b3d.overlap_volume(bd.Box(2, 2, 2), bd.Pos(1.5, 1.5, 1.5) * bd.Box(2, 2, 2)) - 0.125) < 1e-6)
    invalid = type("Invalid", (), {"is_valid": False})()
    broken = type("Broken", (), {"is_valid": True, "__and__": lambda self, other: 1 / 0})()
    check("NEGATIVE: an invalid solid raises, it is not 'no overlap'", raises(b3d.GeometryCheckError, lambda: b3d.overlap_volume(invalid, bd.Box(1, 1, 1))))
    check("NEGATIVE: a failed boolean raises, it is not 'no overlap'", raises(b3d.GeometryCheckError, lambda: b3d.overlap_volume(broken, bd.Box(1, 1, 1))))

    print("requirements against real reports (read-only)")
    env = os.environ.get("MECHKIT_TEST_EXPORT_PROJECT", "")
    six = Path(env) if env else None
    reports = requirements.newest_export(six) if six and six.is_dir() else None
    if reports and (reports / "stability.json").is_file():
        reqs = [
            {"id": "R1", "text": "does not tip", "check": {"type": "stability_min_ratio", "min": 1.5}},
            {"id": "R2", "text": "really does not tip", "check": {"type": "stability_min_ratio", "min": 3.0}},
            {"id": "R3", "text": "prints within a day", "check": {"type": "print_time_max_h", "max": 24}},
            {"id": "R4", "text": "prints within a morning", "check": {"type": "print_time_max_h", "max": 4}},
            {"id": "R5", "text": "under 1 kg of filament", "check": {"type": "filament_max_g", "max": 1000}},
            {"id": "R6", "text": "fits a 256 bed", "check": {"type": "parts_fit_bed", "bed_mm": 256}},
            {"id": "R7", "text": "fits a 180 bed", "check": {"type": "parts_fit_bed", "bed_mm": 180}},
            {"id": "R8", "text": "strong enough", "check": {"type": "strength_min_safety_factor", "min": 3}},
            {"id": "R9", "text": "looks good", "check": {"type": "manual"}},
            {"id": "R10", "text": "signed off", "check": {"type": "manual"}, "result": {"status": "pass", "by": "user", "date": "2026-11-23"}},
            {"id": "R11", "text": "typo in the check", "check": {"type": "no_such_check"}},
        ]
        got = {r["id"]: r["status"] for r in requirements.evaluate(reqs, reports)}
        want = {"R1": "pass", "R2": "fail", "R3": "pass", "R4": "fail", "R5": "pass", "R6": "pass", "R7": "fail", "R8": "not evaluated",
                "R9": "manual", "R10": "pass", "R11": "not evaluated"}
        check("11 requirements judged from %s" % reports.name, got == want, {k: (got[k], want[k]) for k in want if got[k] != want[k]})
    else:
        print("  (MECHKIT_TEST_EXPORT_PROJECT not set or has no reports: skipped)")

    print("\n%d checks, %d failed" % (len(results), results.count(False)))
    sys.exit(1 if False in results else 0)


if __name__ == "__main__":
    main()
