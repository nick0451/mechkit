# Board design in a MechKit build

A board is its native KiCad files (`.kicad_sch`, `.kicad_pcb`, `.kicad_pro`), kept in the project under
`electronics/<board>/`. MechKit checks them, edits them through KiCad's own API, takes the board's outline and holes
into the mechanical design, and makes the package a manufacturer takes. The how-to of schematics, parts, placement,
routing and review is in [pcb/](pcb/README.md) (text-to-cad's references; read its command table first).

## What runs

| Need | Runs | Install |
|---|---|---|
| DRC, ERC, exports, the fabrication package | any `kicad-cli`: `MECHKIT_KICAD_CLI`, else the `kicad` extra's, else the installed KiCad | none if KiCad is installed |
| Edits and routing | the `kicad` extra: kicode, an unofficial packaging of a KiCad nightly (GPL-3.0-or-later) | `uv sync --extra kicad` (about 73 MB; the person approves downloads) |

An edit saves the board in the NIGHTLY's file format. A stable KiCad app refuses to open that, so `edit_board`
refreshes `kicad-10.0/` beside the board: a downgraded copy for looking at in the stable app. Tell the person before
the first edit of a board they made in a stable KiCad; the nightly-format file is the source from then on, and a
change made in the copy is lost.

## The flow, with its gates

1. **Circuit first.** The schematic says what connects to what. A board with no schematic needs a written circuit
   specification the person has reviewed (G1): pad numbers alone do not say which connections are right. Pin numbers,
   footprint orientation and connector sides come from datasheets, tagged like any other number.
2. **Parts** ([pcb/parts.md](pcb/parts.md)). Anything to be bought is G2.
3. **Outline and holes from the mechanical design**, or the other way round: `electronics.board_interface(board)` gives
   the board's size, thickness and holes in the `interface.json` layout (KiCad's frame, y down), and
   `pcb export BOARD step DIR` a STEP for the enclosure script. Decide once which side owns the outline and record it.
4. **Place and route** in `with electronics.edit_board(BOARD) as b:` blocks ([pcb/placement.md](pcb/placement.md),
   [pcb/layout.md](pcb/layout.md), [pcb/board-api.md](pcb/board-api.md)). State results, not changes, so a script can
   run twice. `electronics.route(b, connections, ...)` inside the block for the nets whose path does not matter.
5. **Check every change**: `uv run python -m mechkit pcb check BOARD --out <reports folder>` (exit 0 pass, 1 fail,
   2 not evaluated). Warnings count: silkscreen, mask and courtyard rules are what a fab's engineer flags. Requirement
   type `electronics_ok` reads the report.
6. **Review before ordering** ([pcb/review-fabrication.md](pcb/review-fabrication.md),
   [review-electrical](pcb/review-electrical.md), [review-assembly](pcb/review-assembly.md)) against the chosen fab's own
   capability page; where the person names none, JLCPCB's standard service, said so. A clean DRC shows the board meets
   its own rules, not that the circuit is right or that the fab can make it.
7. **Fabrication package**: `uv run python -m mechkit pcb fab BOARD --out exports/<version>/fab`. It runs DRC (and ERC
   when the schematic is beside the board) and REFUSES on an error or a check that could not run, unless
   `--go-ahead "<the person's words and the date>"`; the manifest then records their words and every error. It writes
   `<board>-gerbers.zip` (gerbers + drill), `assembly/` (placement, the same with JLCPCB's column names, the BOM) and
   `fab_manifest.json` (board sha256, KiCad version, checks, every file's sha256).
8. **Ordering is the person's (G2).** Before they upload: `electronics.package_is_current(out, board)` must be true,
   and they should look at the gerbers in the fab's preview or a Gerber viewer. MechKit sends nothing.

## Rules

- Never run `cad`, `uv tool install cad`, or the person's KiCad app from a script.
- Never weaken a design rule to get a clean report; fix the cause.
- Import KiPy's names from `kicode`, never `kipy`.
- Edits need a local socket: a sandbox that refuses sockets stops them at once.
- A number is read from the board (`cad.kicad_pcb.read`), never off a picture.
