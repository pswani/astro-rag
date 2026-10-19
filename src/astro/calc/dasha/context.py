"""Period-lord context (DAS-5; design §7.7, calc-review G-D3).

For each active period lord (MD, AD, PD at the as-of instant) the context lists the IDs of the
facts and relations that describe that lord in this chart: placement, houses it rules,
nakshatra, dignity, combustion, war, retrogression, aspects received and conjunctions, plus the
sub-period lord's relation to the MD lord. It holds references, never copies, so dasha rule cards
and retrieval read the same facts as everything else. Strength, functional role and karakatva
are not computed yet and are listed under `missing` rather than left out silently.
"""

from __future__ import annotations

from typing import Any

from astro.calc.context import ChartContext
from astro.calc.core.angles import houses_apart
from astro.calc.core.status import Status
from astro.calc.engine import Deps, FeatureRequest
from astro.calc.model import ChartFact, FeatureResult
from astro.calc.sensitivity import Assessment

MISSING = ("strength", "functional_role", "karakatva")
LORD_FACT_KINDS = ("sign", "nakshatra", "pada", "retrograde", "house", "dignity", "combust",
                   "graha_yuddha", "aspected_by", "conjunct_with", "dispositor_chain")


class DashaContext:
    id = "dasha_context"

    def requires(self, params: dict[str, Any]) -> list[FeatureRequest]:
        act = {"as_of": params["as_of"]} if "as_of" in params else {}
        return [FeatureRequest.of("dasha_active", **act), FeatureRequest.of("positions"),
                FeatureRequest.of("relations"), FeatureRequest.of("houses"),
                FeatureRequest.of("condition"), FeatureRequest.of("aspects")]

    def compute(self, ctx: ChartContext, deps: Deps, params: dict[str, Any]) -> FeatureResult:
        act = deps.get_one("dasha_active")
        pos, rel, houses = deps.get_one("positions"), deps.get_one("relations"), \
            deps.get_one("houses")
        others = [deps.get_one("condition"), deps.get_one("aspects"), houses, rel, pos]
        ref = ctx.refdata
        facts: list[ChartFact] = []
        md_lord = act.periods[0].lord
        for period in act.periods:
            subj = f"dasha:vimshottari:{period.level}"
            lord = period.lord
            facts.append(ctx.fact("period_lord", subj, lord))
            lord_houses = [f.subject for f in rel.facts
                           if f.kind == "lord_of" and f.frame == "lagna" and f.value == lord]
            if any(f.kind == "lord_of" and f.frame == "lagna" and f.value is None
                   for f in rel.facts):
                facts.append(ctx.unknown("lord_houses", subj))
            else:
                facts.append(ctx.fact("lord_houses", subj, tuple(lord_houses)))
            refs = [f.id for r in others for f in r.facts
                    if f.subject == lord and f.kind in LORD_FACT_KINDS]
            refs += [r.id for res in (deps.get_one("aspects"), rel) for r in res.relations
                     if lord in (r.source, r.target)]
            facts.append(ctx.fact("context_refs", subj, tuple(dict.fromkeys(refs))))
            if period.level != "MD":
                fa, fb = pos.fact("sign", md_lord), pos.fact("sign", lord)
                a = Assessment.combine(Assessment(fa.sensitivity, fa.margin_minutes),
                                       Assessment(fb.sensitivity, fb.margin_minutes))
                facts.append(ctx.fact("from_md_lord", subj,
                                      houses_apart(ref.rashi_index(fa.value),
                                                   ref.rashi_index(fb.value)),
                                      sensitivity=a.sensitivity, margins=a.margins))
                nat = ref.natural_friendship(lord, md_lord) if lord != md_lord else "same"
                if nat is None:
                    facts.append(ctx.unknown("md_lord_friendship", subj))
                else:
                    facts.append(ctx.fact("md_lord_friendship", subj, nat))
        return FeatureResult(feature_id=self.id, status=Status.OK, facts=tuple(facts),
                             periods=act.periods, provenance={"missing": MISSING,
                                                              "as_of": act.provenance["as_of"]})
