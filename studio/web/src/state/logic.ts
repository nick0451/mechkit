// Pure helpers for the app shell: no DOM, no React, no network. Tested in logic.test.ts.
import type { Box, Kind, Manifest, Part, ProjectInfo, Step } from "../types";
import type { CameraState } from "../viewer/api";

export interface Choice {
  projectId: string;
  version: string;
}

/**
 * Which project and version to open: the remembered one when it still exists, else the first project's newest
 * version (versions are listed newest first). null when there is nothing to open.
 */
export function pickDefault(projects: ProjectInfo[], remembered?: Partial<Choice> | null): Choice | null {
  const usable = projects.filter((p) => p.versions.length > 0);
  if (usable.length === 0) return null;
  const same = remembered?.projectId ? usable.find((p) => p.id === remembered.projectId) : undefined;
  if (same) {
    const version = remembered?.version && same.versions.includes(remembered.version) ? remembered.version : same.versions[0];
    return { projectId: same.id, version };
  }
  return { projectId: usable[0].id, version: usable[0].versions[0] };
}

/** Reads a remembered choice back from storage text; anything odd gives null. */
export function parseChoice(text: string | null | undefined): Choice | null {
  if (!text) return null;
  try {
    const v: unknown = JSON.parse(text);
    if (v && typeof v === "object") {
      const { projectId, version } = v as Record<string, unknown>;
      if (typeof projectId === "string" && typeof version === "string") return { projectId, version };
    }
  } catch {
    // fall through
  }
  return null;
}

const MADE: Record<Kind, string> = {
  printed: "3D printed",
  bought: "Bought",
  hardware: "Hardware",
  reference: "Context only",
};

/** "How it is made", in words. */
export function madeLabel(kind: Kind): string {
  return MADE[kind] ?? String(kind);
}

export const KIND_ORDER: Kind[] = ["printed", "bought", "hardware", "reference"];

/** "48.0 x 11.4 x 47.6 mm" from a [min, max] box. */
export function formatSize(bbox: Box): string {
  const [lo, hi] = bbox;
  const d = [0, 1, 2].map((i) => Math.abs(hi[i] - lo[i]).toFixed(1));
  return `${d[0]} x ${d[1]} x ${d[2]} mm`;
}

function group3(n: string): string {
  return n.replace(/\B(?=(\d{3})+(?!\d))/g, ",");
}

/** Volume in mm3; from 1000 mm3 up also in cm3. */
export function formatVolume(mm3: number): string {
  if (!Number.isFinite(mm3) || mm3 <= 0) return "";
  if (mm3 < 100) return `${mm3.toFixed(1)} mm³`;
  const whole = group3(Math.round(mm3).toString());
  if (mm3 < 1000) return `${whole} mm³`;
  const cm3 = mm3 / 1000;
  return `${whole} mm³ (${cm3.toFixed(cm3 < 100 ? 2 : 1)} cm³)`;
}

export interface StepPart {
  label: number;
  /** Parts-table name. */
  part: string;
  /** How many of this part go on in this step (sum of the items' counts). 0 = a further piece of something already counted. */
  qty: number;
  kind: Kind;
  /** The items behind this line, in manifest order. */
  keys: string[];
}

/** A step's items grouped into one line per balloon number, ordered by number. Unknown keys are skipped. */
export function groupStepParts(manifest: Pick<Manifest, "parts">, step: Step): StepPart[] {
  const wanted = new Set(step.add);
  const byLabel = new Map<number, StepPart>();
  for (const p of manifest.parts) {
    if (!wanted.has(p.key)) continue;
    const g = byLabel.get(p.label);
    if (g) {
      g.qty += p.count;
      g.keys.push(p.key);
    } else {
      byLabel.set(p.label, { label: p.label, part: p.part || p.name, qty: p.count, kind: p.kind, keys: [p.key] });
    }
  }
  return [...byLabel.values()].sort((a, b) => a.label - b.label);
}

export interface StepRef {
  /** 1-based. */
  number: number;
  total: number;
  title: string;
}

/** The assembly step an item goes on in, or null (reference items; projects without steps). */
export function stepOfPart(manifest: Pick<Manifest, "steps">, key: string): StepRef | null {
  const i = manifest.steps.findIndex((s) => s.add.includes(key));
  return i < 0 ? null : { number: i + 1, total: manifest.steps.length, title: manifest.steps[i].title };
}

/** The first item with a balloon number (what a click on a parts-table row selects). */
export function firstKeyForLabel(parts: Part[], label: number): string | null {
  return parts.find((p) => p.label === label)?.key ?? null;
}

/** Items that get a balloon on screen: not reference, and counted (the viewer applies the same rule). */
export function balloonParts(parts: Part[]): Part[] {
  return parts.filter((p) => p.kind !== "reference" && p.count > 0);
}

export function clamp01(t: number): number {
  return Number.isFinite(t) ? Math.min(1, Math.max(0, t)) : 0;
}

/**
 * The camera to hand to a picture of a different shape so that it shows at least everything the screen shows.
 * A capture keeps the camera's picture HEIGHT and takes its width from the picture's shape, so a screen that is
 * wider than the picture would lose its left and right edges: the height is raised until the widths match.
 * A narrower screen needs nothing (the picture then shows a little more at the sides).
 */
export function cameraForPicture(camera: CameraState, screenAspect: number, pictureAspect: number): CameraState {
  if (!(screenAspect > 0) || !(pictureAspect > 0) || screenAspect <= pictureAspect) return camera;
  return { ...camera, height: (camera.height * screenAspect) / pictureAspect };
}

/**
 * True when two cameras give the same picture: same eye, target, up and picture height, to rounding.
 * Used to tell whether the screen still shows the view exactly as "Fit" leaves it (see PrintButtons).
 */
export function sameCamera(a: CameraState, b: CameraState, tolerance = 1e-6): boolean {
  const size = Math.max(1, Math.abs(a.height), Math.abs(b.height));
  const near = (p: readonly number[], q: readonly number[], eps: number) => p.every((v, i) => Math.abs(v - q[i]) <= eps);
  return (
    Math.abs(a.height - b.height) <= tolerance * size &&
    near(a.eye, b.eye, tolerance * size) &&
    near(a.target, b.target, tolerance * size) &&
    near(a.up, b.up, tolerance)
  );
}

/** How many balloon anchors lie outside the picture: parts a print of this view would leave out. */
export function countOutsideView(anchors: readonly { visible: boolean }[]): number {
  return anchors.reduce((n, a) => n + (a.visible ? 0 : 1), 0);
}

/** The sentence shown before printing a view that leaves parts out. */
export function outsideViewMessage(count: number): string {
  return count === 1
    ? "1 part is outside the view and would be missing from the printed sheet."
    : `${count} parts are outside the view and would be missing from the printed sheet.`;
}

export interface Problem {
  title: string;
  detail: string;
  /** What the user can do about it. */
  hint: string;
}

interface ErrorLike {
  kind?: unknown;
  status?: unknown;
  message?: unknown;
}

const START_HINT =
  'Start it from the mechkit folder with:  uv run python -m mechkit studio  and then press "Try again".';

/** Turns a failed project-list request into words. */
export function describeProjectsError(e: unknown): Problem {
  const err = (e ?? {}) as ErrorLike;
  const detail = typeof err.message === "string" ? err.message : String(e);
  if (err.kind === "network" || (err.kind === "http" && Number(err.status) >= 500)) {
    return { title: "The MechKit Studio server is not running", detail, hint: START_HINT };
  }
  return {
    title: "The project list could not be read",
    detail,
    hint: 'Check the terminal where the server runs for an error, then press "Try again".',
  };
}

/** Turns a failed manifest request into words. */
export function describeManifestError(e: unknown, projectName: string, version: string): Problem {
  const err = (e ?? {}) as ErrorLike;
  const detail = typeof err.message === "string" ? err.message : String(e);
  if (err.kind === "network") {
    return { title: "The MechKit Studio server stopped answering", detail, hint: START_HINT };
  }
  if (err.kind === "http" && err.status === 404) {
    return {
      title: `${projectName} ${version} was not found`,
      detail,
      hint: "It may have been rebuilt or removed. Pick another version, or reload the page to refresh the project list.",
    };
  }
  return {
    title: `${projectName} ${version} failed to load`,
    detail,
    hint: 'Rebuild the project\'s presentation (uv run python -m mechkit present "<project folder>"), then press "Try again".',
  };
}
