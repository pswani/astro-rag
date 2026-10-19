"""Panchanga at birth (PAN-1, PAN-2; design §7.4).

With Δ = λ_moon − λ_sun and sidereal longitudes:
tithi = floor(Δ / 12) + 1, karana k = floor(Δ / 6), nakshatra from λ_moon,
nitya yoga = floor((λ_sun + λ_moon) mod 360 / (40/3)) + 1, vara = weekday of the last sunrise.
Start and end times are solved on the angle, never assumed from fixed durations. Δ and the sum
both increase monotonically, so a 6-hour grid brackets every boundary.
"""

from __future__ import annotations

from typing import Any

from astro.calc.context import ChartContext
from astro.calc.core.angles import NAKSHATRA_SPAN, norm360
from astro.calc.core.status import Status
from astro.calc.core.timescale import MINUTE, utc_from_jd, weekday_index
from astro.calc.engine import Deps, FeatureRequest
from astro.calc.model import ChartFact, FeatureResult
from astro.calc.sensitivity import Assessment, assess
from astro.calc.solver import first_crossing_after, last_crossing_before

STEP = 0.25   # days
SPAN = 2.0    # days: longer than any tithi, karana, nakshatra or nitya yoga


def _iso(jd: float) -> str:
    return utc_from_jd(jd).isoformat()


class Panchanga:
    id = "panchanga"

    def requires(self, params: dict[str, Any]) -> list[FeatureRequest]:
        return []

    def compute(self, ctx: ChartContext, deps: Deps, params: dict[str, Any]) -> FeatureResult:
        eph, prof, b = ctx.ephemeris, ctx.profile, ctx.birth
        t = b.jd_ut
        sun = lambda x: eph.body("sun", x, prof).longitude  # noqa: E731
        moon = lambda x: eph.body("moon", x, prof).longitude  # noqa: E731
        delta = lambda x: norm360(moon(x) - sun(x))  # noqa: E731
        total = lambda x: norm360(moon(x) + sun(x))  # noqa: E731
        ref = ctx.refdata
        facts: list[ChartFact] = []

        d = delta(t)
        tithi = min(int(d // 12.0), 29)
        karana = min(int(d // 6.0), 59)
        nak = min(int(moon(t) * 3.0 // 40.0), 26)
        yoga = min(int(total(t) * 3.0 // 40.0), 26)
        limbs = [
            ("tithi", ref.tithi_id(tithi), delta, 12.0),
            ("karana", ref.karana_id(karana), delta, 6.0),
            ("nakshatra", ref.nakshatra_id(nak), moon, NAKSHATRA_SPAN),
            ("nitya_yoga", ref.nitya_yoga_id(yoga), total, NAKSHATRA_SPAN),
        ]
        for kind, value, fn, width in limbs:
            subj = f"panchanga:{kind}"
            a = assess(fn, t, b.u_days, width=width, step=STEP)
            start = last_crossing_before(fn, t, width=width, step=STEP, span=SPAN)
            end = first_crossing_after(fn, t, width=width, step=STEP, span=SPAN)
            fact_kind = "nakshatra" if kind == "nakshatra" else kind
            facts.append(ctx.fact(fact_kind, subj, value, sensitivity=a.sensitivity,
                                  margins=a.margins))
            facts.append(ctx.fact("limb_start", subj, _iso(start.jd)))
            facts.append(ctx.fact("limb_end", subj, _iso(end.jd)))
            if kind == "tithi":
                paksha = "paksha:shukla" if tithi < 15 else "paksha:krishna"
                pa = assess(fn, t, b.u_days, width=180.0, step=STEP)
                facts.append(ctx.fact("paksha", "panchanga:paksha", paksha,
                                      sensitivity=pa.sensitivity, margins=pa.margins))

        provenance: dict[str, Any] = {"sunrise": prof.sunrise.definition,
                                      "elevation_m": b.elevation_m}
        rise = self._last_sunrise(ctx, t)
        if rise is None:
            provenance["unavailable"] = {"vara": "no_sunrise", "sunrise": "no_sunrise"}
            facts += [ctx.unknown("vara", "panchanga:vara"),
                      ctx.unknown("sunrise", "panchanga:sunrise"),
                      ctx.unknown("sunset", "panchanga:sunset")]
        else:
            sset = eph.rise_set(rise, b.latitude, b.longitude, b.elevation_m, "set", prof)
            # weekday of the sunrise on the local mean-time calendar
            vara, _lord = ref.vara(weekday_index(rise + b.longitude / 360.0))
            a = self._vara_assessment(ctx, t, rise)
            facts.append(ctx.fact("vara", "panchanga:vara", vara, sensitivity=a.sensitivity,
                                  margins=a.margins))
            facts.append(ctx.fact("sunrise", "panchanga:sunrise", _iso(rise)))
            if sset is None:
                facts.append(ctx.unknown("sunset", "panchanga:sunset"))
            else:
                facts.append(ctx.fact("sunset", "panchanga:sunset", _iso(sset)))
        return FeatureResult(feature_id=self.id, status=Status.OK, facts=tuple(facts),
                             provenance=provenance)

    @staticmethod
    def _sunrises(ctx: ChartContext, t0: float, t1: float) -> list[float]:
        b, eph, prof = ctx.birth, ctx.ephemeris, ctx.profile
        out, cur = [], t0
        while True:
            r = eph.rise_set(cur, b.latitude, b.longitude, b.elevation_m, "rise", prof)
            if r is None or r > t1:
                return out
            out.append(r)
            cur = r + 10 * MINUTE

    def _last_sunrise(self, ctx: ChartContext, t: float) -> float | None:
        rises = self._sunrises(ctx, t - 1.5, t)
        return rises[-1] if rises else None

    def _vara_assessment(self, ctx: ChartContext, t: float, rise: float) -> Assessment:
        u = ctx.birth.u_days
        if u <= 0:
            return Assessment("stable", (None, None))
        inside = [r for r in self._sunrises(ctx, t - u, t + u) if t - u < r <= t + u]
        if not inside:
            return Assessment("stable", (None, None))
        before = [(t - r) / MINUTE for r in inside if r <= t]
        after = [(r - t) / MINUTE for r in inside if r > t]
        return Assessment("sensitive", (min(before) if before else None,
                                        min(after) if after else None))
