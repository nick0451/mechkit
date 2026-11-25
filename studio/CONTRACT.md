# MechKit Studio v1: contract

A browser viewer for projects built with the kit (`../mechkit`). The user reviews a design; they do not edit it.
They want to: pick a project, see it in 3D, slide it apart, click parts to read what they are, and PRINT
(a) the exploded view with its parts table and (b) a step-by-step assembly guide.

This file is the agreement between the agents building it. If something here is wrong or impossible, say so in your
report; do not quietly do something else.

## Hard rules (every agent)

1. Work only inside the folders you own (table below). Read anything; write only there.
2. FOUNDATION FILES are owned by the main session. Do not edit them: `web/src/types.ts`, `web/src/viewer/api.ts`,
   `web/src/lib/layout.ts`, `web/src/main.tsx`, `web/src/styles/tokens.css`, `web/src/styles/print.css`,
   `web/package.json`, `web/tsconfig.json`, `web/vite.config.ts`, `web/index.html`, this file,
   `mechkit/present/*.py`, any project's `build.py`. If you need a change in one, describe it in your report.
3. Never import, call or start anything to do with Autodesk Fusion (`fusion_client`, `mechkit/present/fusion.py`,
   `mechkit/fusion_export.py`, the add-in on port 3600).
4. No new packages. Python: what `mechkit/pyproject.toml` already lists (fastapi, uvicorn, build123d, numpy...).
   npm: what `web/package.json` already lists (react, react-dom, three, vite, typescript, vitest). No `npm install <x>`,
   no `uv add`. If you believe one is truly needed, stop and say so in your report.
5. Nothing loads from the internet at run time: no CDN links, no web fonts, no analytics.
6. The server listens on 127.0.0.1 only.
7. Do not start long-running servers and leave them running. Start, check, stop.
8. Report honestly: what you built, what you tested and how, and a plain list of what is NOT done or NOT verified.

## Who owns what

| Agent | Writes in |
|---|---|
| Backend | `mechkit/mechkit/studio/` (Python package), `mechkit/tests/test_studio.py`, the `studio` sub-command in `mechkit/mechkit/__main__.py` (add only; touch nothing else in that file) |
| App shell | `web/src/app/`, `web/src/state/`, `web/src/api/` |
| Viewer | `web/src/viewer/` except `api.ts` |
| Print | `web/src/print/` |
| Integrator | everything under `web/src/` except foundation files (after the three above are done) |
| Fixer | the union of the above |

Paths: the kit is this repository's root folder; the web app is `studio/web`.
Run Python as `uv run python ...` from the kit folder. Run `npm run typecheck`, `npm test`, `npm run build` from `web/`.
Shell: Git Bash on Windows. Write files with your file-writing tool, not shell heredocs (they break on apostrophes).

## Data

Projects are folders beside the kit or in its `examples/` folder (see `mechkit/studio/app.py`, `default_roots`). A project is viewable
when it has `exports/<version>/presentation/manifest.json`. Beside the manifest is one STEP file per item
(`<key>.step`), each solid already in its assembled position.

Real example to develop against: `examples/monitor-weather-display/exports/v0p9/presentation/`
(19 items: 7 printed, 2 bought shown as 3 items, 8 hardware, 1 reference; 13 table rows; 5 views; 7 steps).

Manifest shape: `web/src/types.ts` (`Manifest`, `Part`, `View`, `TableRow`, `Step`). Read it; it is commented.
Loading on the Python side: `mechkit.present.manifest.load(path)` (validates; adds `folder`), `manifest.find(project_dir, version=None)`.

**Frames.** The kit frame is millimetres, Z up, +Y toward the user (front), X along the width. All manifest vectors
(explode, centre, bbox, views) are in it.

## Backend API (FastAPI, `mechkit/mechkit/studio/`)

| Route | Returns |
|---|---|
| `GET /api/health` | `{"status": "ok", "kit": "<path>"}` |
| `GET /api/projects` | `ProjectList`: every sibling folder with at least one manifest; `versions` newest first (by manifest modification time) |
| `GET /api/projects/{id}/{version}/manifest` | the manifest JSON (without the server-side `folder` key) |
| `GET /api/projects/{id}/{version}/model.glb` | `model/gltf-binary` |
| anything else | the built web app from `studio/web/dist` (index.html for unknown non-API paths); a clear plain-text message if `dist` is missing |

- `id` is the project folder's name. Refuse anything that is not a direct child of the projects root or a plain
  version folder name: no `..`, no slashes, no absolute paths (404, never read outside).
- 404 with a JSON `{"detail": "..."}` for an unknown project or version.
- The projects root defaults to the kit's parent folder; overridable (`create_app(projects_root=...)`) so tests use a
  temporary folder.
- Command: `uv run python -m mechkit studio [--port 8765] [--no-browser]` starts uvicorn on 127.0.0.1 and opens the
  browser.

### The GLB (important: measured, not guessed)

Make it with build123d (`bd.export_gltf(compound, path, binary=True, linear_deflection=0.05, angular_deflection=0.3)`):
import each item's STEP (`bd.import_step`), set `shape.label = part["key"]` and
`shape.color = bd.Color(r, g, b, opacity)` (0..1 floats from the `#rrggbb`), then
`bd.Compound(label="model", children=[...])`.
What that produces (checked 2026-11-25 with build123d 0.13):
- units are METRES (0.024 = 24 mm);
- the root node `model` carries a rotation that turns the kit's Z-up into glTF's Y-up;
- each item is a node **named by its key** (no transform of its own), with one child node (named `COMPOUND` or
  similar) that holds the mesh and its own placement;
- so, inside the root, an item node's local frame IS the kit frame, in metres: to explode an item by `e` mm, set
  the item node's `position` to `e / 1000` in kit axes (x, y, z as in the manifest). No axis juggling needed.
- colours come through as materials (linear values).
Cache the file as `model.glb` beside the manifest; rebuild when it is missing or older than the manifest or any STEP.
Export takes a few seconds: build it once, serve the file. Two requests at once must not corrupt it (write to a
temporary name, then rename).

## Web app (`studio/web`, React + TypeScript + three.js, Vite)

Layout (from the user's mock-up): header (app name; project and version pickers); left: assembly tree (items grouped
under the project, a coloured marker by kind, click selects); centre: 3D viewport with a toolbar above it
(named-view buttons, "Balloons" toggle, "Context" toggle for reference parts, "Fit") and an Explode slider
0-100 % below; a card for the selected part floating over the viewport's lower-left; tabs along the bottom or top:
**Assembly** (the 3D view), **Parts** (the table), **Guide** (the steps on screen, each with its own small picture or
at least its part list), and the two print buttons: "Print exploded sheet", "Print assembly guide".
Tabs the mock-up shows but v1 does not have (Simulation, Fabrication, Revisions; Section, Measure): leave them out
entirely rather than showing dead buttons.

Look: `web/src/styles/tokens.css`. Dark, quiet, one accent. No emoji, no gradients, no decoration.

### Module boundaries
- `src/viewer/viewer.ts` exports `createViewer` implementing `src/viewer/api.ts` (`Viewer`). Only this folder imports
  three.js. Orthographic camera (no perspective), Z-up handled by the GLB's own root rotation, orbit with the mouse
  (left drag orbit, right drag or shift-drag pan, wheel zoom), click to pick (a drag is not a click).
  `capture()` renders at the REQUESTED size regardless of the on-screen size and device pixel ratio, with the given
  background, and returns anchors in that image's pixels. Each part must get its own material instance so that
  highlight / mute / select never bleed onto other parts.
- `src/print/index.ts` exports `printExplodedSheet` and `printGuide` (signatures in the stub: keep them). It creates
  its own off-screen viewer (`createViewer(hiddenDiv, { background: "#ffffff", interactive: false })`), captures
  images, builds pages inside `#print-root`, waits for the images to be decoded, calls `window.print()`, cleans up.
  Balloons on printed images are drawn as SVG or HTML over the image using `capture().anchors` and
  `lib/layout.ts` (`placeBalloons`, `leaderStart`).
- `src/api/client.ts`: `fetchProjects`, `fetchManifest`, `glbUrl` (keep these names).
- `src/app/` uses the three above. On-screen balloons are HTML positioned from `viewer.anchors()` on `viewer.onFrame`.

### Print outputs (the reason the app exists: get these right)
Paper: A4 or US Letter, the user picks orientation in the print dialog; design for LANDSCAPE, 10 mm margins, and
make sure nothing is cut off in portrait either (images scale to the page width).
White background, dark ink, the parts' own colours. Every page: project name, version, page title, page number.

1. **Exploded sheet** (one page): the view the user has on screen (their camera, their explode amount, their
   context-parts setting), numbered balloons with leader lines, and the parts table (No., Part, Qty, Made, Material,
   Part number, Description). 13 rows must fit on the one page beside or below the picture.
2. **Assembly guide** (several pages): page 1 = title, a picture of the finished assembly, and the full parts table.
   Then one page per step: "Step N of M: title"; a picture showing everything added so far in muted colours and
   this step's parts in full colour, pulled apart along their explode direction (so you see how they go on), with
   balloons on this step's parts only; a "You need" list for the step (number, name, quantity); the step's text.
   Reference parts (the monitor) are left out of step pictures. Camera for each step: the manifest's first
   `exploded` view direction, fitted to what is shown. `page-break-after` between pages; no page splits a picture
   from its text.
   A manifest with no steps: `printGuide` rejects with a clear message and the app disables the button with a
   tooltip saying the project has no assembly order.

## Acceptance list (the reviewers check these; the main session then checks them in a real browser)

1. `uv run python tests/test_studio.py` passes; `npm run typecheck`, `npm test`, `npm run build` pass with no warnings
   that matter.
2. `uv run python -m mechkit studio --no-browser` serves the built app and the API on 127.0.0.1:8765.
3. The monitor display loads: 19 items in the tree, model visible, colours as in the manifest, right way up
   (the round display hangs BELOW the monitor piece; the knob is behind it).
4. Explode slider: at 0 the model is assembled; at 100 % every part has moved by its `explode` vector; smooth between.
5. Clicking a part in the view selects it in the tree and shows its card; clicking in the tree highlights it in the view.
6. Balloons show each part's `label`, follow the parts while orbiting and exploding, never mirror or turn, and the
   numbers match the Parts tab.
7. Named views work; "Fit" works after exploding; context toggle hides and shows the monitor piece.
8. Parts tab: 13 rows, quantities 3 / 3 / 1 for M3 bolts / M3 inserts / display.
9. Guide tab: 7 steps in order with their texts and parts.
10. Both print outputs open the print dialog with complete, uncut pages (see above).
11. A manifest without steps loads and views fine; the guide button is disabled with an explanation.
12. Resizing the window keeps the view correct; switching project or version does not leak WebGL contexts.

## Added after v1 (2026-11-25, main session)

- `Step.view` and `Step.pull` (see `types.ts`): a step's own camera direction and absolute pull-out offsets. When a step
  has `pull`, the print module uses `viewer.setOffsets(pull)` instead of the derived explode map.
- `Viewer.setOffsets(map | null)`: absolute displacement per part in mm, kit frame; wins over explode for the parts named.
- `Manifest.guide` (`Guide` in `types.ts`): tools, consumables, printing, wiring, commissioning, notes. Printed by
  `print/extras.ts` as extra pages: title, before you start, wiring, the steps, commissioning (only the pages a project has).
