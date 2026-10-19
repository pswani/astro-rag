"""Helpers shared by features."""

from __future__ import annotations

from collections.abc import Callable, Hashable, Iterable

from astro.calc.context import ChartContext
from astro.calc.core.angles import NAKSHATRA_SPAN, PADA_SPAN, SIGN_SPAN, norm360, sign_index
from astro.calc.core.timescale import MINUTE
from astro.calc.ephemeris.port import BODIES, Body
from astro.calc.model import ChartFact
from astro.calc.sensitivity import STABLE, UNKNOWN, Assessment, assess, assess_many
from astro.calc.solver import crossings, find_stations

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
        return assess(ctx.lagna_fn(), b.jd_ut, b.u_days, targets=targets,
                      step=ctx.step_days(LAGNA))
    speed = ctx.speed_fn(body) if ctx.needs_speed(body) else None  # type: ignore[arg-type]
    return assess(ctx.lon_fn(body), b.jd_ut, b.u_days,  # type: ignore[arg-type]
                  targets=targets, step=ctx.step_days(body), speed=speed)


def assess_angle(ctx: ChartContext, a: str, b: str, targets: list[float]) -> Assessment:
    """Sensitivity of a fact that changes when the angle a − b (degrees, [0, 360)) crosses any
    of `targets`: combustion, graha yuddha and orb conjunctions."""
    la, lb = ctx.lon_fn(a), ctx.lon_fn(b)  # type: ignore[arg-type]
    va, vb = ctx.speed_fn(a), ctx.speed_fn(b)  # type: ignore[arg-type]
    step = min(ctx.step_days(a), ctx.step_days(b))
    return assess(lambda t: norm360(la(t) - lb(t)), ctx.birth.jd_ut, ctx.birth.u_days,
                  targets=targets, step=step, speed=lambda t: va(t) - vb(t))


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


# -- exact sensitivity of derived facts ------------------------------------------------------
#
# A fact derived from signs, angles or latitudes is piecewise constant in time: it can only
# change at an instant where one of its inputs changes. The instants are solved exactly, the
# fact is evaluated once inside every piece of [t − u, t + u], and it is sensitive if any piece
# disagrees with the value at t; the margins are the nearest instants where it actually changes.

def sign_changes(ctx: ChartContext, body: str) -> tuple[float, ...]:
    """Instants inside [t − u, t + u] where `body` (or the Lagna) changes sign."""
    key = ("sign_changes", body)
    if key not in ctx.memo:
        b = ctx.birth
        if b.u_days <= 0:
            ctx.memo[key] = ()
        else:
            speed = None if body == LAGNA or not ctx.needs_speed(body) else ctx.speed_fn(body)
            step = min(ctx.step_days(body), b.u_days)
            cs = crossings(lon_fn(ctx, body), b.jd_ut - b.u_days, b.jd_ut + b.u_days,
                           step=step, speed=speed, width=SIGN_SPAN)
            ctx.memo[key] = tuple(c.jd for c in cs)
    return ctx.memo[key]


def sign_at(ctx: ChartContext, body: str, t: float) -> int:
    return sign_index(lon_fn(ctx, body)(t))


def piecewise(ctx: ChartContext, change_times: Iterable[float],
              value_at: Callable[[float], Hashable]) -> Assessment:
    b = ctx.birth
    if b.u_days <= 0:
        return STABLE
    t, lo, hi = b.jd_ut, b.jd_ut - b.u_days, b.jd_ut + b.u_days
    # the interval is closed: a change exactly at t + u still happens inside it
    cuts = sorted({c for c in change_times if lo < c <= hi and c != t})
    if not cuts:
        return STABLE
    now = value_at(t)
    edges = [lo, *(c for c in cuts if c < hi), hi]
    pieces = [(a, z, value_at((a + z) / 2)) for a, z in zip(edges, edges[1:], strict=False)]
    if cuts[-1] == hi:  # a zero-length piece at the end: the value from that instant on
        pieces.append((hi, hi, value_at(hi)))
    before = [z for a, z, v in pieces if z <= t and v != now]
    after = [a for a, z, v in pieces if a >= t and v != now]
    if not before and not after:
        return STABLE
    return Assessment("sensitive", ((t - max(before)) / MINUTE if before else None,
                                    (min(after) - t) / MINUTE if after else None))


def sign_piecewise(ctx: ChartContext, bodies: Iterable[str],
                   value_at: Callable[[float], Hashable]) -> Assessment:
    """`piecewise` for a fact that depends only on the signs of `bodies`."""
    bodies = list(bodies)
    if LAGNA in bodies and not ctx.birth.time_known:
        return UNKNOWN
    return piecewise(ctx, (c for x in bodies for c in sign_changes(ctx, x)), value_at)


def angle_changes(ctx: ChartContext, a: str, b: str,
                  targets: tuple[float, ...]) -> tuple[float, ...]:
    """Instants inside [t − u, t + u] where the angle a − b crosses any of `targets`."""
    key = ("angle_changes", a, b, targets)
    if key not in ctx.memo:
        bt = ctx.birth
        if bt.u_days <= 0:
            ctx.memo[key] = ()
        else:
            la, lb = ctx.lon_fn(a), ctx.lon_fn(b)  # type: ignore[arg-type]
            va, vb = ctx.speed_fn(a), ctx.speed_fn(b)  # type: ignore[arg-type]
            step = min(ctx.step_days(a), ctx.step_days(b), bt.u_days)
            cs = crossings(lambda t: norm360(la(t) - lb(t)), bt.jd_ut - bt.u_days,
                           bt.jd_ut + bt.u_days, step=step, speed=lambda t: va(t) - vb(t),
                           targets=targets)
            ctx.memo[key] = tuple(c.jd for c in cs)
    return ctx.memo[key]


def target_changes(ctx: ChartContext, body: str,
                   targets: tuple[float, ...]) -> tuple[float, ...]:
    """Instants inside [t − u, t + u] where `body` crosses any of `targets` (degrees)."""
    key = ("target_changes", body, targets)
    if key not in ctx.memo:
        b = ctx.birth
        if b.u_days <= 0 or not targets or (body == LAGNA and not b.time_known):
            ctx.memo[key] = ()
        else:
            speed = None if body == LAGNA or not ctx.needs_speed(body) else ctx.speed_fn(body)
            cs = crossings(lon_fn(ctx, body), b.jd_ut - b.u_days, b.jd_ut + b.u_days,
                           step=min(ctx.step_days(body), b.u_days), speed=speed,
                           targets=targets)
            ctx.memo[key] = tuple(c.jd for c in cs)
    return ctx.memo[key]


def station_times(ctx: ChartContext, body: str) -> tuple[float, ...]:
    key = ("stations", body)
    if key not in ctx.memo:
        b = ctx.birth
        ctx.memo[key] = () if b.u_days <= 0 or not ctx.needs_speed(body) else tuple(
            find_stations(ctx.speed_fn(body), b.jd_ut - b.u_days,  # type: ignore[arg-type]
                          b.jd_ut + b.u_days, min(ctx.step_days(body), b.u_days)))
    return ctx.memo[key]


def latitude_crossings(ctx: ChartContext, a: str, b: str) -> tuple[float, ...]:
    """Instants inside [t − u, t + u] where the ecliptic latitudes of a and b are equal."""
    key = ("latitude_crossings", a, b)
    if key not in ctx.memo:
        bt = ctx.birth
        if bt.u_days <= 0:
            ctx.memo[key] = ()
        else:
            lat = lambda x, t: ctx.ephemeris.body(x, t, ctx.profile).latitude  # noqa: E731
            ctx.memo[key] = tuple(find_stations(
                lambda t: lat(a, t) - lat(b, t), bt.jd_ut - bt.u_days, bt.jd_ut + bt.u_days,
                min(ctx.step_days(a), ctx.step_days(b), bt.u_days)))
    return ctx.memo[key]
