// Orthographic camera maths. Pure: no three.js, no DOM (unit-tested in node).
// Everything here is in ONE frame (the kit frame, mm); viewer.ts converts to three's world only when it applies the
// result to the real camera. The basis matches THREE.Object3D.lookAt for a camera with the same eye / target / up.

import type { Vec3 } from "../types";
import type { CameraState } from "./api";
import { add, cross, dot, isFiniteVec, length, normalize, rotateAbout, scale, sub } from "./vec";

export interface Basis {
  right: Vec3; // picture +x
  up: Vec3; // picture up (square to forward; not necessarily state.up)
  forward: Vec3; // eye -> target
}

export interface Size {
  width: number;
  height: number;
}

export const MIN_HEIGHT = 0.5; // mm
export const MAX_HEIGHT = 1e5;

const AXES: Vec3[] = [
  [0, 0, 1],
  [0, 1, 0],
  [1, 0, 0],
];

/** Unit direction eye -> target, or null when they coincide. */
export function viewDirection(eye: Vec3, target: Vec3): Vec3 | null {
  return normalize(sub(target, eye));
}

/** Right / up / forward for a direction and an up hint. A hint along the direction falls back to a kit axis. */
export function basisFor(forward: Vec3, upHint: Vec3): Basis {
  const f = normalize(forward) ?? [0, -1, 0];
  let right = normalize(cross(f, upHint));
  if (!right || length(cross(f, normalize(upHint) ?? [0, 0, 0])) < 1e-6) {
    right = null;
    for (const axis of AXES) {
      if (Math.abs(dot(f, axis)) < 0.9) {
        right = normalize(cross(f, axis));
        break;
      }
    }
  }
  const r = right ?? [1, 0, 0];
  return { right: r, up: cross(r, f), forward: f };
}

export function basisOf(state: CameraState): Basis {
  return basisFor(sub(state.target, state.eye), state.up);
}

export function cloneState(s: CameraState): CameraState {
  return { eye: [...s.eye], target: [...s.target], up: [...s.up], height: s.height };
}

/** True when the state can be used as it is (finite numbers, eye apart from target, positive height). */
export function isValidState(s: CameraState): boolean {
  return (
    isFiniteVec(s.eye) &&
    isFiniteVec(s.target) &&
    isFiniteVec(s.up) &&
    Number.isFinite(s.height) &&
    s.height > 0 &&
    viewDirection(s.eye, s.target) !== null &&
    normalize(s.up) !== null
  );
}

export interface Projected {
  /** Pixels from the top-left of the picture, y down. */
  x: number;
  y: number;
  /** Distance in front of the eye along the view direction (negative = behind the eye). */
  depth: number;
}

/** Orthographic projection of a point into a picture of the given pixel size. */
export function project(p: Vec3, state: CameraState, size: Size): Projected {
  const b = basisOf(state);
  const rel = sub(p, state.target);
  const halfH = state.height / 2;
  const halfW = (halfH * size.width) / size.height;
  const nx = dot(rel, b.right) / halfW;
  const ny = dot(rel, b.up) / halfH;
  return {
    x: ((nx + 1) / 2) * size.width,
    y: ((1 - ny) / 2) * size.height,
    depth: dot(sub(p, state.eye), b.forward),
  };
}

/** The point on the plane through the target (square to the view) that a pixel shows. Inverse of project() there. */
export function unprojectOnTargetPlane(px: number, py: number, state: CameraState, size: Size): Vec3 {
  const b = basisOf(state);
  const halfH = state.height / 2;
  const halfW = (halfH * size.width) / size.height;
  const nx = (px / size.width) * 2 - 1;
  const ny = 1 - (py / size.height) * 2;
  return add(state.target, add(scale(b.right, nx * halfW), scale(b.up, ny * halfH)));
}

/**
 * Look along `forward` with `up`, and frame the points: the target is the middle of their extent as seen from that
 * direction, the height is the smallest that shows all of them in a picture of the given aspect (width / height),
 * times (1 + margin). The eye sits well outside the points. Returns null when there are no points.
 */
export function fitToPoints(points: Vec3[], forward: Vec3, up: Vec3, aspect: number, margin = 0.12): CameraState | null {
  if (points.length === 0) return null;
  const b = basisFor(forward, up);
  let minR = Infinity, maxR = -Infinity, minU = Infinity, maxU = -Infinity, minF = Infinity, maxF = -Infinity;
  for (const p of points) {
    const r = dot(p, b.right), u = dot(p, b.up), f = dot(p, b.forward);
    if (r < minR) minR = r;
    if (r > maxR) maxR = r;
    if (u < minU) minU = u;
    if (u > maxU) maxU = u;
    if (f < minF) minF = f;
    if (f > maxF) maxF = f;
  }
  const a = Number.isFinite(aspect) && aspect > 0 ? aspect : 1;
  const w = maxR - minR;
  const h = maxU - minU;
  const d = maxF - minF;
  const height = Math.min(MAX_HEIGHT, Math.max(MIN_HEIGHT, Math.max(h, w / a) * (1 + margin)));
  const target = add(
    add(scale(b.right, (minR + maxR) / 2), scale(b.up, (minU + maxU) / 2)),
    scale(b.forward, (minF + maxF) / 2),
  );
  const distance = Math.max(d, w, h, 1) * 2;
  return { eye: sub(target, scale(b.forward, distance)), target, up: [...up], height };
}

/** Near and far for an orthographic camera at `state` so that all the points are inside, with padding. */
export function clipRange(state: CameraState, points: Vec3[]): { near: number; far: number } {
  const b = basisOf(state);
  let lo = Infinity, hi = -Infinity;
  for (const p of points) {
    const f = dot(sub(p, state.eye), b.forward);
    if (f < lo) lo = f;
    if (f > hi) hi = f;
  }
  if (!Number.isFinite(lo) || !Number.isFinite(hi)) {
    const dist = length(sub(state.target, state.eye));
    lo = dist - 1000;
    hi = dist + 1000;
  }
  const pad = Math.max(10, (hi - lo) * 0.25);
  return { near: lo - pad, far: hi + pad };
}

const POLE_LIMIT = 0.02; // radians kept between the view direction and the turntable axis

/**
 * Turntable orbit about the target: `yaw` radians about state.up, `pitch` radians toward the up axis
 * (positive = the eye climbs). The eye never passes over the pole. Target, up and height are unchanged.
 */
export function orbit(state: CameraState, yaw: number, pitch: number): CameraState {
  const axis = normalize(state.up) ?? [0, 0, 1];
  let v = sub(state.eye, state.target);
  const dist = length(v);
  if (dist < 1e-9) return cloneState(state);
  v = rotateAbout(v, axis, yaw);
  const cosNow = Math.min(1, Math.max(-1, dot(v, axis) / dist));
  const angleNow = Math.acos(cosNow); // 0 = eye straight above the target
  const angleNew = Math.min(Math.PI - POLE_LIMIT, Math.max(POLE_LIMIT, angleNow - pitch));
  let side = normalize(cross(axis, v));
  if (!side) {
    // Looking straight along the axis: any side will do, but take a stable one.
    side = basisFor(scale(v, -1), axis).right;
  }
  // Rotating about `side` by +a moves v away from the axis by a.
  v = rotateAbout(v, side, angleNew - angleNow);
  return { eye: add(state.target, v), target: [...state.target], up: [...state.up], height: state.height };
}

/** Drag the picture by (dx, dy) pixels (y down): the scene follows the pointer. */
export function pan(state: CameraState, dxPx: number, dyPx: number, size: Size): CameraState {
  const b = basisOf(state);
  const mmPerPx = state.height / size.height;
  const move = add(scale(b.right, -dxPx * mmPerPx), scale(b.up, dyPx * mmPerPx));
  return { eye: add(state.eye, move), target: add(state.target, move), up: [...state.up], height: state.height };
}

/** Multiply the picture height by `factor` (< 1 zooms in), keeping what is under pixel (px, py) where it is. */
export function zoomAt(state: CameraState, factor: number, px: number, py: number, size: Size): CameraState {
  const height = Math.min(MAX_HEIGHT, Math.max(MIN_HEIGHT, state.height * factor));
  const f = height / state.height;
  const under = unprojectOnTargetPlane(px, py, state, size);
  const move = scale(sub(under, state.target), 1 - f);
  return { eye: add(state.eye, move), target: add(state.target, move), up: [...state.up], height };
}
