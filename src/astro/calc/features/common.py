"""Helpers shared by features."""

from __future__ import annotations

from astro.calc.context import ChartContext
from astro.calc.core.angles import NAKSHATRA_SPAN, PADA_SPAN, SIGN_SPAN
from astro.calc.ephemeris.port import BODIES, Body
from astro.calc.model import ChartFact
from astro.calc.sensitivity import UNKNOWN, Assessment, assess, assess_many, assess_targets
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


def assess_boundaries(ctx: ChartContext, body: str, targets: list[float]) -> Assessment:
    """Sensitivity of a fact of `body` that changes at the given absolute longitudes."""
    b = ctx.birth
    if body == LAGNA:
        if not b.time_known:
            return UNKNOWN
        return assess_targets(ctx.lagna_fn(), b.jd_ut, b.u_days, targets=targets,
                              step=ctx.step_days(LAGNA))
    speed = ctx.speed_fn(body) if ctx.needs_speed(body) else None  # type: ignore[arg-type]
    return assess_targets(ctx.lon_fn(body), b.jd_ut, b.u_days,  # type: ignore[arg-type]
                          targets=targets, step=ctx.step_days(body), speed=speed)


ZODIAC_MULTIPLES = {"pada": 1, "nakshatra": 4, "sign": 9}  # in pada spans


def assess_zodiac(ctx: ChartContext, body: str) -> dict[str, Assessment]:
    """Sign, nakshatra and pada sensitivity of `body` from a single crossing search."""
    b = ctx.birth
    if body == LAGNA:
        if not b.time_known:
            return {k: UNKNOWN for k in ZODIAC_MULTIPLES}
        return assess_many(ctx.lagna_fn(), b.jd_ut, b.u_days, base_width=PADA_SPAN,
                           multiples=ZODIAC_MULTIPLES, step=ctx.step_days(LAGNA))
    speed = ctx.speed_fn(body) if ctx.needs_speed(body) else None  # type: ignore[arg-type]
    return assess_many(ctx.lon_fn(body), b.jd_ut, b.u_days,  # type: ignore[arg-type]
                       base_width=PADA_SPAN, multiples=ZODIAC_MULTIPLES,
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


def is_retrograde(ctx: ChartContext, body: str, speed: float) -> bool:
    """Retrograde status under the profile: nodes may be retrograde by definition."""
    if body in ("rahu", "ketu") and ctx.profile.nodes.retrograde == "always":
        return True
    return speed < 0


def assessment_of(f: ChartFact) -> Assessment:
    return Assessment(f.sensitivity, f.margin_minutes)
