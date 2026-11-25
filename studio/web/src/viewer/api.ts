// The 3D viewer's public interface. FOUNDATION FILE: owned by the main session. Agents read it; they do not edit it.
// The Viewer agent implements it in ./viewer.ts (export function createViewer). Everything else in the app talks to
// the 3D scene ONLY through this interface, and never imports three.js itself.

import type { Manifest, Vec3, View } from "../types";

export interface ViewerOptions {
  /** CSS colour of the scene background. Default: the app's dark viewport colour. Print uses "#ffffff". */
  background?: string;
  /** false = no mouse orbit / picking (used for off-screen rendering by the print module). Default true. */
  interactive?: boolean;
}

/** Where a part's centre currently is on screen (after explode), for drawing its balloon. */
export interface BalloonAnchor {
  key: string;
  label: number;
  /** CSS pixels from the top-left of the viewer's container (or of the captured image), y down. */
  x: number;
  y: number;
  /** false when the part is hidden, behind the camera or outside the picture. */
  visible: boolean;
}

/** Enough to put the camera back exactly. Kit frame, mm. */
export interface CameraState {
  eye: Vec3;
  target: Vec3;
  up: Vec3;
  /** Orthographic zoom: height of the picture in mm at the target. */
  height: number;
}

export interface Capture {
  /** PNG data URL of exactly the requested size. */
  dataUrl: string;
  /** Anchors in the captured image's own pixel coordinates. */
  anchors: BalloonAnchor[];
}

export interface Viewer {
  /** Load a project. Resolves when the model is on screen, assembled, camera fitted to the first assembled view. */
  load(manifest: Manifest, glbUrl: string): Promise<void>;

  /** Explode amount for every part, 0 (assembled) .. 1 (fully apart): each part moves by t * part.explode. */
  setExplode(t: number): void;
  /** Per-part override (key -> 0..1), used by the assembly guide; null clears it and setExplode's value applies again. */
  setExplodeMap(map: Record<string, number> | null): void;

  /** Absolute displacement per part (key -> mm, kit frame), used by the assembly guide's step pictures. A part named
   *  here ignores setExplode / setExplodeMap; parts not named are unaffected. null clears it. */
  setOffsets(map: Record<string, Vec3> | null): void;

  /** Which parts are drawn at all; null = all. Reference parts are also subject to showReference(). */
  setVisible(keys: string[] | null): void;
  /** Parts to emphasise: when the list is not empty, every other visible part is drawn muted (pale, see-through). */
  setHighlighted(keys: string[]): void;
  /** The selected part gets an outline or tint; null clears. Does NOT call the onSelect listeners. */
  setSelected(key: string | null): void;
  /** Called when the user clicks a part (its key) or empty space (null). Returns an unsubscribe function. */
  onSelect(cb: (key: string | null) => void): () => void;

  /** Context parts (kind "reference") on or off. Default on. */
  showReference(on: boolean): void;

  /** Look from the view's direction, fitted to what is currently visible (after explode). */
  setView(view: View): void;
  /** Keep the direction, re-fit the picture to what is currently visible. */
  fit(): void;
  getCamera(): CameraState;
  setCamera(state: CameraState): void;

  /** Balloon anchors for the parts that are visible, not reference, and have count > 0. */
  anchors(): BalloonAnchor[];
  /** Called after every frame in which the camera, the explode amount or visibility changed. Returns unsubscribe. */
  onFrame(cb: () => void): () => void;

  /** Render the current state at the given size (not the screen size) and return it with matching anchors. */
  capture(opts: { width: number; height: number; background?: string }): Promise<Capture>;

  /** Call when the container changed size. */
  resize(): void;
  /** Free the WebGL context and listeners. */
  dispose(): void;
}

export type CreateViewer = (container: HTMLElement, options?: ViewerOptions) => Viewer;
