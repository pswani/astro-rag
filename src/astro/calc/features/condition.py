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
    assess_angle,
    assess_boundaries,
    assessment_of,
    points,
    subject,
)
from astro.calc.model import ChartFact, FeatureResult, Relation
from astro.calc.refdata import GRAHAS_7
from astro.calc.sensitivity import Assessment

COMBUSTIBLE = ("moon", "mars", "mercury", "jupiter", "venus", "saturn")
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
        return [FeatureRequest.of("positions"), FeatureRequest.of("friendship")]

    def compute(self, ctx: ChartContext, deps: Deps, params: dict[str, Any]) -> FeatureResult:
        pos, fr = deps.get_one("positions"), deps.get_one("friendship")
        prof = ctx.profile
        facts: list[ChartFact] = []
        rels: list[Relation] = []
        basis = prof.dignity.friendship_basis
        friendship = {(r.source, r.target): r for r in fr.relations if r.system == basis}
        lon = {subject(p): pos.fact("longitude", subject(p)).value for p in points(ctx)}
        sign_a = {subject(p): assessment_of(pos.fact("sign", subject(p))) for p in points(ctx)}

        # dignity
        for g in BODIES:
            s = subject(g)
            if g not in GRAHAS_7:
                facts.append(ctx.unknown("dignity", s))
                continue
            lord = ctx.refdata.sign_lord(sign_index(lon[s]))
            rel = friendship.get((s, lord))
            dig = dignity_of(ctx, s, lon[s], None if rel is None else rel.value)
            a = Assessment.combine(sign_a[s], assess_boundaries(ctx, g, dignity_boundaries(ctx, s)))
            if rel is not None and basis == "compound":  # temporal part moves with the lord
                a = Assessment.combine(a, sign_a.get(lord, a))
            facts.append(ctx.fact("dignity", s, f"dignity:{dig}", sensitivity=a.sensitivity,
                                  margins=a.margins))

        # combustion
        sun = lon["graha:sun"]
        for g in BODIES:
            s = subject(g)
            dist = abs(signed_diff(lon[s], sun))
            if g not in COMBUSTIBLE:
                facts.append(ctx.fact("combust", s, False))
                continue
            retro = pos.fact("retrograde", s).value
            orb = prof.combustion.orbs.get(f"{g}_retro" if retro else g,
                                           prof.combustion.orbs[g])
            a = assess_angle(ctx, g, "sun", [orb, 360.0 - orb])
            facts.append(ctx.fact("sun_distance", s, dist, unit="deg"))
            facts.append(ctx.fact("combust", s, dist <= orb, sensitivity=a.sensitivity,
                                  margins=a.margins))

        # graha yuddha
        gy = prof.graha_yuddha
        won: dict[str, int] = {f"graha:{g}": 0 for g in BODIES}
        lost: dict[str, int] = {f"graha:{g}": 0 for g in BODIES}
        war_a = {f"graha:{g}": Assessment("stable", (None, None)) for g in BODIES}
        for i, ga in enumerate(gy.bodies):
            for gb in gy.bodies[i + 1:]:
                sa, sb = f"graha:{ga}", f"graha:{gb}"
                a = assess_angle(ctx, ga, gb, [gy.orb_deg, 360.0 - gy.orb_deg])
                war_a[sa] = Assessment.combine(war_a[sa], a)
                war_a[sb] = Assessment.combine(war_a[sb], a)
                if abs(signed_diff(lon[sa], lon[sb])) > gy.orb_deg:
                    continue
                win, lose = self._winner(pos, sa, sb, lon, gy.winner)
                won[win] += 1
                lost[lose] += 1
                rels.append(Relation(id=f"{ctx.chart_id}/graha_yuddha/{win}/{lose}",
                                     kind="graha_yuddha", source=win, target=lose,
                                     system=f"orb_{gy.orb_deg}_{gy.winner}", value=win,
                                     profile_id=prof.id, sensitivity=a.sensitivity))
        for s in won:
            # a planet in several wars is a loser if it lost any of them
            v = "loser" if lost[s] else "winner" if won[s] else "none"
            a = war_a[s]
            facts.append(ctx.fact("graha_yuddha", s, v, sensitivity=a.sensitivity,
                                  margins=a.margins))

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

    @staticmethod
    def _winner(pos, sa: str, sb: str, lon: dict, rule: str) -> tuple[str, str]:
        if rule == "north_latitude":
            la, lb = pos.fact("latitude", sa).value, pos.fact("latitude", sb).value
            return (sa, sb) if la >= lb else (sb, sa)
        # "lesser" along the zodiac: sb ahead of sa by less than 180° means sa is behind
        return (sa, sb) if signed_diff(lon[sb], lon[sa]) >= 0 else (sb, sa)
