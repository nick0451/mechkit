import { describe, expect, it } from "vitest";
import { leaderStart, placeBalloons } from "./layout";

describe("placeBalloons", () => {
  it("keeps balloons from touching, even for anchors that almost coincide", () => {
    const pts = [...Array(8).keys()].map((i) => ({ x: i * 10, y: i * 2 }));
    pts.push({ x: 40, y: 8.5 }, { x: 40.5, y: 8 });
    const spots = placeBalloons(pts, 5, 30);
    let closest = Infinity;
    for (let i = 0; i < spots.length; i++)
      for (let j = i + 1; j < spots.length; j++) closest = Math.min(closest, Math.hypot(spots[i].x - spots[j].x, spots[i].y - spots[j].y));
    expect(closest).toBeGreaterThanOrEqual(10);
  });

  it("puts balloons to the side of a horizontal stack, not along it", () => {
    const pts = [0, 50, 100, 150].map((x) => ({ x, y: 0 }));
    for (const [i, s] of placeBalloons(pts, 5, 30).entries()) {
      expect(Math.abs(s.y)).toBeGreaterThan(20);
      expect(Math.abs(s.x - pts[i].x)).toBeLessThan(15);
    }
  });

  it("respects bounds and handles an empty list", () => {
    expect(placeBalloons([], 5, 30)).toEqual([]);
    const spots = placeBalloons([{ x: 2, y: 2 }, { x: 98, y: 98 }], 5, 30, { width: 100, height: 100 });
    for (const s of spots) {
      expect(s.x).toBeGreaterThanOrEqual(9);
      expect(s.x).toBeLessThanOrEqual(91);
      expect(s.y).toBeGreaterThanOrEqual(9);
      expect(s.y).toBeLessThanOrEqual(91);
    }
  });
});

describe("leaderStart", () => {
  it("starts on the rim, toward the anchor", () => {
    expect(leaderStart({ x: 0, y: 0 }, { x: 10, y: 0 }, 4)).toEqual({ x: 4, y: 0 });
  });
});
