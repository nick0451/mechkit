---
name: mechkit
description: Designs physical things end to end with a person deciding at gates - parts as build123d Python, bought parts as tagged data, overlap and requirement checks, manufacturability checks (3D printing, laser / sheet cut files), structural simulation with CalculiX, engineering drawings, and MechKit Studio's exploded views and printable assembly guides. Use when the person wants a part, enclosure, bracket, mount or multi-part build designed, checked, simulated or documented for making.
license: MIT
metadata:
  repository: nick0451/mechkit
---

# MechKit
Instructions for an AI coding agent working with this kit. MechKit takes a mechanical idea to checked, simulated,
ready-to-make parts (and firmware), with a person deciding at gates. The agent does the work between gates.

Geometry is authored headless, as Python (build123d). MechKit Studio (`python -m mechkit studio`) is how the person
looks at the result: 3D view, exploded view, parts, and the printed exploded sheet and assembly guide.

If the folder has a `CLAUDE.local.md` or a `state.md`, read them first: they hold this machine's and this person's
specifics and the current status. Keep `state.md` current as you work (it is not tracked by git).

## Starting any new build or part: gate G0
Before creating anything, confirm with the person WHERE it lives. Never skip this, even for a small part.
1. `uv run python -m mechkit propose --name "..." [--purchased N] [--custom N] [--firmware] [--part-of "project"] [--one-off]`
   prints a recommendation with reasons. It creates nothing.
2. Ask the person: own folder / inside an existing project / shared small-parts folder.
3. `uv run python -m mechkit new --name "..." --where own|inside|shared --confirmed "<their answer + date>" ...`
   creates the folder with its own `CLAUDE.md` and `state.md`. It refuses without `--confirmed`.

## Gates in every build
| Gate | Stop for |
|---|---|
| G0 | the brief, and where the work lives |
| G1 | concept choice: 2-3 options with pictures and a risk list |
| G2 | anything that must be bought |
| G3 | pre-print review: report, requirement results, small fit coupons before large parts |
| G4 | flashing firmware or any other action on real hardware |

Asked as questions, logged in the build's `state.md`. Between gates, work alone within the budget stated at the last
gate; stop early if the same requirement fails twice.

## Environment
- Run everything with `uv run ...` from this folder (Python 3.12, pinned in `.python-version`).
- CalculiX solver: looked for in `$MECHKIT_CCX`, else `tools/ccx/**/ccx*.exe` (`mechkit.sim.ccx.find_ccx`). It is not
  included; downloads need the person's approval.
- Web app: `studio/web` (`npm install`, `npm run build`; rebuild after any change under `studio/web/src`).

## What is here
```
mechkit/project.py            propose() / new(): spin-up with the folder gate; templates in mechkit/templates/
mechkit/requirements.py       requirements.json checked against report files
mechkit/kernel/b3d.py         headless geometry helpers (build123d): prisms, holes, body_info, overlap_volume, STEP / STL
mechkit/dfm.py                manufacturability + geometry checks via text-to-cad's `cad` library (see references/fabrication.md)
mechkit/drawing.py            engineering drawings (PDF), every number measured from the solid
mechkit/revisions.py          which export revision is newest (by name)
mechkit/hardware.py           standard screws and heat-set inserts as solids + tagged dimensions (bd_warehouse)
mechkit/motion.py             tipping / sliding under a push (MuJoCo) -> stability.json; mechanism travel collisions
mechkit/electronics.py        KiCad: DRC / ERC, board edits and routing, a board's outline and holes as an interface,
                              the fabrication package for a manufacturer (see references/electronics.md)
mechkit/slicer.py             slices the print files with the installed Bambu Studio / OrcaSlicer -> print_estimates.json
mechkit/sim/mesh.py           gmsh -> 10-node tetrahedra (CalculiX C3D10) + surface triangles
mechkit/sim/ccx.py            input deck writer, solver runner with the repeat guard, result reader (mm, N, MPa)
mechkit/sim/loadcase.py       sim/loadcases.json: face selectors, cases, judgement, sim_report.json
mechkit/sim/picture.py        stress pictures without a window
mechkit/sim/benchmark.py      clamped-beam known-answer test (run after ANY change to the simulation chain)
mechkit/materials.json        material cards, each tagged assumed or calibrated
mechkit/calibration.py        test-bar STLs + the maths that turns sag / break measurements into a material card
mechkit/present/manifest.py   presentation manifest: one item per physical thing, views, assembly steps, guide sections
mechkit/present/layout.py     picture-plane maths and balloon placement
mechkit/present/sheet.py      labelled picture sheets (exploded views with balloons + parts table)
mechkit/present/fusion.py     OPTIONAL, experimental: builds a presentation document in Autodesk Fusion (needs a separate add-in)
mechkit/fusion_export.py      OPTIONAL, experimental: STEP export from an open Fusion document (same add-in)
mechkit/studio/               Studio backend (FastAPI, 127.0.0.1 only): projects, manifest, GLB model
studio/CONTRACT.md            the web app's contract: data shapes, routes, module boundaries, print outputs
studio/web/                   the web app (React + TypeScript + three.js)
examples/monitor-weather-display/   a complete worked example: build script, bought-part data, firmware, outputs
tests/                        plain scripts: `uv run python tests/test_<name>.py` (last line "N checks, M failed")
```
Commands: `python -m mechkit propose | new | check <project> | sim <project> | present <project> --no-fusion | studio`,
`python -m mechkit pcb check | fab | inspect | interface | export | render | stable | kicad-cli`,
`uv run python tests/test_fab.py`, `tests/test_integrations.py`, `tests/test_pcb.py` (adopted capabilities),
`python -m mechkit.sim.benchmark`, `python -m mechkit.calibration make | fit`.

## Rules
1. Every new capability starts with a known-answer spike before anything depends on it.
2. Never guess a dimension. Tag each one **stated** (datasheet / drawing), **measured** (calipers), **scaled** (read
   off a picture) or **assumed**, and ask about assumed ones that matter.
3. Results are tagged like dimensions: **calibrated** (matched to a printed test) or **assumed**. An assumed
   simulation can rank options; it does not approve a design (`requirements.py` enforces this for strength).
   A strength result counts only when it is clean and current: no problems or solver warnings, the mesh sizes agree,
   the simulated STEP file is unchanged (sha256), and a calibrated material card carries a `calibration` record
   (date, bars, print_settings). `mechkit check` exits 0 only when everything passes (1 fail, 2 anything unchecked).
4. Units: mm, N, MPa, grams in reports.
5. Each bought part gets `parts/purchased/<part>/interface.json` (dimensions with tags + how it mounts). Scripts read
   those values; a number from a bought part is never copied into a script.
6. New parts are plain functions of (parameters, inputs) on `mechkit/kernel/b3d.py`. Give bought parts stand-in solids
   so fit can be checked with `b3d.overlap_volume`. It raises when it cannot compute an overlap: report that as a
   problem, never as clear. Revisions are ordered by name (`mechkit/revisions.py`: v0p10 > v0p9), never by file time.
7. Pin assignments live in the project's `pinmap.json` only; the firmware header and the wiring page are generated from it.
8. Presentation: a project's build writes `exports/<version>/presentation/manifest.json` (see the example's
   `present_items`, `present_steps`, `present_guide`). Each assembly step says where its picture is taken from and how
   its parts are pulled out, along the way they really go on.
9. Simulation chain facts that were learned the hard way:
   - gmsh orders the last two mid-edge nodes of a 10-node tetrahedron differently from CalculiX (`GMSH_TO_CCX_TET10`).
   - A uniform force on 6-node triangles goes on the mid-edge nodes only (one third each), nothing on the corners.
   - The solver once returned a wrong answer for an identical input (4 threads, ccx 2.24 on Windows). Keep the guard
     in `StaticCase.run` (1 thread, solve twice, compare); never bypass it for results that go into a report.
   - A stress peak that changes more than 15 % between two mesh sizes sits on a sharp corner: report it as such; do
     not call it a pass or a fail on that number alone.
   - Before proposing a fix for a stress peak, read `peak_stress_at` and test the fix headless.
10. build123d: a sketch extrudes toward -Z if its points are given clockwise (place solids by their bounding box);
    `Rot(X=90)` maps local y to z and z to -y.
11. After a change: this kit's tests, the beam benchmark, `npm test` and `npm run build`.
12. Buying, ordering, flashing, publishing, deleting: always the person's decision.
13. Fabrication checks (`mechkit/dfm.py`, details in [references/fabrication.md](references/fabrication.md)): run the
    printing check on each part IN ITS PRINT ORIENTATION, the geometry check on every solid, and the laser check on
    every cut file. Their rules are general published guidance, not this printer's or a shop's limits: an error is a
    problem to fix or put to the person at G3; warnings go in the pre-print review. A check that could not run is
    "not evaluated", never clear. Requirements can use `dfm_ok` and `geometry_sound`.
14. Drawings (`mechkit/drawing.py`) show only numbers measured from the model; never type a dimension onto a sheet.
15. Screws and inserts come from `mechkit/hardware.py`, not hand-made cylinders: its numbers are tagged stated with the
    standard or maker as source. An insert's hole is `facts["hole_d"]` (the maker's), never the thread's tap drill.
16. `mechkit/motion.py`: masses and friction are assumed until weighed / measured, and the report says so. Push forces
    (`force_n`) are the person's numbers or tagged assumed. A thing that moves with no push is a problem, not a result.
17. Board design: read [references/electronics.md](references/electronics.md) first. Checks and exports use any
    kicad-cli; edits need the `kicad` extra (a KiCad nightly) and save in its format, with a stable-format copy kept
    beside the board. `pcb fab` refuses on rule-check errors unless the person said to go ahead; ordering is G2.
    `mechkit/slicer.py` estimates only: it never sends a print (G4 is the person's).
18. Programs on the machine are found, never installed silently: `MECHKIT_CCX`, `MECHKIT_KICAD_CLI`, `MECHKIT_SLICER`.
    When one is missing the result is "not evaluated" and the build says which.
