// Explode maths in the kit frame (mm). Pure: no three.js, no DOM (unit-tested in node).

import type { Box, Part, Vec3 } from "../types";

export const clamp01 = (t: number): number => (Number.isFinite(t) ? Math.min(1, Math.max(0, t)) : 0);

/** The explode amount that applies to one part: its entry in the override map if it has one, else the global value. */
export function explodeAmount(key: string, global: number, map: Record<string, number> | null): number {
  if (map && Object.prototype.hasOwnProperty.call(map, key)) return clamp01(map[key]);
  return clamp01(global);
}

/** How far a part has moved, mm, kit frame: t * part.explode. */
export function explodeOffset(part: Pick<Part, "explode">, t: number): Vec3 {
  return [part.explode[0] * t, part.explode[1] * t, part.explode[2] * t];
}

/** Where the part's centre is now. */
export function movedCentre(part: Pick<Part, "centre" | "explode">, t: number): Vec3 {
  const o = explodeOffset(part, t);
  return [part.centre[0] + o[0], part.centre[1] + o[1], part.centre[2] + o[2]];
}

/** The 8 corners of a box moved by an offset. */
export function boxCorners(box: Box, offset: Vec3 = [0, 0, 0]): Vec3[] {
  const [lo, hi] = box;
  const out: Vec3[] = [];
  for (let i = 0; i < 8; i++) {
    out.push([
      (i & 1 ? hi[0] : lo[0]) + offset[0],
      (i & 2 ? hi[1] : lo[1]) + offset[1],
      (i & 4 ? hi[2] : lo[2]) + offset[2],
    ]);
  }
  return out;
}

/** Corners of a part's box at explode amount t. */
export function movedCorners(part: Pick<Part, "bbox" | "explode">, t: number): Vec3[] {
  return boxCorners(part.bbox, explodeOffset(part, t));
}
