"""Helpers shared by features: subjects, memoized ephemeris states, change instants and
birth-time sensitivity (CALC-7).

Every discrete fact is piecewise constant in time; it can only change at an instant where one of
its inputs changes (a sign, pada or cusp crossing, an angle reaching an orb, a station, a latitude
crossing). Those instants are solved exactly once per chart and memoized on the context, so the
positions, houses, condition and aspects features share one set of solves:

Every assessment goes through `piecewise`: the solved instants only propose cut points, and the
fact's own value function is evaluated inside every piece and at both ends of the closed
interval. Sensitivity is therefore decided by values, never by a crossing's direction or the
root finder's tolerance; the instants only make the margins exact.
"""

from __future__ import annotations

from collections import OrderedDict
from collections.abc import Callable, Hashable, Iterable

from astro.calc.context import ChartContext
from astro.calc.core.angles import (
    PADA_SPAN,
    nakshatra_index,
    norm360,
    pada_count,
    sign_index,
)
from astro.calc.core.timescale import MINUTE
from astro.calc.ephemeris.port import BODIES, Body, BodyState
from astro.calc.model import ChartFact
from astro.calc.sensitivity import STABLE, UNKNOWN, Assessment
from astro.calc.solver import Crossing, crossings, find_stations

LAGNA = "lagna"
_PADAS = round(360.0 / PADA_SPAN)
# kind → (boundaries in pada spans, index of a longitude)
ZODIAC_VALUES = {"pada": (1, pada_count), "nakshatra": (4, nakshatra_index),
                 "sign": (9, sign_index)}


def subject(body: str) -> str:
    return LAGNA if body == LAGNA else f"graha:{body}"


def points(ctx: ChartContext) -> list[str]:
    """Bodies plus the Lagna (facts of the Lagna are `unknown` without a birth time)."""
    return [*BODIES, LAGNA]


def is_retrograde(ctx: ChartContext, body: str, speed: float) -> bool:
    """Retrograde status under the profile: nodes may be retrograde by definition."""
    if body in ("rahu", "ketu") and ctx.profile.nodes.retrograde == "always":
        return True
    return speed < 0


def assessment_of(f: ChartFact) -> Assessment:
    return Assessment(f.sensitivity, f.margin_minutes)


# -- memoized states at an instant ------------------------------------------------------------

def _memo(ctx: ChartContext, key: tuple, compute: Callable[[], object]):
    if key not in ctx.memo:
        ctx.memo[key] = compute()
    return ctx.memo[key]


_STATES_MAX = 50_000  # least recently used states go first; hot instants stay


def _state(ctx: ChartContext, key: tuple, compute: Callable[[], object]):
    states = ctx.memo.get("states")
    if states is None:
        states = ctx.memo["states"] = OrderedDict()
    if key in states:
        states.move_to_end(key)
        return states[key]
    value = states[key] = compute()
    if len(states) > _STATES_MAX:
        states.popitem(last=False)
    return value


def state_at(ctx: ChartContext, body: str, t: float) -> BodyState:
    return _state(ctx, ("state", body, t),
                  lambda: ctx.ephemeris.body(body, t, ctx.profile))  # type: ignore[arg-type]


def lon_at(ctx: ChartContext, body: str, t: float) -> float:
    if body == LAGNA:
        b = ctx.birth
        return _state(ctx, ("lagna", t), lambda: ctx.ephemeris.ascendant(
            t, b.latitude, b.longitude, ctx.profile))
    return state_at(ctx, body, t).longitude


def sign_at(ctx: ChartContext, body: str, t: float) -> int:
    return sign_index(lon_at(ctx, body, t))


def cusps_at(ctx: ChartContext, t: float) -> tuple[float, ...]:
    b = ctx.birth
    return _state(ctx, ("cusps", t),
                  lambda: ctx.ephemeris.cusps(t, b.latitude, b.longitude, ctx.profile))


def cusp_house(lon: float, cusps: tuple[float, ...]) -> int:
    """House i spans [cusp_i, cusp_i+1) (Sripati, Placidus)."""
    for i in range(12):
        a, z = cusps[i], cusps[(i + 1) % 12]
        if norm360(lon - a) < norm360(z - a):
            return i + 1
    raise AssertionError("cusps do not cover the circle")  # pragma: no cover


def cusp_house_at(ctx: ChartContext, body: str, t: float) -> int:
    return cusp_house(lon_at(ctx, body, t), cusps_at(ctx, t))


# -- change instants inside [t − u, t + u], solved once per chart ------------------------------

def _window(ctx: ChartContext) -> tuple[float, float] | None:
    """The closed interval [t − u, t + u]; None when the time is exact."""
    b = ctx.birth
    return None if b.u_days <= 0 else (b.jd_ut - b.u_days, b.jd_ut + b.u_days)



def _motion(ctx: ChartContext, body: str) -> tuple[Callable, dict]:
    """The longitude of a body or the Lagna, and the solver arguments: the sampling step and
    the memoized stations (none for monotone motion)."""
    step = min(ctx.step_days(body), ctx.birth.u_days)
    lon = lambda t: lon_at(ctx, body, t)  # noqa: E731
    if body == LAGNA or not ctx.needs_speed(body):
        return lon, {"step": step, "stations": ()}
    return lon, {"step": step, "stations": station_times(ctx, body)}


def zodiac_crossings(ctx: ChartContext, body: str) -> tuple[Crossing, ...]:
    """Every pada boundary crossing of `body`; sign and nakshatra boundaries are among them."""
    def compute():
        w = _window(ctx)
        if w is None or (body == LAGNA and not ctx.birth.time_known):
            return ()
        lon, kw = _motion(ctx, body)
        return tuple(crossings(lon, *w, width=PADA_SPAN, **kw))
    return _memo(ctx, ("zodiac", body), compute)


def _zodiac_times(ctx: ChartContext, body: str, multiple: int) -> tuple[float, ...]:
    return tuple(c.jd for c in zodiac_crossings(ctx, body)
                 if round(c.boundary / PADA_SPAN) % _PADAS % multiple == 0)


def sign_changes(ctx: ChartContext, body: str) -> tuple[float, ...]:
    return _zodiac_times(ctx, body, ZODIAC_VALUES["sign"][0])


def width_changes(ctx: ChartContext, body: str, width: float) -> tuple[float, ...]:
    """Crossings of every multiple of `width` degrees (equal-part varga boundaries)."""
    def compute():
        w = _window(ctx)
        if w is None or (body == LAGNA and not ctx.birth.time_known):
            return ()
        lon, kw = _motion(ctx, body)
        return tuple(c.jd for c in crossings(lon, *w, width=width, **kw))
    return _memo(ctx, ("width", body, width), compute)


def target_changes(ctx: ChartContext, body: str,
                   targets: Iterable[float]) -> tuple[float, ...]:
    """Crossings of any of `targets` (absolute longitudes)."""
    # exact (unrounded) targets, so the cuts sit where the facts' rules really change
    targets = tuple(sorted({norm360(x) for x in targets}))

    def compute():
        w = _window(ctx)
        if w is None or not targets or (body == LAGNA and not ctx.birth.time_known):
            return ()
        lon, kw = _motion(ctx, body)
        return tuple(c.jd for c in crossings(lon, *w, targets=targets, **kw))
    return _memo(ctx, ("targets", body, targets), compute)


def angle_changes(ctx: ChartContext, a: str, b: str,
                  targets: Iterable[float]) -> tuple[float, ...]:
    """Instants where the angle a − b crosses any of `targets`. The angle b − a crosses
    360° − x at the same instants, so the pair is put in a canonical order and solved once."""
    if b < a:
        a, b, targets = b, a, [norm360(-x) for x in targets]
    # 1e-9° canonical rounding (CALC-9) so 360 − (360 − x) keys the same memo entry as x
    targets = tuple(sorted(round(norm360(x), 9) % 360.0 for x in targets))

    def compute():
        w = _window(ctx)
        if w is None:
            return ()
        step = min(ctx.step_days(a), ctx.step_days(b), ctx.birth.u_days)
        diff = lambda t: norm360(lon_at(ctx, a, t) - lon_at(ctx, b, t))  # noqa: E731
        speed = lambda t: state_at(ctx, a, t).speed - state_at(ctx, b, t).speed  # noqa: E731
        return tuple(c.jd for c in crossings(diff, *w, step=step, speed=speed,
                                             targets=targets))
    return _memo(ctx, ("angle", a, b, targets), compute)


def station_times(ctx: ChartContext, body: str) -> tuple[float, ...]:
    def compute():
        w = _window(ctx)
        if w is None or not ctx.needs_speed(body):
            return ()
        speed = lambda t: state_at(ctx, body, t).speed  # noqa: E731
        return tuple(find_stations(speed, *w, min(ctx.step_days(body), ctx.birth.u_days)))
    return _memo(ctx, ("stations", body), compute)


def latitude_crossings(ctx: ChartContext, a: str, b: str) -> tuple[float, ...]:
    """Instants where the ecliptic latitudes of a and b are equal."""
    a, b = sorted((a, b))

    def compute():
        w = _window(ctx)
        if w is None:
            return ()
        diff = lambda t: state_at(ctx, a, t).latitude - state_at(ctx, b, t).latitude  # noqa
        return tuple(find_stations(diff, *w, min(ctx.step_days(a), ctx.step_days(b),
                                                 ctx.birth.u_days)))
    return _memo(ctx, ("latitude", a, b), compute)


def cusp_changes(ctx: ChartContext, body: str) -> tuple[float, ...]:
    """Instants where `body` crosses a house cusp (Sripati, Placidus). Cusps move with the
    Lagna, so the search samples on the Lagna step."""
    def compute():
        w = _window(ctx)
        if w is None or not ctx.birth.time_known:
            return ()
        step = min(ctx.step_days(LAGNA), ctx.birth.u_days)
        out: set[float] = set()
        for i in range(12):
            gap = lambda t, i=i: norm360(lon_at(ctx, body, t) - cusps_at(ctx, t)[i])  # noqa
            out.update(c.jd for c in crossings(gap, *w, step=step, targets=(0.0,)))
        return tuple(sorted(out))
    return _memo(ctx, ("cusp", body), compute)


# -- assessments ---------------------------------------------------------------------------
#
# Each assessment evaluates the fact's own rule (a function of longitude, angle or state); the
# solved instants only propose where it may change.

def _unknown_lagna(ctx: ChartContext, body: str) -> bool:
    return body == LAGNA and not ctx.birth.time_known



def assess_zodiac(ctx: ChartContext, body: str) -> dict[str, Assessment]:
    """Sign, nakshatra and pada sensitivity of `body` from one crossing search."""
    if _unknown_lagna(ctx, body):
        return {k: UNKNOWN for k in ZODIAC_VALUES}
    return {k: assess_lon(ctx, body, _zodiac_times(ctx, body, m), f)
            for k, (m, f) in ZODIAC_VALUES.items()}


def assess_lon(ctx: ChartContext, body: str, change_times: Iterable[float],
               rule: Callable[[float], Hashable]) -> Assessment:
    """Sensitivity of a fact `rule(longitude of body)` that can change only at `change_times`
    (from `sign_changes`, `width_changes` or `target_changes`)."""
    if _unknown_lagna(ctx, body):
        return UNKNOWN
    return piecewise(ctx, change_times, lambda t: rule(lon_at(ctx, body, t)))


def assess_angle(ctx: ChartContext, a: str, b: str, targets: Iterable[float],
                 rule: Callable[[float], Hashable]) -> Assessment:
    """Sensitivity of a fact `rule(angle a − b)` that can change only where the angle crosses
    `targets`."""
    ts = tuple(targets)
    if not ts:
        return STABLE
    return piecewise(ctx, angle_changes(ctx, a, b, ts),
                     lambda t: rule(norm360(lon_at(ctx, a, t) - lon_at(ctx, b, t))))


def assess_station(ctx: ChartContext, body: Body) -> Assessment:
    """Retrograde status changes only at a station."""
    return piecewise(ctx, station_times(ctx, body),
                     lambda t: state_at(ctx, body, t).speed < 0)


def piecewise(ctx: ChartContext, change_times: Iterable[float],
              value_at: Callable[[float], Hashable]) -> Assessment:
    """Exact sensitivity of a fact over the closed interval [t − u, t + u] (module doc)."""
    w = _window(ctx)
    if w is None:
        return STABLE
    t = ctx.birth.jd_ut
    lo, hi = w
    now = value_at(t)
    cuts = sorted({c for c in change_times if lo < c < hi})
    # t is an edge too, so a change the root finder places a hair on the wrong side of t
    # still shows up in the piece next to t (margin ~0)
    edges = sorted({lo, hi, t, *cuts})
    interior = [(a, z, value_at((a + z) / 2)) for a, z in zip(edges, edges[1:], strict=False)]
    # both ends of the closed interval get their own zero-length piece: a change exactly at
    # t − u or t + u is decided by the value there, not by how a root was rounded
    pieces = [(lo, lo, value_at(lo)), *interior, (hi, hi, value_at(hi))]
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
    if any(_unknown_lagna(ctx, x) for x in bodies):
        return UNKNOWN
    return piecewise(ctx, (c for x in bodies for c in sign_changes(ctx, x)), value_at)
