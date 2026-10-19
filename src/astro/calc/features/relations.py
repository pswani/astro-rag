"""Lordships, occupants, parivartana and dispositor chains (REL-1 subset).

Aspects and conjunctions wait for decision 4 (calc-review G-R1). Rahu and Ketu own no sign here
(their co-lordships are disputed), so they never start a parivartana, but they do have
dispositors.
"""

from __future__ import annotations

from typing import Any

from astro.calc.context import ChartContext
from astro.calc.core.angles import houses_apart
from astro.calc.core.status import Status
from astro.calc.engine import Deps, FeatureRequest
from astro.calc.ephemeris.port import BODIES
from astro.calc.features.common import (
    assessment_of,
    cusp_changes,
    cusp_house_at,
    piecewise,
    sign_at,
    sign_piecewise,
    subject,
)
from astro.calc.features.houses import DEFAULT_FRAMES as HOUSE_DEFAULT_FRAMES
from astro.calc.features.houses import frame_reference
from astro.calc.model import ChartFact, FeatureResult, Relation
from astro.calc.refdata import GRAHAS_7
from astro.calc.sensitivity import Assessment

DEFAULT_FRAMES = ("lagna", "chandra")


class Relations:
    id = "relations"

    def requires(self, params: dict[str, Any]) -> list[FeatureRequest]:
        frames = tuple(params.get("frames", DEFAULT_FRAMES))
        if set(frames) <= set(HOUSE_DEFAULT_FRAMES):  # share the default houses request
            return [FeatureRequest.of("positions"), FeatureRequest.of("houses")]
        return [FeatureRequest.of("positions"), FeatureRequest.of("houses", frames=frames)]

    def compute(self, ctx: ChartContext, deps: Deps, params: dict[str, Any]) -> FeatureResult:
        pos, houses = deps.get_one("positions"), deps.get_one("houses")
        frames = tuple(params.get("frames", DEFAULT_FRAMES))
        ref = ctx.refdata
        facts: list[ChartFact] = []
        rels: list[Relation] = []

        sign = {subject(b): ref.rashi_index(pos.fact("sign", subject(b)).value) for b in BODIES}
        sign_a = {s: assessment_of(pos.fact("sign", s)) for s in sign}

        # lordships and occupants per frame
        for frame in frames:
            # an unknown placement (time unknown, cusps undefined) makes occupants unknown
            placements_known = all(f.value is not None for f in houses.facts
                                   if f.kind == "house" and f.frame == frame)
            for n in range(1, 13):
                hs = houses.fact("house_sign", f"bhava:{n}", frame=frame)
                if hs.value is None:
                    facts.append(ctx.unknown("lord_of", f"bhava:{n}", frame=frame))
                else:
                    facts.append(ctx.fact("lord_of", f"bhava:{n}",
                                          ref.sign_lord(ref.rashi_index(hs.value)), frame=frame,
                                          sensitivity=hs.sensitivity, margins=hs.margin_minutes))
                if hs.value is None or not placements_known:
                    facts.append(ctx.unknown("occupants", f"bhava:{n}", frame=frame))
                    continue
                in_house = []
                for b in BODIES:
                    try:
                        h = houses.fact("house", subject(b), frame=frame).value
                    except KeyError:  # the frame's own reference graha is in house 1
                        h = 1
                    if h == n:
                        in_house.append(subject(b))
                if frame == "lagna" and ctx.profile.house_system != "whole_sign":
                    # exact over every body's cusp crossings (houses can be narrow)
                    def cusp_occupants(t: float, n: int = n) -> tuple[str, ...]:
                        return tuple(subject(x) for x in BODIES
                                     if cusp_house_at(ctx, x, t) == n)

                    a = piecewise(ctx, [c for x in BODIES for c in cusp_changes(ctx, x)],
                                  cusp_occupants)
                else:  # sign-based: exact over the sign changes of the reference and bodies
                    ref_body = frame_reference(frame).split(":")[-1]

                    def occupants_at(t: float, n: int = n, ref_body: str = ref_body):
                        base = sign_at(ctx, ref_body, t)
                        return tuple(subject(x) for x in BODIES
                                     if houses_apart(base, sign_at(ctx, x, t)) == n)

                    a = sign_piecewise(ctx, [ref_body, *BODIES], occupants_at)
                facts.append(ctx.fact("occupants", f"bhava:{n}", tuple(in_house), frame=frame,
                                      sensitivity=a.sensitivity, margins=a.margins))

        # parivartana (sign exchange) between the seven sign-owning grahas
        for i, ga in enumerate(GRAHAS_7):
            for gb in GRAHAS_7[i + 1:]:
                sa, sb = f"graha:{ga}", f"graha:{gb}"
                if ref.sign_lord(sign[sa]) == sb and ref.sign_lord(sign[sb]) == sa:
                    a = Assessment.combine(sign_a[sa], sign_a[sb])
                    rels.append(Relation(
                        id=f"{ctx.chart_id}/parivartana/{sa}/{sb}", kind="parivartana",
                        source=sa, target=sb, system="parashari_sign", direction="mutual",
                        profile_id=ctx.profile.id, sensitivity=a.sensitivity))

        # dispositor chains
        for b in BODIES:
            s = subject(b)
            chain: list[str] = []
            seen = {s}
            cur = s
            terminal = "cycle"
            while True:
                nxt = ref.sign_lord(sign[cur])
                if nxt == cur:
                    terminal = "own_sign"
                    break
                chain.append(nxt)
                if nxt in seen:
                    break
                seen.add(nxt)
                cur = nxt
            a = Assessment.combine(sign_a[s], *(sign_a[c] for c in chain))
            facts.append(ctx.fact("dispositor_chain", s, tuple(chain),
                                  sensitivity=a.sensitivity, margins=a.margins))
            facts.append(ctx.fact("dispositor_terminal", s, terminal,
                                  sensitivity=a.sensitivity, margins=a.margins))
            first = ref.sign_lord(sign[s])
            if first != s:
                rels.append(Relation(id=f"{ctx.chart_id}/dispositor/{s}", kind="dispositor",
                                     source=s, target=first, system="parashari_sign",
                                     profile_id=ctx.profile.id,
                                     sensitivity=sign_a[s].sensitivity))
        return FeatureResult(feature_id=self.id, status=Status.OK, facts=tuple(facts),
                             relations=tuple(rels))
