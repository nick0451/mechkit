import { describe, expect, it } from "vitest";
import type { Manifest, Part, Vec3 } from "../types";
import { monitor } from "./fixture.monitor";
import { assertHasSteps, MIN_TRAVEL_MM, needRows, STEP_EXPLODE, stepExplodeMap, stepSets, stepTravel } from "./steps";

const len = (v: Vec3): number => Math.hypot(v[0], v[1], v[2]);
const part = (m: Manifest, key: string): Part => m.parts.find((p) => p.key === key)!;
/** How far (mm) a part moves in the step picture. */
const moved = (m: Manifest, map: Record<string, number>, key: string): number => map[key] * len(part(m, key).explode);

describe("stepSets (real manifest)", () => {
  it("shows everything fitted so far, never the reference part, and highlights this step's items", () => {
    const s1 = stepSets(monitor, 0);
    expect(s1.visible.sort()).toEqual(["Insert_M3_pod_L", "Insert_M3_pod_R", "Pod"]);
    expect(s1.highlighted.sort()).toEqual(["Insert_M3_pod_L", "Insert_M3_pod_R", "Pod"]);

    const s3 = stepSets(monitor, 2);
    expect(s3.highlighted.sort()).toEqual(["Display_Board", "Display_Screen"]);
    expect(s3.visible).toHaveLength(8);
    expect(s3.visible).toContain("Clamp");
    expect(s3.visible).not.toContain("Cover");
  });

  it("ends with all 18 non-reference items and each item highlighted in exactly one step", () => {
    const last = stepSets(monitor, monitor.steps.length - 1);
    expect(last.visible).toHaveLength(18);
    expect(last.visible).not.toContain("Monitor");
    const seen = monitor.steps.flatMap((_, i) => stepSets(monitor, i).highlighted);
    expect(seen).toHaveLength(18);
    expect(new Set(seen).size).toBe(18);
  });

  it("drops unknown keys and reference items, and refuses a bad index", () => {
    const m: Manifest = { ...monitor, steps: [{ title: "t", text: "x", add: ["Pod", "Monitor", "Nope"] }] };
    expect(stepSets(m, 0)).toEqual({ visible: ["Pod"], highlighted: ["Pod"] });
    expect(() => stepSets(monitor, 7)).toThrow(RangeError);
    expect(() => stepSets(monitor, -1)).toThrow(RangeError);
  });
});

describe("needRows (real manifest)", () => {
  it("groups items sharing a label and adds up their counts", () => {
    expect(needRows(monitor, 0)).toEqual([
      { label: 2, part: "Pod", qty: 1 },
      { label: 6, part: "Heat-set insert M3", qty: 2 },
    ]);
    expect(needRows(monitor, 3)).toEqual([
      { label: 4, part: "Cover", qty: 1 },
      { label: 7, part: "Bolt M3 x 10, socket head", qty: 2 },
    ]);
  });

  it("counts the display once although it is two items (the screen has count 0)", () => {
    expect(needRows(monitor, 2)).toEqual([{ label: 3, part: "Round display GC9A01 1.28 in", qty: 1 }]);
  });

  it("keeps a row whose only item has count 0, with quantity 0", () => {
    const m: Manifest = { ...monitor, steps: [{ title: "t", text: "x", add: ["Display_Screen"] }] };
    expect(needRows(m, 0)).toEqual([{ label: 3, part: "Round display GC9A01 1.28 in", qty: 0 }]);
  });

  it("over all steps adds up to the parts table's quantities", () => {
    const total = new Map<number, number>();
    monitor.steps.forEach((_, i) => {
      for (const r of needRows(monitor, i)) total.set(r.label, (total.get(r.label) ?? 0) + r.qty);
    });
    for (const row of monitor.table) expect(total.get(row.label)).toBe(row.qty);
    expect(total.size).toBe(13);
  });
});

describe("assertHasSteps", () => {
  it("passes with steps and gives a clear error without", () => {
    expect(() => assertHasSteps(monitor)).not.toThrow();
    expect(() => assertHasSteps({ ...monitor, steps: [] })).toThrow(/no assembly order/);
  });
});

describe("stepTravel", () => {
  it("uses the share of the full distance, but at least the minimum and never more than the full distance", () => {
    expect(stepTravel(100)).toBeCloseTo(100 * STEP_EXPLODE);
    expect(stepTravel(20)).toBe(MIN_TRAVEL_MM);
    expect(stepTravel(6)).toBe(6);
    expect(stepTravel(0)).toBe(0);
  });
});

describe("stepExplodeMap (real manifest)", () => {
  it("has an amount in 0..1 for every part in every step, 0 for parts not yet fitted and for the reference part", () => {
    monitor.steps.forEach((_, i) => {
      const map = stepExplodeMap(monitor, i);
      const { visible } = stepSets(monitor, i);
      expect(Object.keys(map).sort()).toEqual(monitor.parts.map((p) => p.key).sort());
      for (const p of monitor.parts) {
        expect(map[p.key]).toBeGreaterThanOrEqual(0);
        expect(map[p.key]).toBeLessThanOrEqual(1);
        if (!visible.includes(p.key)) expect(map[p.key]).toBe(0);
      }
      expect(map.Monitor).toBe(0);
    });
  });

  it("plain rule: only this step's parts move", () => {
    monitor.steps.forEach((_, i) => {
      const map = stepExplodeMap(monitor, i, { moveBlockers: false });
      const { highlighted } = stepSets(monitor, i);
      for (const p of monitor.parts) {
        if (highlighted.includes(p.key)) expect(moved(monitor, map, p.key)).toBeCloseTo(stepTravel(len(p.explode)));
        else expect(map[p.key]).toBe(0);
      }
    });
  });

  it("every step part with an explode vector separates by at least the minimum travel (or its full distance)", () => {
    monitor.steps.forEach((_, i) => {
      const map = stepExplodeMap(monitor, i);
      for (const key of stepSets(monitor, i).highlighted) {
        const full = len(part(monitor, key).explode);
        if (full > 0) expect(moved(monitor, map, key)).toBeGreaterThanOrEqual(Math.min(full, MIN_TRAVEL_MM) - 1e-9);
      }
    });
    // step 2: the M4 insert's full distance is 6 mm, the M3 insert's 10 mm: both go all the way
    const s2 = stepExplodeMap(monitor, 1);
    expect(s2.Insert_M4_clamp).toBe(1);
    expect(s2.Insert_M3_cap).toBe(1);
    expect(s2.Clamp).toBe(0);
  });

  it("step 3: the pod (fitted in step 1) moves out of the display's way, as one block with its inserts; the clamp stays", () => {
    const map = stepExplodeMap(monitor, 2);
    const display = moved(monitor, map, "Display_Board");
    expect(moved(monitor, map, "Display_Screen")).toBeCloseTo(display);
    const dir = part(monitor, "Display_Board").explode.map((c) => c / len(part(monitor, "Display_Board").explode)) as Vec3;
    const along = (key: string): number => {
      const e = part(monitor, key).explode;
      return map[key] * (e[0] * dir[0] + e[1] * dir[1] + e[2] * dir[2]);
    };
    expect(along("Pod")).toBeGreaterThanOrEqual(display + MIN_TRAVEL_MM - 1e-6);
    expect(along("Insert_M3_pod_L")).toBeCloseTo(along("Pod"));
    expect(along("Insert_M3_pod_R")).toBeCloseTo(along("Pod"));
    expect(map.Clamp).toBe(0);
    expect(map.Insert_M3_cap).toBe(0);
    expect(map.Insert_M4_clamp).toBe(0);
  });

  it("step 4: pod, inserts and display move ahead of the cover together; the bolts go the other way", () => {
    const map = stepExplodeMap(monitor, 3);
    const cover = moved(monitor, map, "Cover");
    const pod = moved(monitor, map, "Pod");
    expect(pod).toBeGreaterThan(cover);
    expect(moved(monitor, map, "Display_Board")).toBeCloseTo(pod);
    expect(moved(monitor, map, "Display_Screen")).toBeCloseTo(pod);
    expect(moved(monitor, map, "Insert_M3_pod_L")).toBeCloseTo(pod);
    expect(moved(monitor, map, "Bolt_M3x10_pod_L")).toBeGreaterThanOrEqual(MIN_TRAVEL_MM);
    expect(map.Clamp).toBe(0);
  });

  it("steps 5 to 7: nothing fitted earlier is in the way, so only the step's own parts move", () => {
    for (const i of [4, 5, 6]) {
      const map = stepExplodeMap(monitor, i);
      const { highlighted } = stepSets(monitor, i);
      for (const p of monitor.parts) if (!highlighted.includes(p.key)) expect(map[p.key]).toBe(0);
    }
  });
});
