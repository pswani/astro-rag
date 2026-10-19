"""Birth-time sensitivity (CALC-7, design §7.9, design-notes §5).

A discrete fact derived from a longitude changes when the longitude crosses a boundary of width
`w`. The solver finds every crossing inside [t − u, t + u], so a cross-and-recross near a station
is not labelled stable.
"""

from __future__ import annotations

from dataclasses import dataclass

from astro.calc.core.timescale import MINUTE
from astro.calc.model import Sensitivity
from astro.calc.solver import Fn, crossings

Margins = tuple[float | None, float | None]


@dataclass(frozen=True)
class Assessment:
    sensitivity: Sensitivity
    margins: Margins  # minutes to the nearest change before and after t, inside the interval

    @staticmethod
    def combine(*items: Assessment) -> Assessment:
        if any(i.sensitivity == "unknown" for i in items):
            return Assessment("unknown", (None, None))
        sens: Sensitivity = "sensitive" if any(i.sensitivity == "sensitive" for i in items) \
            else "stable"
        before = [i.margins[0] for i in items if i.margins[0] is not None]
        after = [i.margins[1] for i in items if i.margins[1] is not None]
        return Assessment(sens, (min(before) if before else None, min(after) if after else None))


STABLE = Assessment("stable", (None, None))
UNKNOWN = Assessment("unknown", (None, None))


def assess(lon: Fn, t: float, u_days: float, *, width: float, step: float,
           speed: Fn | None = None, offset: float = 0.0) -> Assessment:
    if u_days <= 0:
        return STABLE
    cs = crossings(lon, t - u_days, t + u_days, step=min(step, u_days), speed=speed, width=width,
                   offset=offset)
    if not cs:
        return STABLE
    before = [(t - c.jd) / MINUTE for c in cs if c.jd <= t]
    after = [(c.jd - t) / MINUTE for c in cs if c.jd > t]
    return Assessment("sensitive", (min(before) if before else None,
                                    min(after) if after else None))
