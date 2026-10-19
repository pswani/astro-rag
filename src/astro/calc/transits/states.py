"""Named transit states as intervals (TRN-3 subset; design §7.8).

Sade Sati (Saturn in the 12th, 1st or 2nd sign from the natal Moon, with phase), Ashtama Shani
(8th), Kantaka Shani (4th, 7th, 10th), Jupiter's house from the Moon, the Jupiter–Saturn double
transit (a sign both occupy or aspect, by the profile's sign-based graha drishti) and the
Rahu–Ketu axis over natal points (a node in the sign of a natal point). Retrograde re-entries
produce separate intervals.
"""

from __future__ import annotations

from typing import Any

from astro.calc.context import ChartContext
from astro.calc.core.angles import SIGN_SPAN, houses_apart, sign_index
from astro.calc.core.status import CalcError, Reason, Status
from astro.calc.core.timescale import utc_from_jd
from astro.calc.engine import Deps, FeatureRequest
from astro.calc.features.aspects import aspect_offsets
from astro.calc.model import FeatureResult, TransitEvent
from astro.calc.solver import crossings
from astro.calc.transits.common import check_window, window

SADE_SATI_PHASE = {12: "rising", 1: "peak", 2: "setting"}


def sign_segments(ctx: ChartContext, body: str, t0: float, t1: float
                  ) -> list[tuple[float, float, int]]:
    """Half-open [start, end) pieces of the window in which `body` stays in one sign."""
    lon = ctx.lon_fn(body)  # type: ignore[arg-type]
    speed = ctx.speed_fn(body) if ctx.needs_speed(body) else None  # type: ignore[arg-type]
    cs = crossings(lon, t0, t1, step=ctx.step_days(body), speed=speed, width=SIGN_SPAN)
    edges = [t0, *(c.jd for c in cs if t0 < c.jd < t1), t1]
    out = []
    for a, b in zip(edges, edges[1:], strict=False):
        if b > a:
            out.append((a, b, sign_index(lon((a + b) / 2))))
    return out


def merge(pieces: list[tuple[float, float, Any]]) -> list[tuple[float, float, Any]]:
    out: list[tuple[float, float, Any]] = []
    for a, b, v in pieces:
        if out and out[-1][2] == v and out[-1][1] == a:
            out[-1] = (out[-1][0], b, v)
        else:
            out.append((a, b, v))
    return out


class TransitStates:
    id = "transit_states"

    def requires(self, params: dict[str, Any]) -> list[FeatureRequest]:
        return [FeatureRequest.of("positions")]

    def compute(self, ctx: ChartContext, deps: Deps, params: dict[str, Any]) -> FeatureResult:
        t0, t1 = window(params)
        check_window(t0, t1, ("saturn", "jupiter"))
        moon = deps.get_one("positions").fact("sign", "graha:moon")
        if moon.value is None:  # pragma: no cover - the Moon's sign is always computed
            raise CalcError(Reason.MISSING_INPUT, "natal Moon sign unknown")
        moon_sign = ctx.refdata.rashi_index(moon.value)
        events: list[TransitEvent] = []

        sat = [(a, b, houses_apart(moon_sign, s))
               for a, b, s in sign_segments(ctx, "saturn", t0, t1)]

        def emit(state: str, body: str, pieces, detail_fn, key: str = "") -> None:
            for a, b, v in merge(pieces):
                if v is None:
                    continue
                suffix = f"/{key}" if key else ""
                events.append(TransitEvent(
                    id=f"{ctx.chart_id}/state/{state}{suffix}/{utc_from_jd(a).isoformat()}",
                    kind="state", body=f"graha:{body}", target=f"state:{state}",
                    start_utc=utc_from_jd(a), end_utc=utc_from_jd(b),
                    detail={**detail_fn(v), "clipped_start": a == t0, "clipped_end": b == t1},
                    profile_id=ctx.profile.id))

        emit("sade_sati", "saturn", [(a, b, True if h in SADE_SATI_PHASE else None)
                                     for a, b, h in sat], lambda v: {})
        emit("sade_sati_phase", "saturn", [(a, b, SADE_SATI_PHASE.get(h)) for a, b, h in sat],
             lambda v: {"phase": v})
        emit("ashtama_shani", "saturn", [(a, b, True if h == 8 else None) for a, b, h in sat],
             lambda v: {})
        emit("kantaka_shani", "saturn", [(a, b, h if h in (4, 7, 10) else None)
                                         for a, b, h in sat], lambda v: {"house_from_moon": v})
        jup = [(a, b, houses_apart(moon_sign, s))
               for a, b, s in sign_segments(ctx, "jupiter", t0, t1)]
        emit("jupiter_from_moon", "jupiter", jup, lambda v: {"house_from_moon": v})

        # Jupiter–Saturn double transit: signs both occupy or aspect
        natal = deps.get_one("positions")
        lagna_f = natal.fact("sign", "lagna")
        lagna_sign = None if lagna_f.value is None else ctx.refdata.rashi_index(lagna_f.value)
        jseg = sign_segments(ctx, "jupiter", t0, t1)
        sseg = sign_segments(ctx, "saturn", t0, t1)
        edges = sorted({t0, t1, *(a for a, _, _ in jseg), *(a for a, _, _ in sseg)})
        sign_at = lambda segs, t: next(s for a, b, s in segs if a <= t < b)  # noqa: E731
        both: dict[int, list[tuple[float, float, Any]]] = {s: [] for s in range(12)}
        for a, b in zip(edges, edges[1:], strict=False):
            mid = (a + b) / 2
            js, ss = sign_at(jseg, mid), sign_at(sseg, mid)
            jset = {js, *((js + o - 1) % 12 for o in aspect_offsets(ctx, "jupiter"))}
            sset = {ss, *((ss + o - 1) % 12 for o in aspect_offsets(ctx, "saturn"))}
            for s in range(12):
                both[s].append((a, b, True if s in jset & sset else None))
        for s, pieces in both.items():
            emit("double_transit", "jupiter", pieces, lambda v, s=s: {
                "sign": ctx.refdata.rashi_id(s), "house_from_moon": houses_apart(moon_sign, s),
                "house_from_lagna": None if lagna_sign is None else houses_apart(lagna_sign, s),
            }, key=ctx.refdata.rashi_id(s))

        # Rahu–Ketu axis over natal points (sign-based)
        rseg = sign_segments(ctx, "rahu", t0, t1)
        for f in natal.facts:
            if f.kind != "sign" or f.frame is not None or f.value is None:
                continue
            ps = ctx.refdata.rashi_index(f.value)
            pieces = [(a, b, "rahu" if s == ps else "ketu" if (s + 6) % 12 == ps else None)
                      for a, b, s in rseg]
            emit("node_axis", "rahu", pieces, lambda v, subj=f.subject: {
                "natal_point": subj, "node": f"graha:{v}"}, key=f.subject)
        events.sort(key=lambda e: (e.start_utc, e.target or ""))
        return FeatureResult(feature_id=self.id, status=Status.OK, events=tuple(events),
                             provenance={"natal_moon_sign": moon.value,
                                         "natal_moon_sensitivity": moon.sensitivity})
