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
from astro.calc.features.common import LAGNA, assess_angle, assessment_of, subject
from astro.calc.model import ChartFact, FeatureResult, Relation
from astro.calc.sensitivity import Assessment

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

        # Signs a body can occupy inside [t − u, t + u]: a sensitive sign can move one step
        # either way (the Moon moves under 14° a day). Facts change only if some reachable
        # combination changes them (CALC-7).
        def reach(a: Assessment, s: int) -> tuple[int, ...]:
            return (s,) if a.sensitivity == "stable" else ((s - 1) % 12, s, (s + 1) % 12)

        offsets = {subject(g): aspect_offsets(ctx, g) for g in BODIES}

        def hits(src: str, src_sign: int, target_sign: int) -> bool:
            return houses_apart(src_sign, target_sign) in offsets[src]

        def changes(src: str, target_sign: int, target_reach: tuple[int, ...]) -> bool:
            now = hits(src, sign[src], target_sign)
            return any(hits(src, a, b) != now for a in reach(sign_a[src], sign[src])
                       for b in target_reach)

        for s in sign:
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

        for s in sign:
            by = tuple(x for x in sign if x != s and hits(x, sign[x], sign[s]))
            moving = [Assessment.combine(sign_a[x], sign_a[s]) for x in sign
                      if x != s and changes(x, sign[s], reach(sign_a[s], sign[s]))]
            a = Assessment.combine(Assessment("stable", (None, None)), *moving)
            facts.append(ctx.fact("aspected_by", s, by, frame="rashi",
                                  sensitivity=a.sensitivity, margins=a.margins))

        # house aspects count whole signs from the Lagna sign; under a cusp-based house system
        # that is a different frame from the Houses feature's "lagna" (REL-3)
        house_frame = "lagna" if prof.house_system == "whole_sign" else "lagna_rashi"
        for n in range(1, 13):
            if lagna_f.value is None:
                facts.append(ctx.unknown("aspected_by", f"bhava:{n}", frame=house_frame))
                continue
            la = assessment_of(lagna_f)
            target = (ref.rashi_index(lagna_f.value) + n - 1) % 12
            target_reach = tuple((x + n - 1) % 12
                                 for x in reach(la, ref.rashi_index(lagna_f.value)))
            by = tuple(x for x in sign if hits(x, sign[x], target))
            moving = [Assessment.combine(sign_a[x], la) for x in sign
                      if changes(x, target, target_reach)]
            a = Assessment.combine(Assessment("stable", (None, None)), *moving)
            facts.append(ctx.fact("aspected_by", f"bhava:{n}", by, frame=house_frame,
                                  sensitivity=a.sensitivity, margins=a.margins))

        # conjunctions
        conj = prof.conjunction
        lon = {s: pos.fact("longitude", s).value for s in sign}
        partners: dict[str, list[str]] = {s: [] for s in sign}
        moving_pairs: dict[str, list[Assessment]] = {s: [] for s in sign}
        subjects = list(sign)
        for i, a in enumerate(subjects):
            for b in subjects[i + 1:]:
                if {a, b} == {"graha:rahu", "graha:ketu"}:
                    continue
                if conj.mode == "same_sign":
                    hit = sign[a] == sign[b]
                    varies = any((x == y) != hit for x in reach(sign_a[a], sign[a])
                                 for y in reach(sign_a[b], sign[b]))
                    pair_a = Assessment.combine(sign_a[a], sign_a[b]) if varies else \
                        Assessment("stable", (None, None))
                else:  # the conjunction appears or ends where the angle crosses ±orb
                    hit = abs(signed_diff(lon[a], lon[b])) <= conj.orb_deg
                    pair_a = assess_angle(ctx, a.split(":")[1], b.split(":")[1],
                                          [conj.orb_deg, 360.0 - conj.orb_deg])
                if pair_a.sensitivity != "stable":
                    moving_pairs[a].append(pair_a)
                    moving_pairs[b].append(pair_a)
                if hit:
                    rels.append(Relation(
                        id=f"{ctx.chart_id}/conjunction/{a}/{b}", kind="conjunction", source=a,
                        target=b, system=conj.mode, direction="mutual",
                        value=abs(signed_diff(lon[a], lon[b])), profile_id=prof.id,
                        sensitivity=pair_a.sensitivity))
                    partners[a].append(b)
                    partners[b].append(a)
        for s, ps in partners.items():
            a = Assessment.combine(Assessment("stable", (None, None)), *moving_pairs[s])
            facts.append(ctx.fact("conjunct_with", s, tuple(ps), frame="rashi",
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
