// Small vector helpers on plain [x, y, z] arrays. Pure: no three.js, no DOM (unit-tested in node).

import type { Vec3 } from "../types";

export const add = (a: Vec3, b: Vec3): Vec3 => [a[0] + b[0], a[1] + b[1], a[2] + b[2]];
export const sub = (a: Vec3, b: Vec3): Vec3 => [a[0] - b[0], a[1] - b[1], a[2] - b[2]];
export const scale = (a: Vec3, s: number): Vec3 => [a[0] * s, a[1] * s, a[2] * s];
export const dot = (a: Vec3, b: Vec3): number => a[0] * b[0] + a[1] * b[1] + a[2] * b[2];
export const cross = (a: Vec3, b: Vec3): Vec3 => [
  a[1] * b[2] - a[2] * b[1],
  a[2] * b[0] - a[0] * b[2],
  a[0] * b[1] - a[1] * b[0],
];
export const length = (a: Vec3): number => Math.hypot(a[0], a[1], a[2]);

/** Unit vector, or null when the input is (nearly) zero or not finite. */
export function normalize(a: Vec3): Vec3 | null {
  const n = length(a);
  if (!Number.isFinite(n) || n < 1e-12) return null;
  return [a[0] / n, a[1] / n, a[2] / n];
}

/** Rotate v about a UNIT axis by angle (radians, right-handed). Rodrigues' formula. */
export function rotateAbout(v: Vec3, axis: Vec3, angle: number): Vec3 {
  const c = Math.cos(angle);
  const s = Math.sin(angle);
  const k = dot(axis, v) * (1 - c);
  const x = cross(axis, v);
  return [v[0] * c + x[0] * s + axis[0] * k, v[1] * c + x[1] * s + axis[1] * k, v[2] * c + x[2] * s + axis[2] * k];
}

export const isFiniteVec = (a: readonly number[]): boolean => a.length === 3 && a.every((n) => Number.isFinite(n));
