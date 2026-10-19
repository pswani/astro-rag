"""Condition of each body (CALC-2): dignity, combustion, graha yuddha, gandanta, rashi sandhi.

Conventions come from the profile (calc-review G-C5…G-C8) and are provisional until reviewed:
- Dignity `bphs_v1`: debilitated in the debilitation sign; in the exaltation sign exalted, except
  where a moolatrikona range overlaps it (Moon in Taurus, Mercury in Virgo: exalted before the
  range, moolatrikona inside it, own sign after it); moolatrikona inside its range; own sign;
  otherwise the relationship to the sign lord on the profile's friendship basis. Node dignities
  are disputed and `unknown`.
- Combustion: angular distance in longitude to the Sun within the profile orb (the `_retro` orb
  when retrograde). The Sun and the nodes are never combust.
- Graha yuddha: two of the profile's bodies within `orb_deg` in longitude; the winner by the
  profile rule. A planet in several wars is a loser if it lost any of them; the relations keep
  every pair. Gandanta: within `arc_deg` of a water–fire junction (0°, 120°, 240°). Rashi sandhi:
  within `arc_deg` of a sign boundary.
Every fact's sensitivity comes from solving the relevant boundary crossings (CALC-7).
"""

from __future__ import annotations

from typing import Any

from astro.calc.context import ChartContext
from astro.calc.core.angles import deg_in_sign, norm360, sign_index, signed_diff
from astro.calc.core.status import Status
from astro.calc.engine import Deps, FeatureRequest
from astro.calc.ephemeris.port import BODIES
from astro.calc.features.common import (
    angle_changes,
    assess_boundaries,
    latitude_crossings,
    lon_at,
    piecewise,
    points,
    sign_at,
    sign_changes,
    state_at,
    station_times,
    subject,
    target_changes,
)
from astro.calc.features.friendship import grades
from astro.calc.model import ChartFact, FeatureResult, Relation
from astro.calc.profile import COMBUSTIBLE
from astro.calc.refdata import GRAHAS_7

JUNCTIONS = (0.0, 120.0, 240.0)


def dignity_of(ctx: ChartContext, graha: str, lon: float,
               lord_relation: str | None) -> str | None:
    d = ctx.refdata.dignities(graha)
    if d is None:
        return None
    s, deg = sign_index(lon), deg_in_sign(lon)
    mt_sign, mt_lo, mt_hi = d.moolatrikona
    if s == d.debilitation[0]:
        return "debilitated"
    if s == mt_sign and mt_lo <= deg < mt_hi:
        return "moolatrikona"
    if s == d.exaltation[0]:
        if s == mt_sign and deg >= mt_hi:  # Mercury in Virgo after 20°: own sign
            return "own"
        return "exalted"
    if s in ctx.refdata.own_signs(graha):
        return "own"
    return lord_relation


def dignity_boundaries(ctx: ChartContext, graha: str) -> list[float]:
    """Absolute longitudes where the dignity can change inside a sign."""
    d = ctx.refdata.dignities(graha)
    if d is None:
        return []
    mt_sign, lo, hi = d.moolatrikona
    return [mt_sign * 30.0 + lo, mt_sign * 30.0 + hi]


class Condition:
    id = "condition"

    def requires(self, params: dict[str, Any]) -> list[FeatureRequest]:
        # friendship grades come from the same tables as the friendship feature, evaluated at
        # each instant the dignity's sensitivity needs
        return [FeatureRequest.of("positions")]

    def compute(self, ctx: ChartContext, deps: Deps, params: dict[str, Any]) -> FeatureResult:
        pos = deps.get_one("positions")
        prof = ctx.profile
        facts: list[ChartFact] = []
        rels: list[Relation] = []
        basis = prof.dignity.friendship_basis
        lon = {subject(p): pos.fact("longitude", subject(p)).value for p in points(ctx)}

        t0 = ctx.birth.jd_ut
        sign_changes_all = [c for x in BODIES for c in sign_changes(ctx, x)]

        # dignity: depends on the graha's degree and, on the compound basis, on where its sign
        # lord stands; exact sensitivity over every change of those inputs (CALC-7)
        def dignity_at(g: str, t: float) -> str | None:
            s, gl = subject(g), lon_at(ctx, g, t)
            lord = ctx.refdata.sign_lord(sign_index(gl))
            if lord == s:
                return dignity_of(ctx, s, gl, None)
            natural, _, compound = grades(ctx.refdata, s, lord, sign_index(gl),
                                          sign_at(ctx, lord.split(":")[1], t))
            return dignity_of(ctx, s, gl, natural if basis == "natural" else compound)

        for g in BODIES:
            s = subject(g)
            if g not in GRAHAS_7:
                facts.append(ctx.unknown("dignity", s))
                continue
            changes = [*sign_changes_all,
                       *target_changes(ctx, g, tuple(dignity_boundaries(ctx, s)))]
            a = piecewise(ctx, changes, lambda t, g=g: dignity_at(g, t))
            facts.append(ctx.fact("dignity", s, f"dignity:{dignity_at(g, t0)}",
                                  sensitivity=a.sensitivity, margins=a.margins))

        # combustion: the orb depends on retrogression, so stations are change instants too
        orbs = prof.combustion.orbs  # complete: validated when the profile loads

        def combust_at(g: str, t: float) -> bool:
            st = state_at(ctx, g, t)
            orb = orbs[f"{g}_retro"] if st.speed < 0 and f"{g}_retro" in orbs else orbs[g]
            return abs(signed_diff(st.longitude, lon_at(ctx, "sun", t))) <= orb

        for g in BODIES:
            s = subject(g)
            if g not in COMBUSTIBLE:
                facts.append(ctx.fact("combust", s, False))
                continue
            radii = {orbs[g], orbs.get(f"{g}_retro", orbs[g])}
            targets = tuple(sorted({x for r in radii for x in (r, 360.0 - r)}))
            changes = [*angle_changes(ctx, g, "sun", targets), *station_times(ctx, g)]
            a = piecewise(ctx, changes, lambda t, g=g: combust_at(g, t))
            facts.append(ctx.fact("sun_distance", s, abs(signed_diff(lon[s], lon["graha:sun"])),
                                  unit="deg"))
            facts.append(ctx.fact("combust", s, combust_at(g, t0), sensitivity=a.sensitivity,
                                  margins=a.margins))

        # graha yuddha: wars start and end at ±orb; the winner flips where the longitudes
        # (lesser_longitude) or the latitudes (north_latitude) cross
        gy = prof.graha_yuddha
        pairs = [(a, b) for i, a in enumerate(gy.bodies) for b in gy.bodies[i + 1:]]

        def war_at(a: str, b: str, t: float) -> tuple[str, str] | None:
            """(winner, loser) if a and b are at war at t."""
            la, lb = lon_at(ctx, a, t), lon_at(ctx, b, t)
            if abs(signed_diff(la, lb)) > gy.orb_deg:
                return None
            if gy.winner == "north_latitude":
                a_wins = state_at(ctx, a, t).latitude >= state_at(ctx, b, t).latitude
            else:  # lesser along the zodiac: b ahead of a by less than 180°
                a_wins = signed_diff(lb, la) >= 0
            return (a, b) if a_wins else (b, a)

        def outcome_at(g: str, t: float) -> str:
            wars = [w for a, b in pairs if g in (a, b) and (w := war_at(a, b, t))]
            if any(lose == g for _, lose in wars):  # a loser if it lost any war
                return "loser"
            return "winner" if wars else "none"

        # a war starts and ends at ±orb; its winner flips where the longitudes
        # (lesser_longitude) or the latitudes (north_latitude) cross
        pair_changes = {}
        for a, b in pairs:
            times = [*angle_changes(ctx, a, b, (gy.orb_deg, 360.0 - gy.orb_deg, 0.0))]
            if gy.winner == "north_latitude":
                times += latitude_crossings(ctx, a, b)
            pair_changes[(a, b)] = times
        war_a = {g: piecewise(ctx, [c for p, ts in pair_changes.items() if g in p for c in ts],
                              lambda t, g=g: outcome_at(g, t)) for g in BODIES}
        for a, b in pairs:
            if (w := war_at(a, b, t0)) is None:
                continue
            win, lose = w
            pa = piecewise(ctx, pair_changes[(a, b)], lambda t, a=a, b=b: war_at(a, b, t))
            rels.append(Relation(id=f"{ctx.chart_id}/graha_yuddha/graha:{win}/graha:{lose}",
                                 kind="graha_yuddha", source=f"graha:{win}",
                                 target=f"graha:{lose}", system=f"orb_{gy.orb_deg}_{gy.winner}",
                                 value=f"graha:{win}", profile_id=prof.id,
                                 sensitivity=pa.sensitivity))
        for g in BODIES:
            a = war_a[g]
            facts.append(ctx.fact("graha_yuddha", subject(g), outcome_at(g, t0),
                                  sensitivity=a.sensitivity, margins=a.margins))

        # gandanta and rashi sandhi (bodies and the Lagna)
        g_arc, s_arc = prof.gandanta.arc_deg, prof.sandhi.arc_deg
        for p in points(ctx):
            s = subject(p)
            if lon[s] is None:
                facts += [ctx.unknown("gandanta", s), ctx.unknown("rashi_sandhi", s)]
                continue
            near_j = min(abs(signed_diff(lon[s], j)) for j in JUNCTIONS)
            near_b = abs(signed_diff(lon[s], round(lon[s] / 30.0) * 30.0))
            ga = assess_boundaries(ctx, p, [norm360(j + k * g_arc) for j in JUNCTIONS
                                       for k in (-1, 1)])
            sa = assess_boundaries(ctx, p, [norm360(k * 30.0 + d * s_arc) for k in range(12)
                                       for d in (-1, 1)])
            facts.append(ctx.fact("gandanta", s, near_j < g_arc, sensitivity=ga.sensitivity,
                                  margins=ga.margins))
            facts.append(ctx.fact("rashi_sandhi", s, near_b < s_arc,
                                  sensitivity=sa.sensitivity, margins=sa.margins))
        return FeatureResult(feature_id=self.id, status=Status.OK, facts=tuple(facts),
                             relations=tuple(rels),
                             provenance={"dignity": prof.dignity.model_dump(),
                                         "dignity_varga": "D1"})
