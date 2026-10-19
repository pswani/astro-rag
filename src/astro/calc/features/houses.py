"""Houses (CALC-4, REL-1 placement): house of each body per frame, and the sign of each house.

- Frame `lagna` uses the profile's house system. Whole-sign counts signs from the Lagna; Sripati
  and Placidus use the Swiss Ephemeris cusps (house i spans [cusp_i, cusp_i+1)). Where cusps are
  undefined (Placidus above the polar circles) the Lagna-frame houses are `unknown`.
- Other frames (`chandra`, `surya`, `graha:<id>`) count whole signs from the reference
  (bhavat-bhavam), recorded as `counting: whole_sign` in provenance.
- `house_sign` of a house is always sign-based from the frame's reference sign; lordships use it.
"""

from __future__ import annotations

from typing import Any

from astro.calc.context import ChartContext
from astro.calc.core.angles import houses_apart, norm360
from astro.calc.core.status import CalcError, Status
from astro.calc.core.timescale import MINUTE
from astro.calc.engine import Deps, FeatureRequest
from astro.calc.ephemeris.port import BODIES
from astro.calc.features.common import LAGNA, assessment_of, subject
from astro.calc.model import ChartFact, FeatureResult
from astro.calc.sensitivity import Assessment
from astro.calc.solver import grid

DEFAULT_FRAMES = ("lagna", "chandra", "surya")
_FRAME_REF = {"lagna": LAGNA, "chandra": "graha:moon", "surya": "graha:sun"}


def frame_reference(frame: str) -> str:
    if frame in _FRAME_REF:
        return _FRAME_REF[frame]
    if frame.startswith("graha:"):
        return frame
    raise ValueError(f"unknown frame {frame!r}")


def sripati_house(lon: float, cusps: tuple[float, ...]) -> int:
    for i in range(12):
        a, b = cusps[i], cusps[(i + 1) % 12]
        if norm360(lon - a) < norm360(b - a):
            return i + 1
    raise AssertionError("cusps do not cover the circle")  # pragma: no cover


class Houses:
    id = "houses"

    def requires(self, params: dict[str, Any]) -> list[FeatureRequest]:
        return [FeatureRequest.of("positions")]

    def compute(self, ctx: ChartContext, deps: Deps, params: dict[str, Any]) -> FeatureResult:
        pos = deps.get_one("positions")
        frames = tuple(params.get("frames", DEFAULT_FRAMES))
        ref = ctx.refdata
        facts: list[ChartFact] = []
        unavailable: dict[str, str] = {}
        for frame in frames:
            ref_subj = frame_reference(frame)
            ref_sign_f = pos.fact("sign", ref_subj)
            if ref_sign_f.value is None:
                facts += [ctx.unknown("house", subject(b), frame=frame) for b in BODIES]
                facts += [ctx.unknown("house_sign", f"bhava:{n}", frame=frame)
                          for n in range(1, 13)]
                continue
            ref_sign = ref.rashi_index(ref_sign_f.value)
            ref_a = assessment_of(ref_sign_f)
            for n in range(1, 13):
                facts.append(ctx.fact("house_sign", f"bhava:{n}",
                                      ref.rashi_id(ref_sign + n - 1), frame=frame,
                                      sensitivity=ref_a.sensitivity, margins=ref_a.margins))
            use_cusps = frame == "lagna" and ctx.profile.house_system in ("sripati", "placidus")
            frame_facts: list[ChartFact] = []
            for body in BODIES:
                subj = subject(body)
                if subj == ref_subj:
                    continue  # a graha is trivially in house 1 from itself
                sign_f = pos.fact("sign", subj)
                if use_cusps:
                    try:
                        house, a = self._cusp_house(ctx, body)
                    except CalcError as e:  # cusps undefined: only this frame is unknown
                        frame_facts = [ctx.unknown("house", subject(bd), frame=frame)
                                       for bd in BODIES if subject(bd) != ref_subj]
                        unavailable[frame] = f"{e.reason.value}: {e.detail}"
                        break
                else:
                    house = houses_apart(ref_sign, ref.rashi_index(sign_f.value))
                    a = Assessment.combine(ref_a, assessment_of(sign_f))
                frame_facts.append(ctx.fact("house", subj, house, frame=frame,
                                            sensitivity=a.sensitivity, margins=a.margins))
            facts += frame_facts
        return FeatureResult(feature_id=self.id, status=Status.OK, facts=tuple(facts),
                             provenance={"frames": frames,
                                         "lagna_system": ctx.profile.house_system,
                                         "other_frames_counting": "whole_sign",
                                         **({"unavailable": unavailable} if unavailable else {})})

    @staticmethod
    def _cusp_house(ctx: ChartContext, body: str) -> tuple[int, Assessment]:
        b = ctx.birth

        def house_at(t: float) -> int:
            cusps = ctx.ephemeris.cusps(t, b.latitude, b.longitude, ctx.profile)
            return sripati_house(ctx.ephemeris.body(body, t, ctx.profile).longitude, cusps)

        house = house_at(b.jd_ut)
        if b.u_days <= 0:
            return house, Assessment("stable", (None, None))
        # Cusps move with the Lagna: sample on the Lagna grid (calc-review G-C9). Margins are
        # accurate to one grid step.
        step = min(ctx.step_days(LAGNA), b.u_days)
        ts = grid(b.jd_ut - b.u_days, b.jd_ut + b.u_days, step)
        changes = [t for t in ts if house_at(t) != house]
        if not changes:
            return house, Assessment("stable", (None, None))
        before = [(b.jd_ut - t) / MINUTE for t in changes if t < b.jd_ut]
        after = [(t - b.jd_ut) / MINUTE for t in changes if t > b.jd_ut]
        return house, Assessment("sensitive", (min(before) if before else None,
                                               min(after) if after else None))


