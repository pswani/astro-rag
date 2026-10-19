"""One root-finding engine for panchanga boundaries, transit events and birth-time sensitivity
(design §7.8, design-notes §4).

Functions take plain callables of JD (UT), so the solver has no ephemeris dependency.

1. Stations are found by bracketing sign changes of the speed on a grid, then Brent's method.
2. Sample points are the grid, the stations and the ends. Between two consecutive sample points
   the motion is monotone and moves less than 180°, so values unwrap unambiguously.
3. Each boundary strictly passed between two sample points is crossed exactly once there, and
   Brent's method finds the instant. All crossings of a retrograde loop are therefore returned.

Boundary convention: a longitude exactly on a boundary belongs to the later sector, matching
`angles.sign_index` and friends. Moving forward, a crossing happens when the value reaches the
boundary; moving backward, when it drops below it.
"""

from __future__ import annotations

import math
from collections.abc import Callable, Sequence
from dataclasses import dataclass

from scipy.optimize import brentq

from astro.calc.core.angles import norm360, signed_diff, unwrap
from astro.calc.core.timescale import SECOND

Fn = Callable[[float], float]
XTOL = SECOND / 10


@dataclass(frozen=True)
class Crossing:
    jd: float
    boundary: float     # degrees in [0, 360)
    direction: int      # +1 forward (direct), −1 backward (retrograde)
    index: int          # sector entered (width mode) or target index (targets mode)


@dataclass(frozen=True)
class Contact:
    jd: float           # the station closest to the target
    target_index: int
    distance: float     # |angle| to the target at the station, degrees


def grid(t0: float, t1: float, step: float) -> list[float]:
    if not t0 < t1:
        raise ValueError("empty search interval")
    n = max(1, math.ceil((t1 - t0) / step))
    return [t0 + (t1 - t0) * i / n for i in range(n + 1)]


def find_stations(speed: Fn, t0: float, t1: float, step: float) -> list[float]:
    """Instants in (t0, t1) where the speed changes sign."""
    ts = grid(t0, t1, step)
    vs = [speed(t) for t in ts]
    out = []
    for a, b, va, vb in zip(ts, ts[1:], vs, vs[1:], strict=False):
        if va == 0.0 and a > t0:
            out.append(a)
        elif va * vb < 0:
            out.append(brentq(speed, a, b, xtol=XTOL))
    return out


def _sample(lon: Fn, t0: float, t1: float, step: float,
            stations: Sequence[float]) -> tuple[list[float], list[float]]:
    pts = sorted({*grid(t0, t1, step), *(s for s in stations if t0 < s < t1)})
    return pts, unwrap([lon(t) for t in pts])


def _local_unwrapped(lon: Fn, ref_t_value: float, ref_wrapped: float) -> Fn:
    return lambda t: ref_t_value + signed_diff(lon(t), ref_wrapped)


def crossings(lon: Fn, t0: float, t1: float, *, step: float, speed: Fn | None = None,
              width: float | None = None, offset: float = 0.0,
              targets: Sequence[float] = ()) -> list[Crossing]:
    """All crossings in (t0, t1] of the boundaries `offset + k·width` and/or `targets`."""
    stations = find_stations(speed, t0, t1, step) if speed else []
    pts, vals = _sample(lon, t0, t1, step, stations)
    count = round(360.0 / width) if width else 0
    out: list[Crossing] = []
    for a, b, ua, ub in zip(pts, pts[1:], vals, vals[1:], strict=False):
        if ua == ub:
            continue
        direction = 1 if ub > ua else -1
        lo, hi = (ua, ub) if direction > 0 else (ub, ua)
        candidates: list[tuple[float, int]] = []
        if width:
            for k in range(math.floor((lo - offset) / width) - 1,
                           math.floor((hi - offset) / width) + 2):
                b_val = offset + k * width
                candidates.append((b_val, k))
        for i, tgt in enumerate(targets):
            base = tgt + 360.0 * math.floor((lo - tgt) / 360.0)
            for j in range(-1, 3):
                candidates.append((base + 360.0 * j, -(i + 1)))
        f_local = _local_unwrapped(lon, ua, lon(a))
        for b_val, tag in candidates:
            hit = (ua < b_val <= ub) if direction > 0 else (ub < b_val <= ua)
            if not hit:
                continue
            if b_val == ub and direction > 0:
                jd = b
            elif b_val == ua and direction < 0:
                jd = a
            else:
                jd = brentq(lambda t, bv=b_val, f=f_local: f(t) - bv, a, b, xtol=XTOL)
            if tag >= 0:
                sector = tag if direction > 0 else tag - 1
                out.append(Crossing(jd, norm360(b_val), direction, sector % count))
            else:
                out.append(Crossing(jd, norm360(b_val), direction, -tag - 1))
    out.sort(key=lambda c: (c.jd, c.index))
    return out


def contacts(lon: Fn, t0: float, t1: float, stations: Sequence[float],
             targets: Sequence[float], tol_deg: float,
             found: Sequence[Crossing] = ()) -> list[Contact]:
    """Stations within `tol_deg` of a target that is not crossed in either monotone piece next to
    the station: the body turns back short of the target (design §7.8)."""
    edges = [t0, *sorted(stations), t1]
    out = []
    for i in range(1, len(edges) - 1):
        s, before, after = edges[i], edges[i - 1], edges[i + 1]
        v = lon(s)
        for j, tgt in enumerate(targets):
            d = abs(signed_diff(v, tgt))
            crossed = any(c.index == j and before <= c.jd <= after for c in found)
            if d <= tol_deg and not crossed:
                out.append(Contact(s, j, d))
    return out


def last_crossing_before(lon: Fn, t: float, *, width: float, step: float, span: float,
                         offset: float = 0.0) -> Crossing | None:
    """The latest boundary crossing at or before t, searching back `span` days."""
    cs = crossings(lon, t - span, t, step=step, width=width, offset=offset)
    return cs[-1] if cs else None


def first_crossing_after(lon: Fn, t: float, *, width: float, step: float, span: float,
                         offset: float = 0.0) -> Crossing | None:
    """The first boundary crossing strictly after t, searching forward `span` days."""
    cs = [c for c in crossings(lon, t, t + span, step=step, width=width, offset=offset)
          if c.jd > t]
    return cs[0] if cs else None
