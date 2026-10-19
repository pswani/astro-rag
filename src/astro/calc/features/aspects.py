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
from astro.calc.features.common import LAGNA, assessment_of, subject
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
        received: dict[str, list[tuple[str, Assessment]]] = {s: [] for s in sign}
        house_received: dict[int, list[tuple[str, Assessment]]] = {n: [] for n in range(1, 13)}
        facts: list[ChartFact] = []

        for g in BODIES:
            s = subject(g)
            offsets = aspect_offsets(ctx, g)
            targets = [(sign[s] + off - 1) % 12 for off in offsets]
            facts.append(ctx.fact("aspects_signs", s, tuple(ref.rashi_id(t) for t in targets),
                                  frame="rashi", sensitivity=sign_a[s].sensitivity,
                                  margins=sign_a[s].margins))
            for off, t in zip(offsets, targets, strict=True):
                rels.append(self._rel(ctx, "aspect", s, ref.rashi_id(t), off,
                                      sign_a[s].sensitivity))
                for other, os_ in sign.items():
                    if other != s and os_ == t:
                        a = Assessment.combine(sign_a[s], sign_a[other])
                        rels.append(self._rel(ctx, "aspect", s, other, off, a.sensitivity))
                        received[other].append((s, a))
                if lagna_f.value is not None:
                    n = houses_apart(ref.rashi_index(lagna_f.value), t)
                    house_received[n].append((s, Assessment.combine(
                        sign_a[s], assessment_of(lagna_f))))

        for s, items in received.items():
            a = Assessment.combine(sign_a[s], *(x for _, x in items))
            facts.append(ctx.fact("aspected_by", s, tuple(src for src, _ in items),
                                  frame="rashi", sensitivity=a.sensitivity, margins=a.margins))
        for n, items in house_received.items():
            if lagna_f.value is None:
                facts.append(ctx.unknown("aspected_by", f"bhava:{n}", frame="lagna"))
                continue
            a = Assessment.combine(assessment_of(lagna_f), *(x for _, x in items))
            facts.append(ctx.fact("aspected_by", f"bhava:{n}", tuple(src for src, _ in items),
                                  frame="lagna", sensitivity=a.sensitivity, margins=a.margins))

        # conjunctions
        conj = prof.conjunction
        lon = {s: pos.fact("longitude", s).value for s in sign}
        partners: dict[str, list[str]] = {s: [] for s in sign}
        subjects = list(sign)
        for i, a in enumerate(subjects):
            for b in subjects[i + 1:]:
                if {a, b} == {"graha:rahu", "graha:ketu"}:
                    continue
                if conj.mode == "same_sign":
                    hit = sign[a] == sign[b]
                else:
                    hit = abs(signed_diff(lon[a], lon[b])) <= conj.orb_deg
                if hit:
                    sens = Assessment.combine(sign_a[a], sign_a[b]).sensitivity
                    rels.append(Relation(
                        id=f"{ctx.chart_id}/conjunction/{a}/{b}", kind="conjunction", source=a,
                        target=b, system=conj.mode, direction="mutual",
                        value=abs(signed_diff(lon[a], lon[b])), profile_id=prof.id,
                        sensitivity=sens))
                    partners[a].append(b)
                    partners[b].append(a)
        for s, ps in partners.items():
            a = Assessment.combine(sign_a[s], *(sign_a[p] for p in ps))
            facts.append(ctx.fact("conjunct_with", s, tuple(ps), frame="rashi",
                                  sensitivity=a.sensitivity, margins=a.margins))
        return FeatureResult(feature_id=self.id, status=Status.OK, facts=tuple(facts),
                             relations=tuple(rels),
                             provenance={"aspects": prof.aspects.model_dump(),
                                         "conjunction": prof.conjunction.model_dump()})

    @staticmethod
    def _rel(ctx: ChartContext, kind: str, source: str, target: str, offset: int,
             sensitivity: str) -> Relation:
        return Relation(id=f"{ctx.chart_id}/{kind}/{source}/{target}", kind=kind, source=source,
                        target=target, system=ctx.profile.aspects.system, value=offset,
                        profile_id=ctx.profile.id, sensitivity=sensitivity)  # type: ignore
