"""Natural, temporal and compound (panchadha) friendship of the seven grahas (REL-2 subset).

Temporal: a graha in the 2nd, 3rd, 4th, 10th, 11th or 12th sign from another is its temporary
friend, otherwise its temporary enemy. Compound combines both (BPHS ch. 3). Functional roles per
lagna wait for decision 6 (calc-review G-R2).
"""

from __future__ import annotations

from typing import Any

from astro.calc.context import ChartContext
from astro.calc.core.angles import houses_apart
from astro.calc.core.status import Status
from astro.calc.engine import Deps, FeatureRequest
from astro.calc.features.common import assessment_of
from astro.calc.model import FeatureResult, Relation
from astro.calc.refdata import GRAHAS_7, ReferenceData
from astro.calc.sensitivity import Assessment

TEMPORAL_FRIEND_HOUSES = frozenset({2, 3, 4, 10, 11, 12})
COMPOUND = {
    ("friend", "friend"): "great_friend", ("friend", "enemy"): "neutral",
    ("neutral", "friend"): "friend", ("neutral", "enemy"): "enemy",
    ("enemy", "friend"): "neutral", ("enemy", "enemy"): "great_enemy",
}


def grades(ref: ReferenceData, a: str, b: str, sign_a: int,
           sign_b: int) -> tuple[str | None, str, str | None]:
    """(natural, temporal, compound) friendship of graha `a` towards graha `b` (BPHS ch. 3).
    Natural is None when not modelled (the nodes); compound is then None too."""
    natural = ref.natural_friendship(a, b)
    temporal = "friend" if houses_apart(sign_a, sign_b) in TEMPORAL_FRIEND_HOUSES else "enemy"
    return natural, temporal, None if natural is None else COMPOUND[(natural, temporal)]


class Friendship:
    id = "friendship"

    def requires(self, params: dict[str, Any]) -> list[FeatureRequest]:
        return [FeatureRequest.of("positions")]

    def compute(self, ctx: ChartContext, deps: Deps, params: dict[str, Any]) -> FeatureResult:
        pos = deps.get_one("positions")
        ref = ctx.refdata
        rels: list[Relation] = []
        for ga in GRAHAS_7:
            for gb in GRAHAS_7:
                if ga == gb:
                    continue
                a, b = f"graha:{ga}", f"graha:{gb}"
                fa, fb = pos.fact("sign", a), pos.fact("sign", b)
                natural, temporal, compound = grades(ref, a, b, ref.rashi_index(fa.value),
                                                     ref.rashi_index(fb.value))
                sens = Assessment.combine(assessment_of(fa), assessment_of(fb)).sensitivity
                for system, value, s in (("natural", natural, "stable"),
                                         ("temporal", temporal, sens),
                                         ("compound", compound, sens)):
                    rels.append(Relation(
                        id=f"{ctx.chart_id}/friendship/{system}/{a}/{b}", kind="friendship",
                        source=a, target=b, system=system, value=value,
                        profile_id=ctx.profile.id, sensitivity=s))
        return FeatureResult(feature_id=self.id, status=Status.OK, relations=tuple(rels))
