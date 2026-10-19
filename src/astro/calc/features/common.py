"""Helpers shared by features."""

from __future__ import annotations

from astro.calc.context import ChartContext
from astro.calc.core.angles import NAKSHATRA_SPAN, PADA_SPAN, SIGN_SPAN
from astro.calc.ephemeris.port import BODIES, Body
from astro.calc.model import ChartFact
from astro.calc.sensitivity import UNKNOWN, Assessment, assess
from astro.calc.solver import find_stations

LAGNA = "lagna"
WIDTHS = {"sign": SIGN_SPAN, "nakshatra": NAKSHATRA_SPAN, "pada": PADA_SPAN}


def subject(body: str) -> str:
    return LAGNA if body == LAGNA else f"graha:{body}"


def points(ctx: ChartContext) -> list[str]:
    """Bodies plus the Lagna when the time is known."""
    return [*BODIES, LAGNA]


def lon_fn(ctx: ChartContext, body: str):
    return ctx.lagna_fn() if body == LAGNA else ctx.lon_fn(body)  # type: ignore[arg-type]


def assess_width(ctx: ChartContext, body: str, width: float) -> Assessment:
    """Sensitivity of a discrete fact of `body` with boundaries every `width` degrees."""
    b = ctx.birth
    if body == LAGNA:
        if not b.time_known:
            return UNKNOWN
        return assess(ctx.lagna_fn(), b.jd_ut, b.u_days, width=width, step=ctx.step_days(LAGNA))
    speed = ctx.speed_fn(body) if ctx.needs_speed(body) else None  # type: ignore[arg-type]
    return assess(ctx.lon_fn(body), b.jd_ut, b.u_days, width=width,  # type: ignore[arg-type]
                  step=ctx.step_days(body), speed=speed)


def assess_station(ctx: ChartContext, body: Body) -> Assessment:
    """Retrograde status changes only at a station inside [t − u, t + u]."""
    b = ctx.birth
    if not ctx.needs_speed(body) or b.u_days <= 0:
        return Assessment("stable", (None, None))
    st = find_stations(ctx.speed_fn(body), b.jd_ut - b.u_days, b.jd_ut + b.u_days,
                       min(ctx.step_days(body), b.u_days))
    if not st:
        return Assessment("stable", (None, None))
    before = [(b.jd_ut - s) * 1440 for s in st if s <= b.jd_ut]
    after = [(s - b.jd_ut) * 1440 for s in st if s > b.jd_ut]
    return Assessment("sensitive", (min(before) if before else None,
                                    min(after) if after else None))


def assessment_of(f: ChartFact) -> Assessment:
    return Assessment(f.sensitivity, f.margin_minutes)
