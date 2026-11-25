// Lets a drag or a wheel turn that STARTS on an overlay (a balloon) reach the 3D canvas beneath it.
//
// Balloons are buttons lying over the canvas, and the viewer listens on its canvas only: without this, the model
// cannot be grabbed wherever a balloon sits (17 of them, heaped together when assembled). A plain click on a balloon
// is untouched: forwarding starts only once the pointer has moved further than a click allows, and the click that
// would follow such a drag is swallowed.
//
// The canvas is handed synthetic pointer events carrying the real pointer's id, so the viewer's own
// setPointerCapture works; once the canvas holds the capture the browser sends it the real events and nothing more
// is forwarded.

const CLICK_SLOP = 4; // px, the same allowance the viewer uses to tell a click from a drag

interface Press {
  id: number;
  x: number;
  y: number;
  button: number;
  forwarding: boolean;
  /** The canvas took the pointer capture: it now gets the real events itself. */
  captured: boolean;
}

/** `buttons` bit for a `button` number (left, middle, right). */
export function buttonsFor(button: number): number {
  return button === 0 ? 1 : button === 1 ? 4 : button === 2 ? 2 : 0;
}

/** True once the pointer is further from where it went down than a click allows. */
export function isDrag(dx: number, dy: number, slop = CLICK_SLOP): boolean {
  return Math.hypot(dx, dy) > slop;
}

function pointerEvent(type: string, from: PointerEvent, x: number, y: number, button: number, buttons: number): PointerEvent {
  return new PointerEvent(type, {
    bubbles: true,
    cancelable: true,
    composed: true,
    pointerId: from.pointerId,
    pointerType: from.pointerType,
    isPrimary: from.isPrimary,
    clientX: x,
    clientY: y,
    screenX: from.screenX,
    screenY: from.screenY,
    button,
    buttons,
    shiftKey: from.shiftKey,
    ctrlKey: from.ctrlKey,
    altKey: from.altKey,
    metaKey: from.metaKey,
  });
}

/**
 * Forwards drags and wheel turns from `overlay` (and everything in it) to the canvas `getCanvas` returns.
 * Returns a function that removes every listener again.
 */
export function forwardToCanvas(overlay: HTMLElement, getCanvas: () => HTMLCanvasElement | null): () => void {
  let press: Press | null = null;
  let swallowClick = false;

  const stopWatching = (): void => {
    window.removeEventListener("pointermove", onMove);
    window.removeEventListener("pointerup", onUp);
    window.removeEventListener("pointercancel", onUp);
  };

  const onDown = (e: PointerEvent): void => {
    if (press || (e.button !== 0 && e.button !== 1 && e.button !== 2)) return;
    swallowClick = false;
    press = { id: e.pointerId, x: e.clientX, y: e.clientY, button: e.button, forwarding: false, captured: false };
    window.addEventListener("pointermove", onMove);
    window.addEventListener("pointerup", onUp);
    window.addEventListener("pointercancel", onUp);
  };

  const onMove = (e: PointerEvent): void => {
    if (!press || e.pointerId !== press.id || press.captured) return;
    const canvas = getCanvas();
    if (!canvas) return;
    if (!press.forwarding) {
      if (!isDrag(e.clientX - press.x, e.clientY - press.y)) return;
      press.forwarding = true;
      swallowClick = true;
      // The drag starts where the pointer went down, so the view does not jump by the distance already covered.
      canvas.dispatchEvent(pointerEvent("pointerdown", e, press.x, press.y, press.button, buttonsFor(press.button)));
      try {
        press.captured = canvas.hasPointerCapture(press.id);
      } catch {
        press.captured = false;
      }
    }
    // Sent even when the canvas has just taken the capture: this one real event was not delivered to it.
    canvas.dispatchEvent(pointerEvent("pointermove", e, e.clientX, e.clientY, -1, buttonsFor(press.button)));
  };

  const onUp = (e: PointerEvent): void => {
    if (!press || e.pointerId !== press.id) return;
    const p = press;
    press = null;
    stopWatching();
    if (p.forwarding && !p.captured) getCanvas()?.dispatchEvent(pointerEvent(e.type, e, e.clientX, e.clientY, p.button, 0));
  };

  const onWheel = (e: WheelEvent): void => {
    const canvas = getCanvas();
    if (!canvas) return;
    e.preventDefault(); // the page must not scroll or zoom instead
    canvas.dispatchEvent(
      new WheelEvent("wheel", {
        bubbles: true,
        cancelable: true,
        deltaX: e.deltaX,
        deltaY: e.deltaY,
        deltaZ: e.deltaZ,
        deltaMode: e.deltaMode,
        clientX: e.clientX,
        clientY: e.clientY,
        shiftKey: e.shiftKey,
        ctrlKey: e.ctrlKey,
        altKey: e.altKey,
        metaKey: e.metaKey,
      }),
    );
  };

  // Capture phase, so it runs before React's own click handling sees the event.
  const onClick = (e: MouseEvent): void => {
    if (!swallowClick) return;
    swallowClick = false;
    e.stopPropagation();
    e.preventDefault();
  };

  const onContext = (e: Event): void => e.preventDefault(); // a right-drag pans; no menu, as on the canvas itself

  overlay.addEventListener("pointerdown", onDown);
  overlay.addEventListener("wheel", onWheel, { passive: false });
  overlay.addEventListener("click", onClick, true);
  overlay.addEventListener("contextmenu", onContext);

  return () => {
    stopWatching();
    press = null;
    overlay.removeEventListener("pointerdown", onDown);
    overlay.removeEventListener("wheel", onWheel);
    overlay.removeEventListener("click", onClick, true);
    overlay.removeEventListener("contextmenu", onContext);
  };
}
