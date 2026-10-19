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
from astro.calc.core.angles import houses_apart
from astro.calc.core.status import CalcError, Reason, Status
from astro.calc.engine import Deps, FeatureRequest
from astro.calc.ephemeris.port import BODIES
from astro.calc.features.common import (
    LAGNA,
    assessment_of,
    cusp_changes,
    cusp_house_at,
    subject,
    times_assessment,
)
from astro.calc.model import ChartFact, FeatureResult
from astro.calc.sensitivity import Assessment

DEFAULT_FRAMES = ("lagna", "chandra", "surya")
_FRAME_REF = {"lagna": LAGNA, "chandra": "graha:moon", "surya": "graha:sun"}


def frame_reference(frame: str) -> str:
    if frame in _FRAME_REF:
        return _FRAME_REF[frame]
    if frame.startswith("graha:"):
        return frame
    raise ValueError(f"unknown frame {frame!r}")


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
                        # exact: the house changes where the body crosses a moving cusp
                        house = cusp_house_at(ctx, body, ctx.birth.jd_ut)
                        a = times_assessment(ctx, cusp_changes(ctx, body))
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
        # partially unsupported: the other frames stand, the reason is explicit (§6.2.5, §7.10)
        return FeatureResult(feature_id=self.id, status=Status.OK, facts=tuple(facts),
                             reason=Reason.UNSUPPORTED_FEATURE if unavailable else None,
                             detail="; ".join(f"{k}: {v}" for k, v in unavailable.items()),
                             provenance={"frames": frames,
                                         "lagna_system": ctx.profile.house_system,
                                         "other_frames_counting": "whole_sign",
                                         **({"unavailable": unavailable} if unavailable else {})})
