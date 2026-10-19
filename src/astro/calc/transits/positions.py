"""Transit positions at the as-of instant relative to the natal chart (TRN-1)."""

from __future__ import annotations

from typing import Any

from astro.calc.context import ChartContext
from astro.calc.core.angles import houses_apart, nakshatra_index, sign_index, signed_diff
from astro.calc.core.status import CalcError, Reason, Status
from astro.calc.engine import Deps, FeatureRequest
from astro.calc.ephemeris.port import BODIES
from astro.calc.features.common import is_retrograde
from astro.calc.model import ChartFact, FeatureResult
from astro.calc.transits.common import parse_instant

NATAL_REFERENCES = (("natal_lagna", "lagna"), ("natal_chandra", "graha:moon"))


class TransitPositions:
    id = "transit_positions"

    def requires(self, params: dict[str, Any]) -> list[FeatureRequest]:
        return [FeatureRequest.of("positions")]

    def compute(self, ctx: ChartContext, deps: Deps, params: dict[str, Any]) -> FeatureResult:
        natal = deps.get_one("positions")
        if "as_of" not in params:
            raise CalcError(Reason.MISSING_INPUT, "transit positions need as_of")
        t = parse_instant(params["as_of"])
        ref = ctx.refdata
        facts: list[ChartFact] = []
        natal_lons = {f.subject: f.value for f in natal.facts
                      if f.kind == "longitude" and f.value is not None}
        for body in BODIES:
            subj = f"graha:{body}"
            st = ctx.ephemeris.body(body, t, ctx.profile)
            s, n = sign_index(st.longitude), nakshatra_index(st.longitude)
            facts += [
                ctx.fact("longitude", subj, st.longitude, frame="transit", unit="deg"),
                ctx.fact("sign", subj, ref.rashi_id(s), frame="transit"),
                ctx.fact("nakshatra", subj, ref.nakshatra_id(n), frame="transit"),
                ctx.fact("retrograde", subj, is_retrograde(ctx, body, st.speed), frame="transit"),
            ]
            for frame, natal_subj in NATAL_REFERENCES:
                nf = natal.fact("sign", natal_subj)
                if nf.value is None:
                    facts.append(ctx.unknown("transit_house", subj, frame=frame))
                    continue
                h = houses_apart(ref.rashi_index(nf.value), s)
                facts.append(ctx.fact("transit_house", subj, h, frame=frame,
                                      sensitivity=nf.sensitivity, margins=nf.margin_minutes))
            for natal_subj, lon in natal_lons.items():
                facts.append(ctx.fact("transit_distance", subj,
                                      signed_diff(st.longitude, float(lon)),
                                      frame=f"natal:{natal_subj}", unit="deg"))
        return FeatureResult(feature_id=self.id, status=Status.OK, facts=tuple(facts),
                             provenance={"as_of": params["as_of"]})
