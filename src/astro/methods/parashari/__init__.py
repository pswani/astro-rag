"""Parashari adapter (design §7.10): the core natal, panchanga, dasha and transit features."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from astro.calc.engine import Feature, FeatureRequest
from astro.calc.registry import default_features


def natal_requests(plan: Mapping[str, Any]) -> list[FeatureRequest]:
    """The baseline requests for a natal reading; a dependency plan narrows them (§11.4)."""
    reqs = [FeatureRequest.of("positions"), FeatureRequest.of("houses"),
            FeatureRequest.of("relations"), FeatureRequest.of("friendship"),
            FeatureRequest.of("condition"), FeatureRequest.of("aspects"),
            FeatureRequest.of("vargas", vargas=tuple(plan.get("vargas", ("D1", "D9", "D10")))),
            FeatureRequest.of("panchanga"), FeatureRequest.of("vimshottari")]
    if "as_of" in plan:
        reqs += [FeatureRequest.of("dasha_active", as_of=plan["as_of"]),
                 FeatureRequest.of("dasha_context", as_of=plan["as_of"])]
    return reqs


class ParashariAdapter:
    method_id = "parashari"

    def feature_set(self) -> list[Feature]:
        return default_features()

    def required_inputs(self, intent: str) -> set[str]:
        return set()

    def features(self, plan: Mapping[str, Any]) -> list[FeatureRequest]:
        return natal_requests(plan)

    def operators(self) -> dict[str, Any]:
        return {}  # predicate operators arrive with the rule engine (design §10.2)
