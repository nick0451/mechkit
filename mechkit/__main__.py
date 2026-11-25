"""mechkit command line.

    python -m mechkit propose --name NAME [--purchased N] [--custom N] [--firmware] [--part-of PROJECT] [--one-off]
    python -m mechkit new --name NAME --where own|inside|shared --confirmed "TEXT" [--project P] [--firmware]
                          [--cloud-folder "Admin Project/NAME"] [--goal "TEXT"]
    python -m mechkit check PROJECT_FOLDER [--reports FOLDER]       exit 0 all pass, 1 a failure, 2 something unchecked
    python -m mechkit sim PROJECT_FOLDER [--refresh] [--no-pictures]     run sim/loadcases.json -> sim/reports/sim_report.json
    python -m mechkit present PROJECT_FOLDER [--version V] [--no-fusion] [--no-save]
                          labelled picture sheets + the Fusion presentation document, from the build's manifest
    python -m mechkit studio [--port 8765] [--no-browser] [--projects DIR ...]
                          the local web viewer: exploded view, parts table, printable exploded sheet and assembly guide
    python -m mechkit.sim.benchmark
"""

import argparse
import json
import sys

from . import project, requirements


def main():
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    p = argparse.ArgumentParser(prog="mechkit", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)
    a = sub.add_parser("propose")
    a.add_argument("--name", required=True)
    a.add_argument("--purchased", type=int, default=0)
    a.add_argument("--custom", type=int, default=1)
    a.add_argument("--firmware", action="store_true")
    a.add_argument("--part-of")
    a.add_argument("--one-off", action="store_true")
    b = sub.add_parser("new")
    b.add_argument("--name", required=True)
    b.add_argument("--where", required=True, choices=["own", "inside", "shared"])
    b.add_argument("--confirmed", default="")
    b.add_argument("--project")
    b.add_argument("--firmware", action="store_true")
    b.add_argument("--cloud-folder")
    b.add_argument("--goal", default="(write the goal here)")
    c = sub.add_parser("check")
    c.add_argument("folder")
    c.add_argument("--reports")
    d = sub.add_parser("sim")
    d.add_argument("folder")
    d.add_argument("--refresh", action="store_true")
    d.add_argument("--no-pictures", action="store_true")
    e = sub.add_parser("present")
    e.add_argument("folder")
    e.add_argument("--version")
    e.add_argument("--no-fusion", action="store_true", help="only the picture sheets")
    e.add_argument("--no-save", action="store_true", help="build the Fusion document but leave saving to the user")
    f = sub.add_parser("studio", help="local web viewer (127.0.0.1): exploded view, parts table, printable assembly guide")
    f.add_argument("--port", type=int, default=8765)
    f.add_argument("--no-browser", action="store_true", help="do not open the browser")
    f.add_argument("--projects", action="append", metavar="DIR",
                   help="a folder whose sub-folders are projects (repeatable). Default: $MECHKIT_PROJECTS, else beside the kit and its examples/")
    args = p.parse_args()

    if args.cmd == "propose":
        r = project.propose(args.name, args.purchased, args.custom, args.firmware, args.part_of, not args.one_off)
        print("Recommended: %s" % r["recommended"])
        for reason in r["reasons"]:
            print("  because %s" % reason)
        print("Other choices: %s" % "; ".join(r["alternatives"].values()))
        print("Nothing was created. Ask the user (gate G0), then run `new` with their answer in --confirmed.")
    elif args.cmd == "new":
        try:
            r = project.new(args.name, args.where, args.confirmed, args.project, args.firmware, args.cloud_folder, args.goal)
        except (PermissionError, FileExistsError, FileNotFoundError) as e:
            sys.exit("NOT CREATED: %s" % e)
        print(json.dumps(r, indent=1))
    elif args.cmd == "sim":
        from pathlib import Path

        from .sim import loadcase
        folder = Path(args.folder).resolve()
        cases = folder / "sim" / "loadcases.json"
        if args.refresh:
            from . import fusion_export
            done = set()
            for part in json.loads(cases.read_text(encoding="utf-8"))["parts"]:
                src = part.get("source")
                if src and part["step"] not in done:
                    info = fusion_export.component_step(src["document"], src["component"], folder / part["step"])
                    done.add(part["step"])
                    print("exported %s from %s v%s%s" % (part["step"], src["document"], info["version"], " (UNSAVED changes)" if info["modified"] else ""))
        report = loadcase.run_file(cases, pictures=not args.no_pictures)
        loadcase.print_report(report)
        sys.exit(1 if report["problems"] else 0)
    elif args.cmd == "present":
        from pathlib import Path

        from .present import manifest, sheet
        folder = Path(args.folder).resolve()
        data = manifest.load(manifest.find(folder, args.version))
        print("%s %s: %d items, %d table rows, %d views" % (data["project"], data["version"], len(data["parts"]), len(data["table"]), len(data["views"])))
        for f in sheet.make(data, folder / "renders" / "presentation"):
            print("  wrote", f)
        if not args.no_fusion:
            from .present import fusion
            try:
                report = fusion.send(data, folder / "renders" / "presentation", save=not args.no_save)
            except RuntimeError as ex:
                sys.exit("FUSION DOCUMENT NOT BUILT: %s" % ex)
            (folder / "logs").mkdir(exist_ok=True)
            (folder / "logs" / ("present_%s.json" % data["version"])).write_text(json.dumps(report, indent=1), encoding="utf-8")
            print("Fusion document %s (%s): %d parts exploded, %d trace lines, %d labels%s" % (
                report["document"], report["state"], report["placed"], report["traces"], report["labels"],
                "; " + report["save"]["how"] if report.get("save") else "; NOT saved"))
            for n in report["notes"]:
                print("  note:", n)
            for pr in report["problems"]:
                print("  PROBLEM:", pr)
            sys.exit(1 if report["problems"] else 0)
    elif args.cmd == "studio":
        from . import studio
        sys.exit(studio.serve(port=args.port, open_browser=not args.no_browser, projects_root=args.projects))
    elif args.cmd == "check":
        results, reports = requirements.check_project(args.folder, args.reports)
        requirements.print_results(results, reports)
        code = requirements.exit_code(results)
        if code == 2:
            print("NOT APPROVED: some requirements are not evaluated or still waiting for a person (exit 2)")
        sys.exit(code)


if __name__ == "__main__":
    main()
