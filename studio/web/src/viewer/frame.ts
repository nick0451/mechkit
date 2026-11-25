// Kit frame (mm, Z up, +Y toward the user) <-> three.js world. Pure: no three.js import (unit-tested in node).
//
// The conversion is DERIVED from the loaded model, never assumed: inside the GLB, an item node's local frame is the
// kit frame in metres (CONTRACT.md, "The GLB"), so the world matrix of the item nodes' PARENT maps kit metres to
// world. Multiply by 0.001 on the way in and you have kit millimetres -> world.
// Matrices are 16 numbers, column-major: exactly THREE.Matrix4.elements.

import type { Vec3 } from "../types";

export interface Frame {
  /** kit mm -> world, column-major 4x4 (affine). */
  readonly m: readonly number[];
  /** world -> kit mm. */
  readonly inv: readonly number[];
  /** World units per kit millimetre (1 when the scene is scaled to millimetres). */
  readonly scale: number;
  /** True when the 3x3 part is a rotation times one uniform scale (it should be). */
  readonly rigid: boolean;
}

export const IDENTITY: readonly number[] = [1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1];

/** a * b for column-major affine 4x4 matrices. */
export function multiply(a: ArrayLike<number>, b: ArrayLike<number>): number[] {
  const out = new Array<number>(16).fill(0);
  for (let c = 0; c < 4; c++) {
    for (let r = 0; r < 4; r++) {
      let s = 0;
      for (let k = 0; k < 4; k++) s += a[k * 4 + r] * b[c * 4 + k];
      out[c * 4 + r] = s;
    }
  }
  return out;
}

/** Inverse of an AFFINE column-major 4x4 (last row 0 0 0 1). Throws when it cannot be inverted. */
export function invertAffine(m: ArrayLike<number>): number[] {
  const a = m[0], b = m[4], c = m[8];
  const d = m[1], e = m[5], f = m[9];
  const g = m[2], h = m[6], i = m[10];
  const det = a * (e * i - f * h) - b * (d * i - f * g) + c * (d * h - e * g);
  if (!Number.isFinite(det) || Math.abs(det) < 1e-30) throw new Error("frame matrix cannot be inverted");
  const r00 = (e * i - f * h) / det, r01 = (c * h - b * i) / det, r02 = (b * f - c * e) / det;
  const r10 = (f * g - d * i) / det, r11 = (a * i - c * g) / det, r12 = (c * d - a * f) / det;
  const r20 = (d * h - e * g) / det, r21 = (b * g - a * h) / det, r22 = (a * e - b * d) / det;
  const tx = m[12], ty = m[13], tz = m[14];
  return [
    r00, r10, r20, 0,
    r01, r11, r21, 0,
    r02, r12, r22, 0,
    -(r00 * tx + r01 * ty + r02 * tz), -(r10 * tx + r11 * ty + r12 * tz), -(r20 * tx + r21 * ty + r22 * tz), 1,
  ];
}

/**
 * Build the frame from the world matrix of the item nodes' parent.
 * unitsPerMm: what one kit millimetre is in the item nodes' local units (0.001: the GLB is in metres).
 */
export function frameFromParentMatrix(parentWorld: ArrayLike<number>, unitsPerMm = 0.001): Frame {
  const m = Array.from({ length: 16 }, (_, k) => Number(parentWorld[k]));
  for (let k = 0; k < 12; k++) m[k] *= k % 4 === 3 ? 1 : unitsPerMm; // scale the three axis columns, not the translation
  const inv = invertAffine(m);
  const sx = Math.hypot(m[0], m[1], m[2]);
  const sy = Math.hypot(m[4], m[5], m[6]);
  const sz = Math.hypot(m[8], m[9], m[10]);
  const s = (sx + sy + sz) / 3;
  const tol = 1e-4 * s;
  const d01 = m[0] * m[4] + m[1] * m[5] + m[2] * m[6];
  const d02 = m[0] * m[8] + m[1] * m[9] + m[2] * m[10];
  const d12 = m[4] * m[8] + m[5] * m[9] + m[6] * m[10];
  const det =
    m[0] * (m[5] * m[10] - m[9] * m[6]) - m[4] * (m[1] * m[10] - m[9] * m[2]) + m[8] * (m[1] * m[6] - m[5] * m[2]);
  const rigid =
    Math.abs(sx - s) < tol &&
    Math.abs(sy - s) < tol &&
    Math.abs(sz - s) < tol &&
    Math.abs(d01) < tol * s &&
    Math.abs(d02) < tol * s &&
    Math.abs(d12) < tol * s &&
    det > 0;
  return { m, inv, scale: s, rigid };
}

function applyPoint(m: readonly number[], p: Vec3): Vec3 {
  return [
    m[0] * p[0] + m[4] * p[1] + m[8] * p[2] + m[12],
    m[1] * p[0] + m[5] * p[1] + m[9] * p[2] + m[13],
    m[2] * p[0] + m[6] * p[1] + m[10] * p[2] + m[14],
  ];
}

function applyDir(m: readonly number[], d: Vec3): Vec3 {
  return [
    m[0] * d[0] + m[4] * d[1] + m[8] * d[2],
    m[1] * d[0] + m[5] * d[1] + m[9] * d[2],
    m[2] * d[0] + m[6] * d[1] + m[10] * d[2],
  ];
}

/** A point: kit mm -> world. */
export const kitToWorld = (f: Frame, p: Vec3): Vec3 => applyPoint(f.m, p);
/** A point: world -> kit mm. */
export const worldToKit = (f: Frame, p: Vec3): Vec3 => applyPoint(f.inv, p);
/** A direction or offset (no translation): kit -> world. Lengths scale by frame.scale. */
export const kitDirToWorld = (f: Frame, d: Vec3): Vec3 => applyDir(f.m, d);
/** A direction or offset: world -> kit. */
export const worldDirToKit = (f: Frame, d: Vec3): Vec3 => applyDir(f.inv, d);
