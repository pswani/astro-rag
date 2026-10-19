"""BNN calculations (SCH-BNN-1, SCH-BNN-2, TRN-6; design §7.10).

- Links: for each graha, the grahas in the 1st (same sign), 5th and 9th (trines), 2nd, 12th and
  7th signs from it; exchanges. Counting is inclusive and by sign.
- Retrograde variant (`retro_in_previous_sign`): a retrograde planet is also treated as being in
  the previous sign. Rahu and Ketu are excluded from the variant because their backward motion
  is their natural motion; this is recorded in provenance so the reviewer can overturn it.
- Karaka roles come from the BNN scheme only and are kept apart from Parashari karakatva.
- Which relations a rule's `bnn.linked` counts is a lineage decision for the rule cards, not
  for this geometry (calc-review G-B1).
"""

from __future__ import annotations

from typing import Any

from astro.calc.context import ChartContext
from astro.calc.core.angles import SIGN_SPAN, houses_apart
from astro.calc.core.status import Status
from astro.calc.core.timescale import utc_from_jd
from astro.calc.engine import Deps, FeatureRequest
from astro.calc.ephemeris.port import BODIES
from astro.calc.model import ChartFact, FeatureResult, Relation, TransitEvent
from astro.calc.sensitivity import Assessment
from astro.calc.solver import crossings
from astro.calc.transits.common import check_window, window

LINK_OFFSETS = {1: "conjunction", 5: "trine", 9: "trine", 2: "second", 12: "twelfth",
                7: "seventh"}
TRIGGER_BODIES = ("jupiter", "saturn", "rahu", "ketu")
NODES = ("rahu", "ketu")


def _signs(ctx: ChartContext, pos, body: str) -> list[tuple[int, str]]:
    """(sign, via) pairs where a body counts: its own sign, plus the previous sign if the
    retrograde variant applies."""
    ref = ctx.refdata
    s = ref.rashi_index(pos.fact("sign", f"graha:{body}").value)
    out = [(s, "sign")]
    retro = pos.fact("retrograde", f"graha:{body}").value
    if ctx.profile.retro_in_previous_sign and retro and body not in NODES:
        out.append(((s - 1) % 12, "retro_previous_sign"))
    return out


class BnnRelations:
    id = "bnn_relations"

    def requires(self, params: dict[str, Any]) -> list[FeatureRequest]:
        return [FeatureRequest.of("positions")]

    def compute(self, ctx: ChartContext, deps: Deps, params: dict[str, Any]) -> FeatureResult:
        pos = deps.get_one("positions")
        ref = ctx.refdata
        rels: list[Relation] = []
        seen: set[tuple[str, str, int]] = set()
        for a in BODIES:
            for b in BODIES:
                if a == b:
                    continue
                sa, sb = f"graha:{a}", f"graha:{b}"
                sens = Assessment.combine(
                    Assessment(pos.fact("sign", sa).sensitivity, (None, None)),
                    Assessment(pos.fact("sign", sb).sensitivity, (None, None))).sensitivity
                for sign_a, via_a in _signs(ctx, pos, a):
                    for sign_b, via_b in _signs(ctx, pos, b):
                        off = houses_apart(sign_a, sign_b)
                        if off not in LINK_OFFSETS or (sa, sb, off) in seen:
                            continue
                        seen.add((sa, sb, off))
                        via = via_a if via_a != "sign" else via_b
                        rels.append(Relation(
                            id=f"{ctx.chart_id}/bnn_link/{sa}/{sb}/{off}", kind="bnn_link",
                            source=sa, target=sb, system="bnn", value=off,
                            profile_id=ctx.profile.id, sensitivity=sens,
                            provenance={"link": LINK_OFFSETS[off], "via": via}))
        signs = {g: ref.rashi_index(pos.fact("sign", f"graha:{g}").value) for g in BODIES}
        for i, a in enumerate(BODIES):
            for b in BODIES[i + 1:]:
                if (ref.sign_lord(signs[a]) == f"graha:{b}"
                        and ref.sign_lord(signs[b]) == f"graha:{a}"):
                    rels.append(Relation(
                        id=f"{ctx.chart_id}/parivartana/bnn/graha:{a}/graha:{b}",
                        kind="parivartana", source=f"graha:{a}", target=f"graha:{b}",
                        system="bnn", direction="mutual", profile_id=ctx.profile.id))
        return FeatureResult(feature_id=self.id, status=Status.OK, relations=tuple(rels),
                             provenance={"retro_in_previous_sign":
                                         ctx.profile.retro_in_previous_sign,
                                         "nodes_excluded_from_retro_variant": True})


class BnnKarakas:
    id = "bnn_karakas"

    def requires(self, params: dict[str, Any]) -> list[FeatureRequest]:
        return []

    def compute(self, ctx: ChartContext, deps: Deps, params: dict[str, Any]) -> FeatureResult:
        ref = ctx.refdata
        facts: list[ChartFact] = [ctx.fact("karaka_role", f"graha:{g}",
                                           ref.karaka_roles("bnn", f"graha:{g}"), frame="bnn")
                                  for g in BODIES]
        gender = ctx.method_inputs.get("native_gender")
        native = ref.native_karaka("bnn", gender) if gender else None
        if native is None:
            # INP-8: asked for only as an explicit, optional method input
            facts.append(ctx.unknown("native_karaka", "native", frame="bnn"))
        else:
            facts.append(ctx.fact("native_karaka", "native", native, frame="bnn"))
        return FeatureResult(feature_id=self.id, status=Status.OK, facts=tuple(facts),
                             provenance={"native_gender_given": gender is not None})


class BnnTriggers:
    """Jupiter, Saturn and the nodes entering the sign of, or a trine to, a natal planet."""

    id = "bnn_triggers"

    def requires(self, params: dict[str, Any]) -> list[FeatureRequest]:
        return [FeatureRequest.of("positions")]

    def compute(self, ctx: ChartContext, deps: Deps, params: dict[str, Any]) -> FeatureResult:
        t0, t1 = window(params)
        check_window(t0, t1, TRIGGER_BODIES)
        pos = deps.get_one("positions")
        ref = ctx.refdata
        natal = {f"graha:{g}": ref.rashi_index(pos.fact("sign", f"graha:{g}").value)
                 for g in BODIES}
        events: list[TransitEvent] = []
        for body in TRIGGER_BODIES:
            speed = ctx.speed_fn(body) if ctx.needs_speed(body) else None
            for c in crossings(ctx.lon_fn(body), t0, t1, step=ctx.step_days(body), speed=speed,
                               width=SIGN_SPAN):
                for planet, s in natal.items():
                    off = houses_apart(s, c.index)
                    if off not in (1, 5, 9):
                        continue
                    when = utc_from_jd(c.jd)
                    events.append(TransitEvent(
                        id=f"{ctx.chart_id}/bnn_trigger/{body}/{planet}/{when.isoformat()}",
                        kind="ingress", body=f"graha:{body}", target=planet, start_utc=when,
                        motion="direct" if c.direction > 0 else "retrograde",
                        detail={"trigger": "bnn", "entered": ref.rashi_id(c.index),
                                "relation": "conjunction" if off == 1 else "trine",
                                "offset": off},
                        profile_id=ctx.profile.id))
        events.sort(key=lambda e: (e.start_utc, e.body, e.target or ""))
        return FeatureResult(feature_id=self.id, status=Status.OK, events=tuple(events))


def features() -> list:
    return [BnnRelations(), BnnKarakas(), BnnTriggers()]
