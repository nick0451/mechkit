# CLAUDE.md: {{NAME}}

Created {{DATE}} by `mechkit new` (shared tooling: `{{KIT}}`, its conventions are in `{{KIT}}/CLAUDE.md`).

## Goal
{{GOAL}}

The full brief is in [brief.md](brief.md); what "done" means is in [requirements.json](requirements.json).
[state.md](state.md) is the resumable source of truth: read its RESUME HERE section first, and keep it current.

## How this build is run: gates
I work alone between gates and stop at each one for the user's decision (asked as a question, logged in state.md):

| Gate | Stop for |
|---|---|
| G0 | the brief, and where the work lives (done at spin-up) |
| G1 | concept choice: 2-3 options with pictures and a risk list |
| G2 | anything that must be bought |
| G3 | pre-print review: report, requirement results, small fit coupons before large parts |
| G4 | flashing firmware or any other action on real hardware |

Between gates: stay within the budget stated at the last gate; stop early if the same requirement fails twice.

## Rules
1. Units are explicit: scripts in mm; Fusion's API is in cm.
2. Never guess a dimension. Tag each one **stated** (datasheet / drawing), **measured** (the user's calipers),
   **scaled** (read off a picture) or **assumed**, and ask about assumed ones that matter.
3. Each bought part gets `parts/purchased/<part>/interface.json` (dimensions with tags + how it mounts). Scripts read
   those values; a number from a bought part is never copied into a script.
4. Custom parts are scripted and parametric; every build records what it read, so `--stale` can say what to rebuild.
5. Checks return data (`{"problems": [...]}`), and the pipeline judges from data, not printed text.
6. Simulation results carry a tag too: **calibrated** (matched to a printed test) or **assumed**. Assumed results may
   rank options; they do not approve a design.
7. Small validated steps; a clean rebuild beats patching an unclear state; save right after a successful build.
8. Pin assignments live in `pinmap.json` only (firmware header and wiring table are generated from it).
9. Buying, ordering, flashing, deleting cloud files: always the user's decision.

## This build
- Fusion cloud folder: {{CLOUD_FOLDER}}
- Firmware: {{FIRMWARE_LINE}}
- Printer / material: see brief.md

## Folders
```
brief.md, requirements.json, project.json, state.md
parts/purchased/<part>/     reference model script + interface.json
parts/custom/<part>/        printed part scripts
assembly/                   layout, checks
sim/                        load cases and simulation reports
firmware/                   PlatformIO project (if any); pinmap.json at the top level
tests/  exports/  renders/  logs/
```
