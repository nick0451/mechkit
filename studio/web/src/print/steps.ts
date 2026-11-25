// Pure logic for the assembly guide: what each step's picture shows and what its "You need" list says.
// No DOM, no viewer: tested in steps.test.ts.
import type { Box, Manifest, Part, Vec3 } from "../types";

/**
 * How far a step's own parts are pulled out in that step's picture, as a share of their full explode distance.
 * The manifest's distances are tuned for the whole exploded view; at 1.0 a single step's parts fly far from the rest.
 */
export const STEP_EXPLODE = 0.45;

/**
 * A part whose full explode distance is short (an insert that moves 6 mm) would hardly separate at STEP_EXPLODE.
 * Such a part travels at least this far, but never further than its full explode distance.
 */
export const MIN_TRAVEL_MM = 12;

/**
 * true: parts fitted in EARLIER steps that sit in the way of this step's parts move outward too, as one block
 * (step "seat the display": the pod, fitted in step 1, is further out than the display along the same line; if it
 * stayed put the display would be drawn pushed through the pod's front).
 * false: the plain rule, this step's parts move and everything else stays assembled.
 */
export const MOVE_BLOCKERS = true;

const EPS = 1e-6;
const TOUCH_MM = 0.05; // boxes this close count as touching

export interface NeedRow {
  label: number;
  part: string;
  /** Sum of the items' `count`. 0 when the step only adds a second piece of something already counted. */
  qty: number;
}

export interface StepSets {
  /** Everything fitted in steps 1..i, reference items left out, in the manifest's part order. */
  visible: string[];
  /** The items fitted in step i itself. */
  highlighted: string[];
}

export function assertHasSteps(manifest: Manifest): void {
  if (!manifest.steps || manifest.steps.length === 0) {
    throw new Error(
      `"${manifest.project}" ${manifest.version} has no assembly order (the manifest lists no steps), so there is no assembly guide to print.`,
    );
  }
}

function checkIndex(manifest: Manifest, index: number): void {
  if (!Number.isInteger(index) || index < 0 || index >= manifest.steps.length) {
    throw new RangeError(`step index ${index} is outside 0..${manifest.steps.length - 1}`);
  }
}

/** The step's items that exist in the manifest and are not reference items, in the manifest's part order. */
export function stepParts(manifest: Manifest, index: number): Part[] {
  checkIndex(manifest, index);
  const wanted = new Set(manifest.steps[index].add);
  return manifest.parts.filter((p) => wanted.has(p.key) && p.kind !== "reference");
}

/** index is 0-based: step N of the guide is index N - 1. */
export function stepSets(manifest: Manifest, index: number): StepSets {
  checkIndex(manifest, index);
  const now = new Set(stepParts(manifest, index).map((p) => p.key));
  const sofar = new Set<string>();
  for (let i = 0; i <= index; i++) for (const k of manifest.steps[i].add) sofar.add(k);
  const visible = manifest.parts.filter((p) => sofar.has(p.key) && p.kind !== "reference").map((p) => p.key);
  return { visible, highlighted: visible.filter((k) => now.has(k)) };
}

/** Rows of a step's "You need" list: items sharing a label are one row; quantities add up. Sorted by label. */
export function needRows(manifest: Manifest, index: number): NeedRow[] {
  const rows = new Map<number, NeedRow>();
  for (const p of stepParts(manifest, index)) {
    const row = rows.get(p.label);
    if (row) row.qty += p.count;
    else rows.set(p.label, { label: p.label, part: p.part, qty: p.count });
  }
  return [...rows.values()].sort((a, b) => a.label - b.label);
}

// ---- explode amounts for a step picture --------------------------------------------------------------------------

const len = (v: Vec3): number => Math.hypot(v[0], v[1], v[2]);
const dot = (a: Vec3, b: Vec3): number => a[0] * b[0] + a[1] * b[1] + a[2] * b[2];

/** How far (mm) a part with the given full explode distance moves in a step picture. */
export function stepTravel(fullDistance: number, amount: number = STEP_EXPLODE): number {
  if (fullDistance <= EPS) return 0;
  return Math.min(fullDistance, Math.max(amount * fullDistance, MIN_TRAVEL_MM));
}

function sweep(box: Box, move: Vec3): Box {
  const lo: Vec3 = [0, 0, 0];
  const hi: Vec3 = [0, 0, 0];
  for (let a = 0; a < 3; a++) {
    lo[a] = Math.min(box[0][a], box[0][a] + move[a]);
    hi[a] = Math.max(box[1][a], box[1][a] + move[a]);
  }
  return [lo, hi];
}

function touches(a: Box, b: Box): boolean {
  for (let i = 0; i < 3; i++) if (a[0][i] > b[1][i] + TOUCH_MM || b[0][i] > a[1][i] + TOUCH_MM) return false;
  return true;
}

export interface StepExplodeOptions {
  amount?: number;
  moveBlockers?: boolean;
}

/**
 * Explode amount (0..1 of its own explode vector) for EVERY part of the manifest in step `index`'s picture.
 * This step's parts are pulled out; parts of earlier steps stay assembled (0) unless they sit in the way (see
 * MOVE_BLOCKERS); everything else is 0 (and hidden anyway).
 *
 * "In the way" of a step part s means: fitted earlier, further out than s along s's explode direction in the
 * full exploded layout, AND its bounding box is crossed by s's box on its way out (or it touches such a part and is
 * also further out: an insert sitting in the pod goes with the pod). Those parts move the same distance along that
 * direction, so they stay together, and far enough to leave a gap ahead of s.
 */
export function stepExplodeMap(manifest: Manifest, index: number, options: StepExplodeOptions = {}): Record<string, number> {
  const amount = options.amount ?? STEP_EXPLODE;
  const moveBlockers = options.moveBlockers ?? MOVE_BLOCKERS;
  const { visible, highlighted } = stepSets(manifest, index);
  const byKey = new Map(manifest.parts.map((p) => [p.key, p] as const));
  const map: Record<string, number> = {};
  for (const p of manifest.parts) map[p.key] = 0;

  const now = highlighted.map((k) => byKey.get(k)!);
  for (const s of now) {
    const full = len(s.explode);
    map[s.key] = full > EPS ? stepTravel(full, amount) / full : 0;
  }
  if (!moveBlockers) return map;

  const nowKeys = new Set(highlighted);
  const earlier = visible.filter((k) => !nowKeys.has(k)).map((k) => byKey.get(k)!);
  for (const s of now) {
    const full = len(s.explode);
    if (full <= EPS) continue;
    const dir: Vec3 = [s.explode[0] / full, s.explode[1] / full, s.explode[2] / full];
    const travel = stepTravel(full, amount);
    const path = sweep(s.bbox, [dir[0] * travel, dir[1] * travel, dir[2] * travel]);
    const outboard = earlier.filter((e) => dot(e.explode, dir) > full + EPS);
    const block = outboard.filter((e) => touches(path, e.bbox));
    if (block.length === 0) continue;
    for (let grew = true; grew; ) {
      grew = false;
      for (const e of outboard) {
        if (!block.includes(e) && block.some((b) => touches(b.bbox, e.bbox))) {
          block.push(e);
          grew = true;
        }
      }
    }
    const nearest = Math.min(...block.map((e) => dot(e.explode, dir)));
    const distance = travel + stepTravel(nearest - full, amount); // never more than `nearest`
    for (const e of block) {
      const t = Math.min(1, distance / dot(e.explode, dir));
      if (t > map[e.key]) map[e.key] = t;
    }
  }
  return map;
}
