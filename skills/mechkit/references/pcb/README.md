# Board design references (from text-to-cad)

The eleven reference files in this folder are text-to-cad's PCB skill references, copied unchanged from
https://github.com/earthtojake/text-to-cad (commit a35df3f, `skills/pcb/references/`), MIT licence, Copyright (c) 2026
Thompson Labs LLC and the others named in [LICENSE](LICENSE). They are the know-how for drawing a schematic, choosing
parts, placing, routing, checking and reviewing a board. Start from [../electronics.md](../electronics.md), which says
how the flow fits MechKit's gates.

## Read this first: the commands are different here

The references are written for text-to-cad's `cad` command. **MechKit never runs `cad`** (it carries telemetry,
auto-update and an installer for agent apps; MechKit uses only the library). Where a reference names a command, use:

| The reference says | In MechKit |
|---|---|
| `cad run script.py` | `uv run python script.py` (the kit's environment already holds the library and, with the `kicad` extra, KiCad) |
| `from cad import kicad_pcb` ... `kicad_pcb.edit(BOARD)` | `from mechkit import electronics` ... `electronics.edit_board(BOARD)` (same block; it also refreshes the stable-format copy). `electronics.edit_schematic`, `electronics.route` likewise |
| `cad kicad_pcb drc BOARD`, `cad kicad_sch erc SCH` | `uv run python -m mechkit pcb check BOARD [--schematic SCH]` |
| `cad kicad_pcb inspect BOARD` | `uv run python -m mechkit pcb inspect BOARD` |
| `cad kicad_pcb export BOARD --to KIND -o DIR` | `uv run python -m mechkit pcb export BOARD KIND DIR`; for a manufacturer, `pcb fab BOARD --out DIR` |
| `cad run kicad-cli ARGS` | `uv run python -m mechkit pcb kicad-cli -- ARGS` |
| `cad kicad_pcb snapshot BOARD OUT.png` | `uv run python -m mechkit pcb render BOARD OUT.png [--side bottom]` (KiCad's 3D render; the `--display placement` / `copper` views are not available: read positions with `kicad_pcb.read` instead) |
| `cad viewer`, `cad_show`, `cad server ...`, `cad step export` | not used. Show the person the render, the PDF export, or the stable-format copy in their KiCad app |
| `uv tool install cad`, `cad --version` | never. The library is pinned in MechKit's `pyproject.toml` |

Reading functions (`cad.kicad_pcb.read`, `cad.kicad_sch.read`) are the library's and are used as written.
