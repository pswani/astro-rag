"""Positions (CALC-1, CALC-2 subset): longitude, latitude, speed, retrograde, sign, degree,
nakshatra, pada and nakshatra lord for Sun…Saturn, Rahu, Ketu and the Lagna.

Continuous values carry the sensitivity of the finest discrete fact of the same body (pada),
so an uncertain time is never presented as a stable degree.
"""

from __future__ import annotations

from typing import Any

from astro.calc.context import ChartContext
from astro.calc.core.angles import deg_in_sign, nakshatra_index, pada, sign_index
from astro.calc.core.status import Status
from astro.calc.engine import Deps, FeatureRequest
from astro.calc.ephemeris.port import BODIES
from astro.calc.features.common import LAGNA, WIDTHS, assess_station, assess_width, subject
from astro.calc.model import ChartFact, FeatureResult
from astro.calc.sensitivity import STABLE, Assessment

KINDS = ("longitude", "latitude", "speed", "retrograde", "sign", "degree_in_sign", "nakshatra",
         "pada", "nakshatra_lord")


class Positions:
    id = "positions"

    def requires(self, params: dict[str, Any]) -> list[FeatureRequest]:
        return []

    def compute(self, ctx: ChartContext, deps: Deps, params: dict[str, Any]) -> FeatureResult:
        t = ctx.birth.jd_ut
        facts: list[ChartFact] = []
        for body in BODIES:
            st = ctx.ephemeris.body(body, t, ctx.profile)
            sign_a = assess_width(ctx, body, WIDTHS["sign"])
            nak_a = assess_width(ctx, body, WIDTHS["nakshatra"])
            pada_a = assess_width(ctx, body, WIDTHS["pada"])
            if body in ("rahu", "ketu") and ctx.profile.nodes.retrograde == "always":
                retro, retro_a = True, STABLE
            else:
                retro = st.speed < 0
                retro_a = assess_station(ctx, body)
            facts += self._body_facts(ctx, subject(body), st.longitude, pada_a, sign_a, nak_a)
            facts.append(ctx.fact("latitude", subject(body), st.latitude, unit="deg",
                                  sensitivity=pada_a.sensitivity, margins=pada_a.margins))
            facts.append(ctx.fact("speed", subject(body), st.speed, unit="deg/day",
                                  sensitivity=pada_a.sensitivity, margins=pada_a.margins))
            facts.append(ctx.fact("retrograde", subject(body), retro,
                                  sensitivity=retro_a.sensitivity, margins=retro_a.margins))
        if ctx.birth.time_known:
            b = ctx.birth
            asc = ctx.ephemeris.ascendant(t, b.latitude, b.longitude, ctx.profile)
            facts += self._body_facts(ctx, LAGNA, asc, assess_width(ctx, LAGNA, WIDTHS["pada"]),
                                      assess_width(ctx, LAGNA, WIDTHS["sign"]),
                                      assess_width(ctx, LAGNA, WIDTHS["nakshatra"]))
        else:
            facts += [ctx.unknown(k, LAGNA) for k in
                      ("longitude", "sign", "degree_in_sign", "nakshatra", "pada",
                       "nakshatra_lord")]
        ayan = ctx.ephemeris.ayanamsa(t, ctx.profile)
        facts.append(ctx.fact("ayanamsa", f"ayanamsa:{ctx.profile.ayanamsa.id}", ayan, unit="deg"))
        return FeatureResult(feature_id=self.id, status=Status.OK, facts=tuple(facts),
                             provenance={"delta_t_s": ctx.ephemeris.delta_t_seconds(t)})

    @staticmethod
    def _body_facts(ctx: ChartContext, subj: str, lon: float, pada_a: Assessment,
                    sign_a: Assessment, nak_a: Assessment) -> list[ChartFact]:
        n = nakshatra_index(lon)
        ref = ctx.refdata
        return [
            ctx.fact("longitude", subj, lon, unit="deg", sensitivity=pada_a.sensitivity,
                     margins=pada_a.margins),
            ctx.fact("degree_in_sign", subj, deg_in_sign(lon), unit="deg",
                     sensitivity=pada_a.sensitivity, margins=pada_a.margins),
            ctx.fact("sign", subj, ref.rashi_id(sign_index(lon)), sensitivity=sign_a.sensitivity,
                     margins=sign_a.margins),
            ctx.fact("nakshatra", subj, ref.nakshatra_id(n), sensitivity=nak_a.sensitivity,
                     margins=nak_a.margins),
            ctx.fact("nakshatra_lord", subj, ref.nakshatra_lord(n),
                     sensitivity=nak_a.sensitivity, margins=nak_a.margins),
            ctx.fact("pada", subj, pada(lon), sensitivity=pada_a.sensitivity,
                     margins=pada_a.margins),
        ]
