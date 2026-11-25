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

## Not adopted (yet)

Slicing (OrcaSlicer), MuJoCo / URDF / SRDF robot descriptions, KiCad boards, CNC and moulding checks, Blender
renders, and the library's persistent build engine. Each is available in the same library and can be wrapped the same
way when a project needs it.
