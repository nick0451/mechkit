import { describe, expect, it } from "vitest";
import type { Part, Vec3 } from "../types";
import type { CameraState } from "./api";
import {
  basisFor,
  basisOf,
  clipRange,
  cloneState,
  fitToPoints,
  isValidState,
  orbit,
  pan,
  project,
  unprojectOnTargetPlane,
  viewDirection,
  zoomAt,
} from "./camera";
import { boxCorners, explodeAmount, explodeOffset, movedCentre, movedCorners } from "./explode";
import { frameFromParentMatrix, IDENTITY, invertAffine, kitDirToWorld, kitToWorld, multiply, worldDirToKit, worldToKit } from "./frame";
import { findItemNodes } from "./nodes";
import { cross, dot, length, rotateAbout, sub } from "./vec";

const close = (a: readonly number[], b: readonly number[], eps = 1e-9) => {
  expect(a.length).toBe(b.length);
  for (let i = 0; i < a.length; i++) expect(Math.abs(a[i] - b[i])).toBeLessThan(eps);
};

/** Column-major rotation matrix from a quaternion (x, y, z, w), as three.js builds it. */
function fromQuaternion(x: number, y: number, z: number, w: number, t: Vec3 = [0, 0, 0], s = 1): number[] {
  const x2 = x + x, y2 = y + y, z2 = z + z;
  const xx = x * x2, xy = x * y2, xz = x * z2, yy = y * y2, yz = y * z2, zz = z * z2;
  const wx = w * x2, wy = w * y2, wz = w * z2;
  return [
    (1 - (yy + zz)) * s, (xy + wz) * s, (xz - wy) * s, 0,
    (xy - wz) * s, (1 - (xx + zz)) * s, (yz + wx) * s, 0,
    (xz + wy) * s, (yz - wx) * s, (1 - (xx + yy)) * s, 0,
    t[0], t[1], t[2], 1,
  ];
}

// What the real GLB has (measured 2026-11-25): root "model" rotation [-0.7071, 0, 0, 0.7071]; the viewer puts it
// under a wrapper scaled by 1000, so the item nodes' parent world matrix is rotation * 1000.
const ROOT = fromQuaternion(-Math.SQRT1_2, 0, 0, Math.SQRT1_2, [0, 0, 0], 1000);

describe("frame", () => {
  const f = frameFromParentMatrix(ROOT, 0.001);

  it("is a plain rotation in millimetres for the real root node", () => {
    expect(f.rigid).toBe(true);
    expect(f.scale).toBeCloseTo(1, 12);
  });

  it("turns kit Z-up into world Y-up, and kit +Y (front) into world -Z", () => {
    close(kitToWorld(f, [0, 0, 10]), [0, 10, 0]);
    close(kitToWorld(f, [0, 10, 0]), [0, 0, -10]);
    close(kitToWorld(f, [10, 0, 0]), [10, 0, 0]);
    close(kitDirToWorld(f, [0, 0, 1]), [0, 1, 0]);
  });

  it("round-trips points and directions", () => {
    const pts: Vec3[] = [[0, 0, 0], [1, 2, 3], [-75, -57.6, -59.9161], [43.1, 108.429, 25.4]];
    for (const p of pts) {
      close(worldToKit(f, kitToWorld(f, p)), p, 1e-9);
      close(worldDirToKit(f, kitDirToWorld(f, p)), p, 1e-9);
    }
  });

  it("round-trips through a frame with translation, an odd rotation and another scale", () => {
    const g = frameFromParentMatrix(fromQuaternion(0.1825742, 0.3651484, 0.5477226, 0.7302967, [5, -7, 11], 250), 0.001);
    expect(g.rigid).toBe(true);
    expect(g.scale).toBeCloseTo(0.25, 6);
    const p: Vec3 = [12.5, -40, 7];
    close(worldToKit(g, kitToWorld(g, p)), p, 1e-9);
    // distances scale by frame.scale
    const a = kitToWorld(g, [0, 0, 0]);
    const b = kitToWorld(g, [3, 4, 0]);
    expect(length(sub(b, a))).toBeCloseTo(5 * 0.25, 6);
  });

  it("flags a mirrored or sheared matrix as not rigid", () => {
    const mirrored = [...IDENTITY];
    mirrored[0] = -1;
    expect(frameFromParentMatrix(mirrored, 1).rigid).toBe(false);
    const squashed = [...IDENTITY];
    squashed[5] = 2;
    expect(frameFromParentMatrix(squashed, 1).rigid).toBe(false);
  });

  it("invertAffine really inverts", () => {
    const m = fromQuaternion(0.1825742, 0.3651484, 0.5477226, 0.7302967, [5, -7, 11], 3);
    close(multiply(m, invertAffine(m)), [...IDENTITY], 1e-6);
    expect(() => invertAffine(new Array(16).fill(0))).toThrow();
  });
});

describe("explode", () => {
  const part = {
    key: "Bezel",
    explode: [0, 98.48, 17.36] as Vec3,
    centre: [0, 4.34, -34.34] as Vec3,
    bbox: [[-24, -1.42, -58.18], [24, 9.95, -10.56]] as [Vec3, Vec3],
  } as unknown as Part;

  it("moves by t * explode", () => {
    close(explodeOffset(part, 0), [0, 0, 0]);
    close(explodeOffset(part, 1), [0, 98.48, 17.36]);
    close(explodeOffset(part, 0.25), [0, 24.62, 4.34]);
    close(movedCentre(part, 0.5), [0, 4.34 + 49.24, -34.34 + 8.68]);
  });

  it("the override map wins over the global amount, per key, and values are clamped", () => {
    expect(explodeAmount("a", 0.3, null)).toBe(0.3);
    expect(explodeAmount("a", 0.3, { b: 1 })).toBe(0.3);
    expect(explodeAmount("b", 0.3, { b: 1 })).toBe(1);
    expect(explodeAmount("b", 0.3, { b: 0 })).toBe(0);
    expect(explodeAmount("b", 7, null)).toBe(1);
    expect(explodeAmount("b", 0, { b: -2 })).toBe(0);
    expect(explodeAmount("b", Number.NaN, null)).toBe(0);
  });

  it("gives 8 distinct moved corners", () => {
    const c = movedCorners(part, 1);
    expect(c.length).toBe(8);
    expect(new Set(c.map((p) => p.join(","))).size).toBe(8);
    expect(Math.min(...c.map((p) => p[1]))).toBeCloseTo(-1.42 + 98.48, 9);
    expect(Math.max(...c.map((p) => p[2]))).toBeCloseTo(-10.56 + 17.36, 9);
    expect(boxCorners([[0, 0, 0], [1, 2, 3]]).length).toBe(8);
  });
});

describe("camera", () => {
  const state: CameraState = { eye: [330, 150, 150], target: [0, -20, -10], up: [0, 0, 1], height: 180 };
  const size = { width: 1200, height: 800 };

  it("basis is right-handed, orthonormal, and keeps kit Z upward in the picture", () => {
    const b = basisOf(state);
    expect(length(b.right)).toBeCloseTo(1, 12);
    expect(length(b.up)).toBeCloseTo(1, 12);
    expect(dot(b.right, b.up)).toBeCloseTo(0, 12);
    expect(dot(b.right, b.forward)).toBeCloseTo(0, 12);
    close(cross(b.right, b.up), [-b.forward[0], -b.forward[1], -b.forward[2]], 1e-12); // camera looks down -z
    expect(b.up[2]).toBeGreaterThan(0);
    expect(b.right[2]).toBeCloseTo(0, 12); // horizon is level
  });

  it("seen from the front (eye on +Y looking toward -Y), kit +X is on the picture's left", () => {
    // Eye on +Y looking toward -Y: right = forward x up = (0,-1,0) x (0,0,1) = (-1,0,0).
    const b = basisFor([0, -1, 0], [0, 0, 1]);
    close(b.right, [-1, 0, 0], 1e-12);
    close(b.up, [0, 0, 1], 1e-12);
  });

  it("survives an up hint along the view direction", () => {
    const b = basisFor([0, 0, -1], [0, 0, 1]);
    expect(length(b.right)).toBeCloseTo(1, 12);
    expect(dot(b.right, b.forward)).toBeCloseTo(0, 12);
    expect(length(b.up)).toBeCloseTo(1, 12);
  });

  it("projects the target to the middle and respects the picture height", () => {
    const p = project(state.target, state, size);
    expect(p.x).toBeCloseTo(600, 9);
    expect(p.y).toBeCloseTo(400, 9);
    expect(p.depth).toBeCloseTo(length(sub(state.target, state.eye)), 9);
    const b = basisOf(state);
    const top: Vec3 = [state.target[0] + b.up[0] * 90, state.target[1] + b.up[1] * 90, state.target[2] + b.up[2] * 90];
    expect(project(top, state, size).y).toBeCloseTo(0, 9); // half the height up = top edge; y runs down
    const right: Vec3 = [state.target[0] + b.right[0] * 135, state.target[1] + b.right[1] * 135, state.target[2] + b.right[2] * 135];
    expect(project(right, state, size).x).toBeCloseTo(1200, 9); // half-width = 90 * 1200/800
  });

  it("unproject is the inverse of project on the target plane", () => {
    for (const [px, py] of [[0, 0], [600, 400], [1000, 123], [37.5, 790]]) {
      const w = unprojectOnTargetPlane(px, py, state, size);
      const p = project(w, state, size);
      expect(p.x).toBeCloseTo(px, 8);
      expect(p.y).toBeCloseTo(py, 8);
    }
  });

  it("depth is negative behind the eye", () => {
    const behind: Vec3 = [660, 320, 310];
    expect(project(behind, state, size).depth).toBeLessThan(0);
  });

  it("cloneState copies a camera state independently, and isValidState rejects unusable ones", () => {
    const c = cloneState(state);
    expect(c).toEqual(state);
    c.eye[0] = 1;
    expect(state.eye[0]).toBe(330);
    expect(isValidState(state)).toBe(true);
    expect(isValidState({ ...state, target: [...state.eye] })).toBe(false);
    expect(isValidState({ ...state, height: 0 })).toBe(false);
    expect(isValidState({ ...state, eye: [Number.NaN, 0, 0] })).toBe(false);
  });

  describe("fit", () => {
    const pts = boxCorners([[-24, -130, -56], [43, 108, 25]]);
    const forward = viewDirection([330, 150, 150], [0, -20, -10])!;

    for (const aspect of [0.5, 1, 1.5, 3]) {
      it(`shows every point with the margin, touching one pair of edges (aspect ${aspect})`, () => {
        const margin = 0.1;
        const s = fitToPoints(pts, forward, [0, 0, 1], aspect, margin)!;
        const sz = { width: 1000 * aspect, height: 1000 };
        const pr = pts.map((p) => project(p, s, sz));
        const minX = Math.min(...pr.map((p) => p.x)), maxX = Math.max(...pr.map((p) => p.x));
        const minY = Math.min(...pr.map((p) => p.y)), maxY = Math.max(...pr.map((p) => p.y));
        expect(minX).toBeGreaterThanOrEqual(-1e-6);
        expect(maxX).toBeLessThanOrEqual(sz.width + 1e-6);
        expect(minY).toBeGreaterThanOrEqual(-1e-6);
        expect(maxY).toBeLessThanOrEqual(sz.height + 1e-6);
        // centred
        expect((minX + maxX) / 2).toBeCloseTo(sz.width / 2, 6);
        expect((minY + maxY) / 2).toBeCloseTo(sz.height / 2, 6);
        // the tighter direction fills 1 / (1 + margin) of the picture
        const fill = Math.max((maxX - minX) / sz.width, (maxY - minY) / sz.height);
        expect(fill).toBeCloseTo(1 / (1 + margin), 6);
        // every point is in front of the eye
        expect(Math.min(...pr.map((p) => p.depth))).toBeGreaterThan(0);
      });
    }

    it("keeps the direction and the up it was given", () => {
      const s = fitToPoints(pts, forward, [0, 0, 1], 1.5)!;
      close(viewDirection(s.eye, s.target)!, forward, 1e-12);
      expect(s.up).toEqual([0, 0, 1]);
    });

    it("re-fitting from a fitted camera changes nothing (fit() is stable)", () => {
      const s1 = fitToPoints(pts, forward, [0, 0, 1], 1.5)!;
      const s2 = fitToPoints(pts, basisOf(s1).forward, s1.up, 1.5)!;
      close(s2.eye, s1.eye, 1e-9);
      close(s2.target, s1.target, 1e-9);
      expect(s2.height).toBeCloseTo(s1.height, 9);
    });

    it("returns null for nothing, and a usable camera for a single point", () => {
      expect(fitToPoints([], forward, [0, 0, 1], 1)).toBeNull();
      const s = fitToPoints([[1, 2, 3]], forward, [0, 0, 1], 1)!;
      expect(isValidState(s)).toBe(true);
      close(s.target, [1, 2, 3], 1e-9);
    });
  });

  it("clip range holds every point with room to spare", () => {
    const pts = boxCorners([[-75, -130, -60], [75, 110, 90]]);
    const { near, far } = clipRange(state, pts);
    for (const p of pts) {
      const d = project(p, state, size).depth;
      expect(d).toBeGreaterThan(near);
      expect(d).toBeLessThan(far);
    }
  });

  describe("orbit", () => {
    it("keeps the target, the distance, the up and the height", () => {
      const o = orbit(state, 0.7, -0.3);
      expect(o.target).toEqual(state.target);
      expect(o.up).toEqual(state.up);
      expect(o.height).toBe(state.height);
      expect(length(sub(o.eye, o.target))).toBeCloseTo(length(sub(state.eye, state.target)), 9);
    });

    it("yaw turns about the up axis: the eye's height above the target does not change", () => {
      const o = orbit(state, 1.1, 0);
      expect(o.eye[2]).toBeCloseTo(state.eye[2], 9);
      // positive yaw moves the eye toward its own right
      const b = basisOf(state);
      expect(dot(sub(orbit(state, 0.05, 0).eye, state.eye), b.right)).toBeGreaterThan(0);
    });

    it("positive pitch lifts the eye; opposite orbits undo each other", () => {
      expect(orbit(state, 0, 0.2).eye[2]).toBeGreaterThan(state.eye[2]);
      const back = orbit(orbit(state, 0, 0.2), 0, -0.2);
      close(back.eye, state.eye, 1e-9);
      const back2 = orbit(orbit(state, 0.4, 0), -0.4, 0);
      close(back2.eye, state.eye, 1e-9);
    });

    it("never goes over the pole, and the horizon stays level", () => {
      let s = state;
      for (let i = 0; i < 50; i++) s = orbit(s, 0.1, 0.3);
      const v = sub(s.eye, s.target);
      const angle = Math.acos(dot(v, [0, 0, 1]) / length(v));
      expect(angle).toBeGreaterThan(0.019);
      const b = basisOf(s);
      expect(Math.abs(b.right[2])).toBeLessThan(1e-9);
      expect(b.up[2]).toBeGreaterThan(0);
      for (let i = 0; i < 50; i++) s = orbit(s, 0.1, -0.3);
      const v2 = sub(s.eye, s.target);
      expect(Math.acos(dot(v2, [0, 0, 1]) / length(v2))).toBeLessThan(Math.PI - 0.019);
    });
  });

  it("pan moves the scene with the pointer and keeps the direction", () => {
    const p = pan(state, 30, -20, size);
    const before = project([0, 0, 0], state, size);
    const after = project([0, 0, 0], p, size);
    expect(after.x - before.x).toBeCloseTo(30, 8);
    expect(after.y - before.y).toBeCloseTo(-20, 8);
    close(viewDirection(p.eye, p.target)!, viewDirection(state.eye, state.target)!, 1e-12);
    expect(p.height).toBe(state.height);
  });

  it("zoom keeps what is under the pointer in place", () => {
    const px = 900, py = 200;
    const under = unprojectOnTargetPlane(px, py, state, size);
    const z = zoomAt(state, 0.5, px, py, size);
    expect(z.height).toBeCloseTo(90, 9);
    const p = project(under, z, size);
    expect(p.x).toBeCloseTo(px, 8);
    expect(p.y).toBeCloseTo(py, 8);
    close(viewDirection(z.eye, z.target)!, viewDirection(state.eye, state.target)!, 1e-12);
    // clamped at the limits
    expect(zoomAt(state, 1e-9, px, py, size).height).toBeGreaterThan(0);
  });

  it("rotateAbout is a right-handed rotation", () => {
    close(rotateAbout([1, 0, 0], [0, 0, 1], Math.PI / 2), [0, 1, 0], 1e-12);
  });
});

describe("findItemNodes (which node of the loaded model is which item)", () => {
  interface N {
    name: string;
    userData: Record<string, unknown>;
    children: N[];
  }
  /** A node as the glTF loader leaves it: `name` made unique, the file's own name kept in userData.name. */
  const node = (name: string, children: N[] = [], original: string | null = name): N => ({
    name,
    userData: original === null ? {} : { name: original },
    children,
  });
  /** scene -> model -> one node per key, each with a mesh child called COMPOUND (made unique by the loader). */
  function scene(keys: string[]): { root: N; model: N; items: N[] } {
    const used = new Map<string, number>([["model", 1]]);
    const unique = (n: string) => {
      const seen = used.get(n) ?? 0;
      used.set(n, seen + 1);
      return seen === 0 ? n : `${n}_${seen}`;
    };
    const items = keys.map((k) => {
      const self = unique(k); // parents are named before their children, as in the loader
      return node(self, [node(unique("COMPOUND"), [], "COMPOUND")], k);
    });
    const model = node("model", items);
    return { root: node("Scene", [model], null), model, items };
  }

  it("finds every item among the root node's children", () => {
    const { root, items } = scene(["Pod", "Bezel", "Knob"]);
    const found = findItemNodes(root, ["Pod", "Bezel", "Knob"]);
    expect([...found.keys()]).toEqual(["Pod", "Bezel", "Knob"]);
    expect(found.get("Bezel")).toBe(items[1]);
  });

  it("an item keyed `model` is the child node, not the root that shares its name", () => {
    const { root, model, items } = scene(["Pod", "model", "Knob"]);
    expect(items[1].name).toBe("model_1"); // what the loader does to the duplicate
    const found = findItemNodes(root, ["Pod", "model", "Knob"]);
    expect(found.get("model")).toBe(items[1]);
    expect(found.get("model")).not.toBe(model);
    expect(found.size).toBe(3);
  });

  it("an item keyed `COMPOUND` is the item node, not another item's mesh child", () => {
    const { root, items } = scene(["Pod", "COMPOUND", "Knob"]);
    const found = findItemNodes(root, ["Pod", "COMPOUND", "Knob"]);
    expect(found.get("COMPOUND")).toBe(items[1]);
    expect(items[0].children[0].userData.name).toBe("COMPOUND"); // the trap: an earlier node with that very name
    expect(found.get("Pod")).toBe(items[0]);
  });

  it("a mesh child never stands in for an item, even when its item is missing", () => {
    const { root } = scene(["Pod", "Knob"]);
    const found = findItemNodes(root, ["Pod", "Knob", "COMPOUND"]);
    expect(found.size).toBe(2);
    expect(found.has("COMPOUND")).toBe(false);
  });

  it("uses the loader's cleaned-up name when the file's own name was not kept", () => {
    const item = node("Bolt_M3", [], null);
    const root = node("Scene", [node("model", [item], null)], null);
    const sanitise = (s: string) => s.replace(/\s/g, "_");
    expect(findItemNodes(root, ["Bolt M3"], sanitise).get("Bolt M3")).toBe(item);
    expect(findItemNodes(root, ["Bolt M3"]).size).toBe(0);
  });

  it("gives an empty result when nothing matches, and one node is never two items", () => {
    const { root } = scene(["Pod"]);
    expect(findItemNodes(root, ["Nope"]).size).toBe(0);
    expect(findItemNodes(root, ["Pod", "Pod"]).size).toBe(1);
  });
});
