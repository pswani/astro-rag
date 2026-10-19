"""Parashari graha drishti and conjunctions (REL-1; calc-review G-R1).

Graha drishti is sign-based: every graha aspects the 7th sign from itself; Mars also the 4th and
8th, Jupiter the 5th and 9th, Saturn the 3rd and 10th. Node aspects follow the profile
(`none` by default, provisional). Counting is inclusive. A graha aspects the sign and every body
in it. Conjunction is "same sign" or "within an orb" per the profile.
"""

from __future__ import annotations

from typing import Any

from astro.calc.context import ChartContext
from astro.calc.core.angles import houses_apart, signed_diff
from astro.calc.core.status import Status
from astro.calc.engine import Deps, FeatureRequest
from astro.calc.ephemeris.port import BODIES
from astro.calc.features.common import (
    LAGNA,
    angle_changes,
    assess_angle,
    assessment_of,
    lon_fn,
    piecewise,
    sign_at,
    sign_changes,
    sign_piecewise,
    subject,
)
from astro.calc.model import ChartFact, FeatureResult, Relation
from astro.calc.sensitivity import STABLE, Assessment

SPECIAL = {"mars": (4, 7, 8), "jupiter": (5, 7, 9), "saturn": (3, 7, 10)}
NODE_ASPECTS = {"none": (), "seventh": (7,), "fifth_seventh_ninth": (5, 7, 9)}


def aspect_offsets(ctx: ChartContext, graha: str) -> tuple[int, ...]:
    if graha in ("rahu", "ketu"):
        return NODE_ASPECTS[ctx.profile.aspects.nodes]
    return SPECIAL.get(graha, (7,))


class Aspects:
    id = "aspects"

    def requires(self, params: dict[str, Any]) -> list[FeatureRequest]:
        return [FeatureRequest.of("positions")]

    def compute(self, ctx: ChartContext, deps: Deps, params: dict[str, Any]) -> FeatureResult:
        pos = deps.get_one("positions")
        ref, prof = ctx.refdata, ctx.profile
        sign = {subject(g): ref.rashi_index(pos.fact("sign", subject(g)).value) for g in BODIES}
        sign_a = {s: assessment_of(pos.fact("sign", s)) for s in sign}
        lagna_f = pos.fact("sign", LAGNA)
        rels: list[Relation] = []
        facts: list[ChartFact] = []

        offsets = {subject(g): aspect_offsets(ctx, g) for g in BODIES}
        bodies = list(sign)
        names = {s: s.split(":", 1)[1] for s in bodies}

        def hits(src: str, src_sign: int, target_sign: int) -> bool:
            return houses_apart(src_sign, target_sign) in offsets[src]

        def signs_at(t: float) -> dict[str, int]:
            return {x: sign_at(ctx, names[x], t) for x in bodies}

        for s in bodies:
            targets = [(sign[s] + off - 1) % 12 for off in offsets[s]]
            facts.append(ctx.fact("aspects_signs", s, tuple(ref.rashi_id(t) for t in targets),
                                  frame="rashi", sensitivity=sign_a[s].sensitivity,
                                  margins=sign_a[s].margins))
            for off, t in zip(offsets[s], targets, strict=True):
                rels.append(self._rel(ctx, "aspect", s, ref.rashi_id(t), off,
                                      sign_a[s].sensitivity))
                for other, os_ in sign.items():
                    if other != s and os_ == t:
                        a = Assessment.combine(sign_a[s], sign_a[other])
                        rels.append(self._rel(ctx, "aspect", s, other, off, a.sensitivity))

        # aspects received: exact sensitivity over every sign change of every body (CALC-7)
        def received_at(s: str):
            def value(t: float) -> tuple[str, ...]:
                sg = signs_at(t)
                return tuple(x for x in bodies if x != s and hits(x, sg[x], sg[s]))
            return value

        for s in bodies:
            value = received_at(s)
            a = sign_piecewise(ctx, [names[x] for x in bodies], value)
            facts.append(ctx.fact("aspected_by", s, value(ctx.birth.jd_ut), frame="rashi",
                                  sensitivity=a.sensitivity, margins=a.margins))

        # house aspects count whole signs from the Lagna sign; under a cusp-based house system
        # that is a different frame from the Houses feature's "lagna" (REL-3)
        house_frame = "lagna" if prof.house_system == "whole_sign" else "lagna_rashi"
        for n in range(1, 13):
            if lagna_f.value is None:
                facts.append(ctx.unknown("aspected_by", f"bhava:{n}", frame=house_frame))
                continue

            def house_value(t: float, n: int = n) -> tuple[str, ...]:
                sg = signs_at(t)
                target = (sign_at(ctx, LAGNA, t) + n - 1) % 12
                return tuple(x for x in bodies if hits(x, sg[x], target))

            a = sign_piecewise(ctx, [LAGNA, *(names[x] for x in bodies)], house_value)
            facts.append(ctx.fact("aspected_by", f"bhava:{n}", house_value(ctx.birth.jd_ut),
                                  frame=house_frame, sensitivity=a.sensitivity,
                                  margins=a.margins))

        # conjunctions
        conj = prof.conjunction
        lon = {s: pos.fact("longitude", s).value for s in bodies}
        orb_targets = () if conj.orb_deg is None else (conj.orb_deg, 360.0 - conj.orb_deg)

        def pairs(t: float | None) -> set[frozenset[str]]:
            out = set()
            sg = signs_at(t) if t is not None else sign
            lt = {x: lon_fn(ctx, names[x])(t) for x in bodies} if t is not None else lon
            for i, a in enumerate(bodies):
                for b in bodies[i + 1:]:
                    if {a, b} == {"graha:rahu", "graha:ketu"}:
                        continue
                    hit = sg[a] == sg[b] if conj.mode == "same_sign" else \
                        abs(signed_diff(lt[a], lt[b])) <= conj.orb_deg
                    if hit:
                        out.add(frozenset((a, b)))
            return out

        def change_times(s: str) -> list[float]:
            if conj.mode == "same_sign":
                return [c for x in bodies for c in sign_changes(ctx, names[x])]
            return [c for x in bodies if x != s
                    for c in angle_changes(ctx, names[s], names[x], orb_targets)]

        now_pairs = pairs(None)
        for p in sorted(now_pairs, key=sorted):
            a, b = sorted(p, key=bodies.index)
            pa = (Assessment.combine(sign_a[a], sign_a[b]) if conj.mode == "same_sign"
                  else assess_angle(ctx, names[a], names[b], list(orb_targets)))
            rels.append(Relation(
                id=f"{ctx.chart_id}/conjunction/{a}/{b}", kind="conjunction", source=a,
                target=b, system=conj.mode, direction="mutual",
                value=abs(signed_diff(lon[a], lon[b])), profile_id=prof.id,
                sensitivity=pa.sensitivity))
        for s in bodies:
            def partners(t: float, s: str = s) -> tuple[str, ...]:
                return tuple(x for x in bodies
                             if x != s and frozenset((s, x)) in pairs(t))

            a = piecewise(ctx, change_times(s), partners) if ctx.birth.u_days > 0 else STABLE
            facts.append(ctx.fact("conjunct_with", s, partners(ctx.birth.jd_ut), frame="rashi",
                                  sensitivity=a.sensitivity, margins=a.margins))
        return FeatureResult(feature_id=self.id, status=Status.OK, facts=tuple(facts),
                             relations=tuple(rels),
                             provenance={"aspects": prof.aspects.model_dump(),
                                         "conjunction": prof.conjunction.model_dump(),
                                         "house_aspects": {"frame": house_frame,
                                                           "counting": "whole_sign"}})

    @staticmethod
    def _rel(ctx: ChartContext, kind: str, source: str, target: str, offset: int,
             sensitivity: str) -> Relation:
        return Relation(id=f"{ctx.chart_id}/{kind}/{source}/{target}", kind=kind, source=source,
                        target=target, system=ctx.profile.aspects.system, value=offset,
                        profile_id=ctx.profile.id, sensitivity=sensitivity)  # type: ignore
