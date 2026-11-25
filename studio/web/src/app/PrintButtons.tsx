// The two print outputs. The print module builds the pages and opens the browser's print dialog.
import { useEffect, useState } from "react";
import { glbUrl } from "../api/client";
import { onPrintFailure, printExplodedSheet, printGuide, SHEET_PICTURE_ASPECT } from "../print/index";
import { cameraForPicture, countOutsideView, outsideViewMessage, sameCamera } from "../state/logic";
import { getActiveViewAspect, getActiveViewer, getState, useStore } from "../state/store";
import type { Manifest } from "../types";
import type { Viewer } from "../viewer/api";

type Job = "sheet" | "guide";

function messageOf(e: unknown): string {
  return e instanceof Error && e.message ? e.message : String(e);
}

/**
 * Is the screen showing the view exactly as "Fit" (or a named view) leaves it? The viewer does not say, so: fit,
 * compare, and put the user's camera back if it was different. Both calls happen before the next frame is drawn,
 * so nothing shows on screen.
 */
function isFittedView(viewer: Viewer): boolean {
  const before = viewer.getCamera();
  viewer.fit();
  if (sameCamera(before, viewer.getCamera())) return true;
  viewer.setCamera(before);
  return false;
}

export function PrintButtons({ manifest, projectId, version }: { manifest: Manifest; projectId: string; version: string }) {
  const modelReady = useStore((s) => s.modelReady);
  const [busy, setBusy] = useState<Job | null>(null);
  const [error, setError] = useState<string | null>(null);
  /** Set while asking what to do about a view that leaves parts out: how many parts. */
  const [outside, setOutside] = useState<number | null>(null);
  const hasSteps = manifest.steps.length > 0;

  // The print dialog opens just after a job has resolved; a failure there arrives here instead.
  useEffect(() => onPrintFailure((message) => setError(message)), []);

  // A question about one model's view does not carry over to another.
  useEffect(() => setOutside(null), [manifest]);

  /** asShown: print the view even though parts are outside it (the user was asked). */
  const run = async (job: Job, asShown = false) => {
    if (busy) return;
    setError(null);
    setOutside(null);
    const url = glbUrl(projectId, version);
    let work: () => Promise<void>;
    if (job === "sheet") {
      const viewer = getActiveViewer();
      if (!viewer) {
        setError("Exploded sheet could not be printed: The 3D view is not ready yet.");
        return;
      }
      const s = getState();
      const fitted = isFittedView(viewer);
      if (!fitted && !asShown) {
        // The likeliest way to a sheet with parts missing: the slider was moved after the view was fitted.
        const n = countOutsideView(viewer.anchors());
        if (n > 0) {
          setOutside(n);
          return;
        }
      }
      // A fitted view is fitted again for the sheet's own picture shape (it then fills the picture). Any other view
      // is printed as it is; when the screen is wider than the picture it is zoomed out just enough to keep its sides.
      const camera = fitted ? viewer.getCamera() : cameraForPicture(viewer.getCamera(), getActiveViewAspect(), SHEET_PICTURE_ASPECT);
      work = () => printExplodedSheet({ manifest, glbUrl: url, camera, explode: s.explode, showReference: s.context, fitted });
    } else {
      work = () => printGuide({ manifest, glbUrl: url });
    }
    setBusy(job);
    try {
      await work();
    } catch (e) {
      setError(`${job === "sheet" ? "Exploded sheet" : "Assembly guide"} could not be printed: ${messageOf(e)}`);
    } finally {
      setBusy(null);
    }
  };

  const fitAndPrint = () => {
    getActiveViewer()?.fit();
    void run("sheet");
  };

  return (
    <div className="print-buttons">
      {busy && (
        <span className="print-status" role="status">
          Preparing pages...
        </span>
      )}
      {outside !== null && !busy && (
        <span className="print-status ask" role="alert">
          {outsideViewMessage(outside)}
          <button type="button" className="btn small primary" onClick={fitAndPrint}>
            Fit and print
          </button>
          <button type="button" className="btn small" onClick={() => void run("sheet", true)}>
            Print as shown
          </button>
          <button type="button" className="btn small" onClick={() => setOutside(null)}>
            Cancel
          </button>
        </span>
      )}
      {error && !busy && (
        <span className="print-status problem" role="alert">
          {error}
          <button type="button" className="btn small" onClick={() => setError(null)}>
            Dismiss
          </button>
        </span>
      )}
      <button
        type="button"
        className="btn primary"
        disabled={busy !== null || !modelReady}
        title={modelReady ? "Print the view as it is now, with balloons and the parts table" : "Available once the 3D model is shown"}
        onClick={() => void run("sheet")}
      >
        {busy === "sheet" ? "Preparing..." : "Print exploded sheet"}
      </button>
      <button
        type="button"
        className="btn primary"
        disabled={busy !== null || !hasSteps}
        title={hasSteps ? "Print the step-by-step assembly guide" : "This project has no assembly order, so there is no guide to print"}
        onClick={() => void run("guide")}
      >
        {busy === "guide" ? "Preparing..." : "Print assembly guide"}
      </button>
    </div>
  );
}
