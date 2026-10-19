"""Transit event search over a window (TRN-2; design §7.8).

Sign, nakshatra and pada ingresses, stations, conjunctions with natal points and returns. The
solver partitions motion at stations, so every crossing of a retrograde loop is returned, and a
station that turns back short of a natal point within `contact_orb_deg` is a `contact`.
"""

from __future__ import annotations

from typing import Any

from astro.calc.context import ChartContext
from astro.calc.core.angles import NAKSHATRA_SPAN, PADA_SPAN, SIGN_SPAN
from astro.calc.core.status import Status
from astro.calc.core.timescale import utc_from_jd
from astro.calc.engine import Deps, FeatureRequest
from astro.calc.ephemeris.port import BODIES
from astro.calc.model import FeatureResult, TransitEvent
from astro.calc.solver import contacts, crossings, find_stations
from astro.calc.transits.common import check_window, window

DEFAULT_KINDS = ("sign", "nakshatra", "station", "conjunction")
ALL_KINDS = ("sign", "nakshatra", "pada", "station", "conjunction")
_WIDTH = {"sign": SIGN_SPAN, "nakshatra": NAKSHATRA_SPAN, "pada": PADA_SPAN}


class TransitEvents:
    id = "transit_events"

    def requires(self, params: dict[str, Any]) -> list[FeatureRequest]:
        return [FeatureRequest.of("positions")] if "conjunction" in params.get(
            "kinds", DEFAULT_KINDS) else []

    def compute(self, ctx: ChartContext, deps: Deps, params: dict[str, Any]) -> FeatureResult:
        t0, t1 = window(params)
        bodies = tuple(params.get("bodies", BODIES))
        kinds = tuple(params.get("kinds", DEFAULT_KINDS))
        unknown_kinds = set(kinds) - set(ALL_KINDS)
        if unknown_kinds:
            raise ValueError(f"unknown event kinds {sorted(unknown_kinds)}")
        check_window(t0, t1, bodies)
        orb = float(params.get("contact_orb_deg", 1.0))
        targets: list[tuple[str, float]] = []
        if "conjunction" in kinds:
            natal = deps.get_one("positions")
            targets = [(f.subject, float(f.value)) for f in natal.facts
                       if f.kind == "longitude" and f.value is not None
                       and f.frame is None]
        ref = ctx.refdata
        events: list[TransitEvent] = []
        for body in bodies:
            lon = ctx.lon_fn(body)
            speed = ctx.speed_fn(body) if ctx.needs_speed(body) else None
            step = ctx.step_days(body)
            subj = f"graha:{body}"
            stations = find_stations(speed, t0, t1, step) if speed else []
            for kind in ("sign", "nakshatra", "pada"):
                if kind not in kinds:
                    continue
                for c in crossings(lon, t0, t1, step=step, speed=speed, width=_WIDTH[kind]):
                    target = ref.rashi_id(c.index) if kind == "sign" else ref.nakshatra_id(
                        c.index // 4 if kind == "pada" else c.index)
                    detail = {"ingress": kind}
                    if kind == "pada":
                        detail["pada"] = c.index % 4 + 1
                    events.append(self._event(ctx, "ingress", subj, target, c.jd, c.direction,
                                              detail))
            if "station" in kinds:
                for s in stations:
                    after = ctx.ephemeris.body(body, s + step / 4, ctx.profile).speed
                    motion = "direct" if after > 0 else "retrograde"
                    events.append(self._event(ctx, "station", subj, None, s,
                                              1 if motion == "direct" else -1,
                                              {"turns": motion}))
            if targets:
                tl = [lon_ for _, lon_ in targets]
                found = crossings(lon, t0, t1, step=step, speed=speed, targets=tl)
                for c in found:
                    natal_subj = targets[c.index][0]
                    kind = "return" if natal_subj == subj else "conjunction"
                    events.append(self._event(ctx, kind, subj, natal_subj, c.jd, c.direction,
                                              {"natal_longitude": tl[c.index]}))
                for ct in contacts(lon, t0, t1, stations, tl, orb, found):
                    events.append(self._event(ctx, "contact", subj, targets[ct.target_index][0],
                                              ct.jd, None, {"distance_deg": ct.distance,
                                                            "orb_deg": orb}))
        events.sort(key=lambda e: (e.start_utc, e.body, e.kind, e.target or ""))
        return FeatureResult(feature_id=self.id, status=Status.OK, events=tuple(events),
                             provenance={"bodies": bodies, "kinds": kinds})

    @staticmethod
    def _event(ctx: ChartContext, kind: str, body: str, target: str | None, jd: float,
               direction: int | None, detail: dict[str, Any]) -> TransitEvent:
        when = utc_from_jd(jd)
        motion = None if direction is None else ("direct" if direction > 0 else "retrograde")
        return TransitEvent(id=f"{ctx.chart_id}/event/{body}/{kind}/{target}/{when.isoformat()}",
                            kind=kind, body=body, target=target, start_utc=when, motion=motion,
                            detail=detail, profile_id=ctx.profile.id)
