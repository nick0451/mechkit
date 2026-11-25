"""Shared layout maths for labelled views: a camera's picture plane and where to put the balloons."""

import math


def _norm(v):
    n = math.sqrt(sum(c * c for c in v)) or 1.0
    return [c / n for c in v]


def _cross(a, b):
    return [a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0]]


def _dot(a, b):
    return sum(x * y for x, y in zip(a, b))


def camera_basis(eye, target, up):
    """(right, up, toward_camera) unit vectors of a view."""
    f = _norm([t - e for e, t in zip(eye, target)])
    r = _norm(_cross(f, up))
    u = _cross(r, f)
    return r, u, [-c for c in f]


def project(point, origin, right, up):
    """A 3D point's (x, y) on the picture plane through `origin` (y up)."""
    d = [p - o for p, o in zip(point, origin)]
    return _dot(d, right), _dot(d, up)


def place_balloons(points, r, reach):
    """Balloon centres for anchor points [(x, y)]: set to the side of the line the parts spread along, then nudged apart.

    An exploded stack runs roughly along one line in the picture; balloons go square to that line, on the side their
    part already leans to, so leaders stay short and do not run along the stack. r: balloon radius; reach: leader
    length. Works in any unit and either y direction.
    """
    if not points:
        return []
    cx = sum(p[0] for p in points) / len(points)
    cy = sum(p[1] for p in points) / len(points)
    sxx = sum((p[0] - cx) ** 2 for p in points)
    syy = sum((p[1] - cy) ** 2 for p in points)
    sxy = sum((p[0] - cx) * (p[1] - cy) for p in points)
    ang = 0.5 * math.atan2(2 * sxy, sxx - syy)                  # direction of largest spread
    px, py = -math.sin(ang), math.cos(ang)                      # square to it
    spots = []
    for i, (x, y) in enumerate(points):
        side = (x - cx) * px + (y - cy) * py
        sign = (1.0 if side > 0 else -1.0) if abs(side) > 0.08 * reach else (1.0 if i % 2 else -1.0)
        spots.append([x + sign * px * reach, y + sign * py * reach])
    gap = 2.4 * r
    for _ in range(300):
        moved = False
        for i in range(len(spots)):
            for j in range(i + 1, len(spots)):
                dx, dy = spots[j][0] - spots[i][0], spots[j][1] - spots[i][1]
                dist = math.hypot(dx, dy)
                if dist < gap:
                    if dist < 1e-9:
                        dx, dy, dist = 1.0, 0.0, 1.0
                    push = (gap - dist) / 2 + 0.02 * r
                    spots[i][0] -= dx / dist * push
                    spots[i][1] -= dy / dist * push
                    spots[j][0] += dx / dist * push
                    spots[j][1] += dy / dist * push
                    moved = True
        if not moved:
            break
    return [(x, y) for x, y in spots]
