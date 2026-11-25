// Pure logic: from a capture's anchors to balloon positions and the SVG drawn over the picture.
// No DOM (the SVG is built as text). Tested in balloons.test.ts.
import { leaderStart, placeBalloons } from "../lib/layout";
import type { BalloonAnchor } from "../viewer/api";

/** Sizes on PAPER, in mm, at the width the picture is designed to be printed at. */
export const BALLOON_RADIUS_MM = 3;
export const BALLOON_REACH_MM = 9;
export const BALLOON_FONT_MM = 3.4;
export const BALLOON_STROKE_MM = 0.3;
export const BALLOON_DOT_MM = 0.6;

export interface BalloonMetrics {
  r: number;
  reach: number;
  font: number;
  stroke: number;
  dot: number;
}

export interface Balloon {
  key: string;
  label: number;
  /** The part's centre in the picture. */
  ax: number;
  ay: number;
  /** Balloon centre. */
  bx: number;
  by: number;
  /** Where the leader leaves the balloon's rim; null when the anchor lies under the balloon (no leader drawn). */
  leader: { x: number; y: number } | null;
}

export interface BalloonLayout {
  width: number;
  height: number;
  metrics: BalloonMetrics;
  balloons: Balloon[];
}

/** Balloon sizes in image pixels for an image `imageWidth` px wide that is printed `printedWidthMm` wide. */
export function balloonMetrics(imageWidth: number, printedWidthMm: number): BalloonMetrics {
  const perMm = imageWidth / printedWidthMm;
  return {
    r: BALLOON_RADIUS_MM * perMm,
    reach: BALLOON_REACH_MM * perMm,
    font: BALLOON_FONT_MM * perMm,
    stroke: BALLOON_STROKE_MM * perMm,
    dot: BALLOON_DOT_MM * perMm,
  };
}

export interface BalloonOptions {
  width: number; // image size, px
  height: number;
  printedWidthMm: number;
  /** Only these parts get a balloon; omit for all. */
  keys?: readonly string[];
}

/** Only anchors with visible === true, a label above 0 and a position inside the picture get a balloon. */
export function layoutBalloons(anchors: readonly BalloonAnchor[], opts: BalloonOptions): BalloonLayout {
  const metrics = balloonMetrics(opts.width, opts.printedWidthMm);
  const only = opts.keys ? new Set(opts.keys) : null;
  const used = anchors.filter(
    (a) =>
      a.visible === true &&
      a.label > 0 &&
      (!only || only.has(a.key)) &&
      Number.isFinite(a.x) &&
      Number.isFinite(a.y) &&
      a.x >= 0 &&
      a.y >= 0 &&
      a.x <= opts.width &&
      a.y <= opts.height,
  );
  const spots = placeBalloons(
    used.map((a) => ({ x: a.x, y: a.y })),
    metrics.r,
    metrics.reach,
    { width: opts.width, height: opts.height },
  );
  const balloons = used.map((a, i): Balloon => {
    const b = spots[i];
    const apart = Math.hypot(a.x - b.x, a.y - b.y);
    return {
      key: a.key,
      label: a.label,
      ax: a.x,
      ay: a.y,
      bx: b.x,
      by: b.y,
      leader: apart > metrics.r ? leaderStart(b, a, metrics.r) : null,
    };
  });
  return { width: opts.width, height: opts.height, metrics, balloons };
}

const INK = "#111111";
const PAPER = "#ffffff";
const n = (v: number): string => (Math.round(v * 10) / 10).toString();

/**
 * The overlay: same viewBox as the image, to be laid exactly over it. Leaders first (with a white edge so they
 * read across dark parts), then anchor dots, then the balloons on top. Labels are numbers, so no escaping is needed.
 */
export function balloonSvg(layout: BalloonLayout): string {
  const m = layout.metrics;
  const out: string[] = [];
  out.push(
    `<svg xmlns="http://www.w3.org/2000/svg" class="pr-balloons" viewBox="0 0 ${n(layout.width)} ${n(layout.height)}" preserveAspectRatio="xMidYMid meet" aria-hidden="true">`,
  );
  for (const b of layout.balloons) {
    if (!b.leader) continue;
    const line = `x1="${n(b.leader.x)}" y1="${n(b.leader.y)}" x2="${n(b.ax)}" y2="${n(b.ay)}" stroke-linecap="round"`;
    out.push(`<line ${line} stroke="${PAPER}" stroke-width="${n(m.stroke * 3)}"/>`);
    out.push(`<line ${line} stroke="${INK}" stroke-width="${n(m.stroke)}"/>`);
  }
  for (const b of layout.balloons) {
    out.push(`<circle cx="${n(b.ax)}" cy="${n(b.ay)}" r="${n(m.dot)}" fill="${INK}" stroke="${PAPER}" stroke-width="${n(m.stroke)}"/>`);
  }
  for (const b of layout.balloons) {
    out.push(`<circle cx="${n(b.bx)}" cy="${n(b.by)}" r="${n(m.r)}" fill="${PAPER}" stroke="${INK}" stroke-width="${n(m.stroke * 1.4)}"/>`);
    out.push(
      `<text x="${n(b.bx)}" y="${n(b.by)}" dy="0.35em" text-anchor="middle" font-family="Arial, Helvetica, sans-serif" font-weight="700" font-size="${n(m.font)}" fill="${INK}">${Math.trunc(b.label)}</text>`,
    );
  }
  out.push("</svg>");
  return out.join("");
}
