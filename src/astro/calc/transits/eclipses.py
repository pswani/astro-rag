"""Solar and lunar eclipses in a window with contact to natal points (TRN-5)."""

from __future__ import annotations

from typing import Any

from astro.calc.context import ChartContext
from astro.calc.core.angles import signed_diff
from astro.calc.core.status import Status
from astro.calc.core.timescale import utc_from_jd
from astro.calc.engine import Deps, FeatureRequest
from astro.calc.model import FeatureResult, TransitEvent
from astro.calc.transits.common import check_window, window


class Eclipses:
    id = "eclipses"

    def requires(self, params: dict[str, Any]) -> list[FeatureRequest]:
        return [FeatureRequest.of("positions")]

    def compute(self, ctx: ChartContext, deps: Deps, params: dict[str, Any]) -> FeatureResult:
        t0, t1 = window(params)
        check_window(t0, t1, ("sun",))
        orb = ctx.profile.eclipse.orb_deg
        natal = [(f.subject, float(f.value)) for f in deps.get_one("positions").facts
                 if f.kind == "longitude" and f.value is not None]
        events = []
        for e in ctx.ephemeris.eclipses(t0, t1, ctx.profile):
            hits = sorted(({"point": subj, "distance_deg": abs(signed_diff(e.longitude, lon))}
                           for subj, lon in natal if abs(signed_diff(e.longitude, lon)) <= orb),
                          key=lambda h: h["distance_deg"])
            when = utc_from_jd(e.jd_max)
            events.append(TransitEvent(
                id=f"{ctx.chart_id}/eclipse/{e.kind}/{when.isoformat()}", kind="eclipse",
                body="graha:sun" if e.kind == "solar" else "graha:moon",
                target=ctx.refdata.rashi_id(int(e.longitude // 30)), start_utc=when,
                detail={"eclipse": e.kind, "type": e.eclipse_type, "longitude": e.longitude,
                        "contacts": hits, "orb_deg": orb},
                profile_id=ctx.profile.id))
        return FeatureResult(feature_id=self.id, status=Status.OK, events=tuple(events))
