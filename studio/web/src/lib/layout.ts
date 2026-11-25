// Balloon placement. FOUNDATION FILE (main session). A port of mechkit/present/layout.py: keep the two in step.

export interface Point {
  x: number;
  y: number;
}

/**
 * Balloon centres for anchor points: set to the side of the line the parts spread along, then nudged apart.
 *
 * An exploded stack runs roughly along one line in the picture; balloons go square to that line, on the side their
 * part already leans to, so leaders stay short and do not run along the stack.
 * r: balloon radius; reach: leader length. Any unit, either y direction. bounds (optional) keeps them inside a box.
 */
export function placeBalloons(points: Point[], r: number, reach: number, bounds?: { width: number; height: number }): Point[] {
  if (points.length === 0) return [];
  const cx = points.reduce((s, p) => s + p.x, 0) / points.length;
  const cy = points.reduce((s, p) => s + p.y, 0) / points.length;
  let sxx = 0;
  let syy = 0;
  let sxy = 0;
  for (const p of points) {
    sxx += (p.x - cx) ** 2;
    syy += (p.y - cy) ** 2;
    sxy += (p.x - cx) * (p.y - cy);
  }
  const ang = 0.5 * Math.atan2(2 * sxy, sxx - syy); // direction of largest spread
  const px = -Math.sin(ang); // square to it
  const py = Math.cos(ang);
  const spots = points.map((p, i) => {
    const side = (p.x - cx) * px + (p.y - cy) * py;
    const sign = Math.abs(side) > 0.08 * reach ? (side > 0 ? 1 : -1) : i % 2 ? 1 : -1;
    return { x: p.x + sign * px * reach, y: p.y + sign * py * reach };
  });
  const gap = 2.4 * r;
  for (let pass = 0; pass < 300; pass++) {
    let moved = false;
    for (let i = 0; i < spots.length; i++) {
      for (let j = i + 1; j < spots.length; j++) {
        let dx = spots[j].x - spots[i].x;
        let dy = spots[j].y - spots[i].y;
        let dist = Math.hypot(dx, dy);
        if (dist < gap) {
          if (dist < 1e-9) {
            dx = 1;
            dy = 0;
            dist = 1;
          }
          const push = (gap - dist) / 2 + 0.02 * r;
          spots[i].x -= (dx / dist) * push;
          spots[i].y -= (dy / dist) * push;
          spots[j].x += (dx / dist) * push;
          spots[j].y += (dy / dist) * push;
          moved = true;
        }
      }
    }
    if (!moved) break;
  }
  if (bounds) {
    for (const s of spots) {
      s.x = Math.min(Math.max(s.x, r + 4), bounds.width - r - 4);
      s.y = Math.min(Math.max(s.y, r + 4), bounds.height - r - 4);
    }
  }
  return spots;
}

/** The point on a balloon's rim where its leader line starts, heading for the anchor. */
export function leaderStart(balloon: Point, anchor: Point, r: number): Point {
  const dx = anchor.x - balloon.x;
  const dy = anchor.y - balloon.y;
  const n = Math.hypot(dx, dy) || 1;
  return { x: balloon.x + (dx / n) * r, y: balloon.y + (dy / n) * r };
}
