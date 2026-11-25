import { describe, expect, it } from "vitest";
import type { BalloonAnchor } from "../viewer/api";
import { balloonMetrics, balloonSvg, layoutBalloons } from "./balloons";

const W = 2400;
const H = 1500;
const anchor = (key: string, label: number, x: number, y: number, visible = true): BalloonAnchor => ({ key, label, x, y, visible });

describe("balloonMetrics", () => {
  it("scales paper millimetres to image pixels", () => {
    const m = balloonMetrics(2400, 160); // 15 px per mm
    expect(m.r).toBeCloseTo(45);
    expect(m.reach).toBeCloseTo(135);
    expect(m.font).toBeLessThan(2 * m.r); // a two-digit number fits in the circle
  });
});

describe("layoutBalloons", () => {
  const anchors = [
    anchor("A", 1, 400, 700),
    anchor("B", 2, 800, 720),
    anchor("C", 3, 1200, 740),
    anchor("D", 4, 1600, 760),
    anchor("Hidden", 5, 1000, 500, false),
    anchor("Outside", 6, 3000, 500),
    anchor("Ref", 0, 900, 900),
  ];

  it("uses only visible anchors with a label, inside the picture", () => {
    const out = layoutBalloons(anchors, { width: W, height: H, printedWidthMm: 155 });
    expect(out.balloons.map((b) => b.key)).toEqual(["A", "B", "C", "D"]);
    expect(out.width).toBe(W);
    expect(out.height).toBe(H);
  });

  it("limits balloons to the given keys (a step's own parts)", () => {
    const out = layoutBalloons(anchors, { width: W, height: H, printedWidthMm: 155, keys: ["B", "D", "Hidden"] });
    expect(out.balloons.map((b) => b.label)).toEqual([2, 4]);
  });

  it("keeps balloons inside the picture, apart from each other, with leaders that start on the rim", () => {
    const crowded = [...Array(18).keys()].map((i) => anchor(`P${i}`, i + 1, 1100 + (i % 3) * 30, 300 + i * 50));
    const out = layoutBalloons(crowded, { width: W, height: H, printedWidthMm: 155 });
    const r = out.metrics.r;
    expect(out.balloons).toHaveLength(18);
    for (const b of out.balloons) {
      expect(b.bx).toBeGreaterThanOrEqual(r);
      expect(b.bx).toBeLessThanOrEqual(W - r);
      expect(b.by).toBeGreaterThanOrEqual(r);
      expect(b.by).toBeLessThanOrEqual(H - r);
      if (b.leader) expect(Math.hypot(b.leader.x - b.bx, b.leader.y - b.by)).toBeCloseTo(r);
    }
    let closest = Infinity;
    for (let i = 0; i < 18; i++)
      for (let j = i + 1; j < 18; j++)
        closest = Math.min(closest, Math.hypot(out.balloons[i].bx - out.balloons[j].bx, out.balloons[i].by - out.balloons[j].by));
    expect(closest).toBeGreaterThanOrEqual(2 * r); // no two circles overlap
  });

  it("handles no anchors and a single anchor", () => {
    expect(layoutBalloons([], { width: W, height: H, printedWidthMm: 155 }).balloons).toEqual([]);
    const one = layoutBalloons([anchor("A", 7, 1200, 750)], { width: W, height: H, printedWidthMm: 155 });
    expect(one.balloons).toHaveLength(1);
    expect(one.balloons[0].leader).not.toBeNull();
  });
});

describe("balloonSvg", () => {
  it("shares the image's viewBox and draws one numbered circle, dot and leader per balloon", () => {
    const out = layoutBalloons([anchor("A", 12, 600, 700), anchor("B", 3, 1500, 800)], { width: W, height: H, printedWidthMm: 155 });
    const svg = balloonSvg(out);
    expect(svg.startsWith("<svg ")).toBe(true);
    expect(svg).toContain(`viewBox="0 0 ${W} ${H}"`);
    expect(svg.match(/<text /g)).toHaveLength(2);
    expect(svg.match(/<circle /g)).toHaveLength(4); // 2 anchor dots + 2 balloons
    expect(svg.match(/<line /g)).toHaveLength(4); // each leader: white edge + ink
    expect(svg).toContain(">12</text>");
    expect(svg).toContain(">3</text>");
    expect(svg).not.toMatch(/NaN|undefined/);
  });

  it("is an empty overlay when there is nothing to label", () => {
    const svg = balloonSvg(layoutBalloons([], { width: W, height: H, printedWidthMm: 155 }));
    expect(svg).not.toContain("<circle");
    expect(svg.endsWith("</svg>")).toBe(true);
  });
});
