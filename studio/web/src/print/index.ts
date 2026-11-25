// The two printed outputs: the exploded sheet and the assembly guide (see ../../../CONTRACT.md, "Print outputs").
// Each job renders its pictures in ONE off-screen viewer, builds the pages inside #print-root, waits for the
// images, opens the print dialog and clears #print-root after printing. Both resolve once the pages are ready and
// the dialog is about to open.
import "./print.css";

import type { Manifest, View } from "../types";
import type { CameraState, Viewer } from "../viewer/api";
import { createViewer } from "../viewer/viewer";
import { BEFORE_TITLE, COMMISSIONING_TITLE, extraPages, guideBeforePage, guideCommissioningPage, guideWiringPage } from "./extras";
import { GUIDE_TITLE, headers, SHEET_TITLE, stepTitle } from "./pages";
import type { Picture } from "./render";
import { guideCoverPage, guideStepPage, imagesReady, sheetPage } from "./render";
import { assertHasSteps, needRows, stepExplodeMap, stepSets } from "./steps";

export interface SheetRequest {
  manifest: Manifest;
  glbUrl: string;
  /** The camera and explode amount the user has on screen right now. */
  camera: CameraState;
  explode: number; // 0..1
  showReference: boolean;
  /**
   * true = the screen shows the view exactly as "Fit" (or a named view) leaves it. The sheet's picture is then fitted
   * to ITS OWN shape from the same direction, so the model fills the printed picture whatever shape the window has.
   * false / absent = print the camera as given (the user zoomed or panned on purpose).
   */
  fitted?: boolean;
}

export interface GuideRequest {
  manifest: Manifest;
  glbUrl: string;
}

/** Captured size of full-width pictures: 1.6 : 1. At 155 mm wide that is about 260 dpi, and the model's edge lines
 *  (always 1 px in WebGL) print about 0.1 mm wide. More pixels would only make those lines thinner and fainter on
 *  paper (2400 px gave 0.065 mm). NOT yet judged on a real print. */
const FULL = { width: 1600, height: 1000 };
/** Shape (width / height) of the exploded sheet's picture. A caller whose on-screen view is wider must widen the
 *  camera it passes (more picture height) or the sheet loses the sides: see cameraForPicture in state/logic.ts. */
export const SHEET_PICTURE_ASPECT = FULL.width / FULL.height;
/** Step pictures: 4 : 3, taller, because the page has the height for it and we choose the framing ourselves. */
const STEP = { width: 1600, height: 1200 };
/** Height of the hidden viewer in CSS px. Its width is set per picture to the picture's shape (see `frame`). */
const STAGE_HEIGHT = 750;
const WHITE = "#ffffff";
/** Clear the pages this long after opening the dialog if the browser never reports "afterprint". */
const CLEANUP_FALLBACK_MS = 10 * 60 * 1000;
/** Pause between resolving and window.print(), so the app can repaint (the dialog blocks the page in Chrome). */
const DIALOG_DELAY_MS = 60;

let busy = false;
let pendingCleanup: (() => void) | null = null;

// ---- telling the app when the dialog could not be opened --------------------------------------------------------
// A job resolves just BEFORE window.print() is called (see show), so a failure there cannot reject its promise.

const failureListeners = new Set<(message: string) => void>();

/** Called with a message for the user when the print dialog could not be opened. Returns an unsubscribe function. */
export function onPrintFailure(cb: (message: string) => void): () => void {
  failureListeners.add(cb);
  return () => {
    failureListeners.delete(cb);
  };
}

function reportFailure(err: unknown): void {
  const reason = err instanceof Error && err.message ? err.message : String(err);
  console.error("MechKit Studio: the print dialog could not be opened.", err);
  for (const cb of [...failureListeners]) {
    try {
      cb(`The pages were ready, but the browser's print dialog could not be opened: ${reason}`);
    } catch (e) {
      console.error("print failure listener failed", e);
    }
  }
}

// ---- printing from the browser's own menu or Ctrl+P --------------------------------------------------------------
// styles/print.css hides the app whenever the page is printed and shows only #print-root, which is empty unless one
// of the two jobs here has filled it: the browser's own print command would give a blank sheet. It gets one line
// saying how to print instead.

export const PRINT_NOTE = 'Nothing is set up to print. In MechKit Studio, use the "Print exploded sheet" or "Print assembly guide" button.';

function installPrintNote(): void {
  let note: HTMLElement | null = null;
  window.addEventListener("beforeprint", () => {
    const root = printRoot();
    if (root.childElementCount > 0) return; // a job's pages (or the note) are already there
    note = document.createElement("p");
    note.className = "pr-note";
    note.textContent = PRINT_NOTE;
    root.append(note);
  });
  window.addEventListener("afterprint", () => {
    note?.remove();
    note = null;
  });
}

if (typeof window !== "undefined" && typeof document !== "undefined") installPrintNote();

function printRoot(): HTMLElement {
  let root = document.getElementById("print-root");
  if (!root) {
    root = document.createElement("div");
    root.id = "print-root";
    document.body.append(root);
  }
  return root;
}

interface Size {
  width: number;
  height: number;
}

/**
 * Gives the hidden viewer the shape of the picture about to be taken. Call it BEFORE setView / fit: the viewer fits
 * the model to its own shape, and a capture keeps the picture's height and takes its width from the requested size.
 */
type Frame = (size: Size) => void;

const stageWidth = (size: Size): number => Math.round((STAGE_HEIGHT * size.width) / size.height);

/** Runs `shoot` with a loaded off-screen viewer; the viewer and its hidden container are always removed again. */
async function withViewer<T>(manifest: Manifest, glbUrl: string, shoot: (viewer: Viewer, frame: Frame) => Promise<T>): Promise<T> {
  const stage = document.createElement("div");
  stage.setAttribute("aria-hidden", "true");
  // Not display:none: WebGL needs a laid-out container. Parked far off screen instead.
  stage.style.cssText = `position:fixed;left:-10000px;top:0;width:${stageWidth(FULL)}px;height:${STAGE_HEIGHT}px;overflow:hidden;pointer-events:none;`;
  document.body.append(stage);
  let viewer: Viewer | null = null;
  try {
    const made = createViewer(stage, { background: WHITE, interactive: false });
    viewer = made;
    await made.load(manifest, glbUrl);
    const frame: Frame = (size) => {
      stage.style.width = `${stageWidth(size)}px`;
      made.resize();
    };
    return await shoot(made, frame);
  } finally {
    try {
      viewer?.dispose();
    } finally {
      stage.remove();
    }
  }
}

async function shot(viewer: Viewer, size: Size, balloons: Picture["balloons"], alt: string): Promise<Picture> {
  const capture = await viewer.capture({ width: size.width, height: size.height, background: WHITE });
  if (!capture || typeof capture.dataUrl !== "string" || !capture.dataUrl.startsWith("data:image/")) {
    throw new Error("The 3D view returned no picture for the printed page.");
  }
  return { capture, width: size.width, height: size.height, balloons, alt };
}

function lookFrom(viewer: Viewer, view: View | undefined): void {
  if (view) viewer.setView(view);
  else viewer.fit();
}

/** Puts the pages in #print-root, waits for their images and opens the print dialog. */
async function show(pages: HTMLElement[]): Promise<void> {
  const root = printRoot();
  pendingCleanup?.(); // leftovers of an earlier job whose "afterprint" never came
  root.replaceChildren(...pages); // also drops the Ctrl+P note, should one be showing

  let timer = 0;
  const cleanup = (): void => {
    window.removeEventListener("afterprint", cleanup);
    window.clearTimeout(timer);
    if (pendingCleanup === cleanup) pendingCleanup = null;
    root.replaceChildren();
  };
  pendingCleanup = cleanup;

  try {
    await imagesReady(root);
  } catch (err) {
    cleanup();
    throw err;
  }

  window.addEventListener("afterprint", cleanup);
  timer = window.setTimeout(cleanup, CLEANUP_FALLBACK_MS);
  // The dialog opens a moment AFTER this function resolves: window.print() blocks the page in some browsers, and the
  // caller should be able to take down its "preparing" state first. `busy` stays set until print() has been called.
  window.setTimeout(() => {
    try {
      window.print();
    } catch (err) {
      cleanup();
      reportFailure(err);
    } finally {
      busy = false;
    }
  }, DIALOG_DELAY_MS);
}

async function job(build: () => Promise<HTMLElement[]>): Promise<void> {
  if (busy) throw new Error("A print job is already being prepared. Wait for its print dialog, then try again.");
  busy = true;
  let handedOver = false;
  try {
    const pages = await build();
    await show(pages);
    handedOver = true; // show() releases `busy` once the dialog has been opened
  } finally {
    if (!handedOver) busy = false;
  }
}

/** One page: the view on screen (camera, explode amount, context setting) with balloons, and the parts table. */
export async function printExplodedSheet(req: SheetRequest): Promise<void> {
  await job(async () => {
    const { manifest } = req;
    const pic = await withViewer(manifest, req.glbUrl, async (viewer, frame) => {
      frame(FULL);
      viewer.setVisible(null);
      viewer.setHighlighted([]);
      viewer.setSelected(null);
      viewer.showReference(req.showReference);
      viewer.setExplodeMap(null);
      viewer.setExplode(Math.min(1, Math.max(0, req.explode)));
      viewer.setCamera(req.camera);
      // Same direction, fitted to what is shown; the capture then fits it to the picture's own shape.
      if (req.fitted) viewer.fit();
      return shot(viewer, FULL, "all", `${manifest.project}: exploded view`);
    });
    const [header] = headers(manifest, [SHEET_TITLE]);
    return [sheetPage(manifest, header, pic)];
  });
}

/** Title page (finished assembly, parts table), then one page per step. Rejects when the manifest has no steps. */
export async function printGuide(req: GuideRequest): Promise<void> {
  assertHasSteps(req.manifest);
  await job(async () => {
    const { manifest } = req;
    const assembled = manifest.views.find((v) => v.group === "assembled") ?? manifest.views[0];
    const exploded = manifest.views.find((v) => v.group === "exploded") ?? manifest.views[0];
    const allKeys = manifest.parts.map((p) => p.key);

    const pics = await withViewer(manifest, req.glbUrl, async (viewer, frame) => {
      viewer.setSelected(null);

      frame(FULL);
      viewer.setVisible(null);
      viewer.setHighlighted([]);
      viewer.showReference(true);
      viewer.setExplodeMap(null);
      viewer.setExplode(0);
      lookFrom(viewer, assembled);
      const cover = await shot(viewer, FULL, "none", `${manifest.project}: finished assembly`);

      viewer.showReference(false);
      frame(STEP);
      const steps: Picture[] = [];
      for (let i = 0; i < manifest.steps.length; i++) {
        const { visible, highlighted } = stepSets(manifest, i);
        viewer.setVisible(visible);
        viewer.setHighlighted(highlighted);
        viewer.setExplode(0);
        const step = manifest.steps[i];
        if (step.pull) {
          // The project says how this step's parts go on: draw them pulled out along that way, everything else seated.
          viewer.setExplodeMap(null);
          viewer.setOffsets(step.pull);
        } else {
          viewer.setOffsets(null);
          viewer.setExplodeMap(stepExplodeMap(manifest, i));
        }
        // From where the project says this step is best seen, else the general exploded direction. Re-fits to what is shown.
        lookFrom(viewer, step.view ? { name: "step", group: "exploded", eye: step.view.eye, target: step.view.target, up: step.view.up } : exploded);
        steps.push(await shot(viewer, STEP, highlighted, `Step ${i + 1}: ${manifest.steps[i].title}`));
      }
      // Leave the viewer in a plain state before it is disposed (harmless, and keeps a shared GLB cache clean).
      viewer.setOffsets(null);
      viewer.setExplodeMap(null);
      viewer.setHighlighted([]);
      viewer.setVisible(allKeys);
      return { cover, steps };
    });

    // Page order: title, before you start, wiring, the steps, commissioning. Only the pages the project has.
    const extra = extraPages(manifest.guide);
    const stepTitles = manifest.steps.map((_, i) => stepTitle(manifest, i));
    const titles = [
      GUIDE_TITLE,
      ...(extra.before ? [BEFORE_TITLE] : []),
      ...(extra.wiring ? [manifest.guide!.wiring!.title] : []),
      ...stepTitles,
      ...(extra.commissioning ? [COMMISSIONING_TITLE] : []),
    ];
    const heads = headers(manifest, titles);
    let n = 0;
    const pages: HTMLElement[] = [guideCoverPage(manifest, heads[n++], pics.cover)];
    if (extra.before) pages.push(guideBeforePage(heads[n++], manifest.guide!));
    if (extra.wiring) pages.push(guideWiringPage(heads[n++], manifest.guide!.wiring!));
    manifest.steps.forEach((step, i) => {
      pages.push(
        guideStepPage({
          header: heads[n++],
          heading: stepTitles[i],
          text: step.text,
          need: needRows(manifest, i),
          pic: pics.steps[i],
          last: i === manifest.steps.length - 1,
          doneText: extra.commissioning ? "That was the last assembly step. Next: commissioning." : undefined,
        }),
      );
    });
    if (extra.commissioning) pages.push(guideCommissioningPage(heads[n++], manifest.guide!));
    return pages;
  });
}
