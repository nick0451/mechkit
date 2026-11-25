# Fabrication checks and drawings

MechKit's manufacturability checks, flat patterns and drawings are done by text-to-cad's `cad` library
(MIT, https://github.com/earthtojake/text-to-cad), installed as a pinned dependency. MechKit wraps it in
`mechkit/dfm.py` and `mechkit/drawing.py` so the results fit MechKit's gates and reports. Only the library is used:
the `cad` command, its server, its auto-update and its agent-app installer are not run, and `DO_NOT_TRACK=1` is set.

## Checks (`mechkit/dfm.py`)

| Call | What it checks | Give it |
|---|---|---|
| `printing({name: solid}, material="petg", technology="fdm", nozzle=0.4, build_volume=(256, 256, 256))` | walls, overhangs, bed contact, bridges, build volume | each part IN ITS PRINT ORIENTATION on z = 0 |
| `geometry({name: solid})` | valid B-rep, no self-intersections, a boolean accepts it | every solid of the build |
| `laser_dxf({name: path}, material=, thickness=, kerf=)` | closed contours, double cuts, holes / slots / webs against kerf and thickness | the cut files (DXF, mm) |
| `sheet_metal({name: solid}, thickness=, k_factor=, bend_radius=)` | bends, flanges, holes near bends | bent sheet parts |
| `flat_pattern(solid, out, thickness=, k_factor=)` | writes the flat pattern DXF (bend allowance BA = angle x (r + K t)) | a bent sheet part |
| `write_dxf(face, out)` | writes a flat outline as a DXF cut file, layer CUT | a 2D face in XY |

Each part's result is `{status: pass | fail | not evaluated, errors, warnings, issues[], summary}`; each issue names
its rule, the face or entity, the measured value and limit, and the published source. `write_report(folder, {...})`
writes `dfm_report.json` beside the exports; `problems(report)` gives the lines a build prints as PROBLEM.

How to treat results:
- **error**: a rule's feasibility limit is broken. Fix the model, or put it to the person at G3 with the finding.
- **warning**: a recommendation missed. List it in the pre-print review; the person decides.
- **not evaluated**: the check could not judge. Never read it as clear.
- The rules are general guidance (Protolabs Network / Hubs design guides and similar), not this printer's limits.
  Calibrated print behaviour comes from test prints, as for materials.

Requirement checks in `requirements.json`: `{"type": "dfm_ok", "process": "printing" | "sheet" | "laser",
"max_warnings": N}` and `{"type": "geometry_sound"}`, both read `dfm_report.json`.

## Drawings (`mechkit/drawing.py`)

`part_sheet(solid, title, part_number=, material=, source=)` makes one sheet: top, front, right and isometric views,
overall sizes, and hole callouts for full round holes found in the solid (through, blind, from the far side, stepped).
`write([sheets], "drawings.pdf")` writes one PDF; a sheet that does not fit drops to the next standard scale.
Every number is measured from the solid: never type a dimension onto a sheet. The sheet states that no tolerances
are given; tolerances for a printed part come from a fit test, not from the drawing.

## More checks in `mechkit/dfm.py`

`cnc({name: solid}, material=, axes=, tools=)` and `molding({name: solid}, material=, pull=)` report like `printing`.
`clearance(a, b)` gives the smallest gap between two solids and where; `mass({name: (solid, g/cm3)})` gives mass and
centre of mass of SOLID material (a printed part weighs less: weigh it and record that as measured).

## Standard hardware (`mechkit/hardware.py`, bd_warehouse, Apache-2.0)

`screw("M3-0.5", 10)` (ISO 4762; also `pan_head`, `countersunk`, `button_head`) and `insert("M3-0.5", maker="CNCKitchen")`
return `(solid, facts)`: dimensions tagged stated with their source, clearance and tap hole sizes, an insert's hole
size and the maker's product reference. Bearings are not offered (they do not build with this kernel version).

## Motion (`mechkit/motion.py`, MuJoCo, Apache-2.0)

`stability({name: (solid, grams)}, [{"action", "at", "direction", "force_n"}], friction=0.5)` stands the thing on a
floor and finds, per push, the force at which it tips or slides (bisection over rigid-body simulations; each part
collides as its convex hull). `write_report` saves `stability.json`, which requirement `stability_min_ratio` reads.
Checked against hand formulas to 3 %. `sweep(assembly, joint, values)` poses a build123d assembly (build123d joints,
labelled parts) through a joint's travel and lists overlaps; `first_collision(rows)` gives where it first hits.

## Electronics

Board checks, edits and the fabrication package have their own page: [electronics.md](electronics.md).

## Slicing (`mechkit/slicer.py`, Bambu Studio or OrcaSlicer)

`estimates(project, version, printer, process, filament)` slices every STL of the export with the installed slicer
(`MECHKIT_SLICER` to choose one) and writes `print_estimates.json` (time, grams, layers, the settings used), which
requirements `print_time_max_h`, `filament_max_g` and `parts_fit_bed` read. Preset names are the slicer's own, e.g.
"Bambu Lab A1 0.4 nozzle", "0.20mm Standard @BBL A1", "Bambu PETG Basic @BBL A1". It never sends a print.

## Not adopted

URDF / SRDF robot descriptions, Blender renders, and the library's persistent build engine (it belongs to its server, which MechKit does not run; MechKit builds are
plain scripts that take seconds).
