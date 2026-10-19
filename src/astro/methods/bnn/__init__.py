"""BNN adapter (SCH-BNN-1, SCH-BNN-2, TRN-6; design §7.10)."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from astro.calc.engine import Feature, FeatureRequest
from astro.calc.registry import default_features
from astro.methods.bnn.features import features as bnn_features
from astro.methods.parashari import natal_requests


class BnnAdapter:
    method_id = "bnn"

    def feature_set(self) -> list[Feature]:
        return [*default_features(), *bnn_features()]

    def required_inputs(self, intent: str) -> set[str]:
        return set()  # native_gender is optional: asked for only when a rule needs it (INP-8)

    def features(self, plan: Mapping[str, Any]) -> list[FeatureRequest]:
        reqs = [*natal_requests(plan), FeatureRequest.of("bnn_relations"),
                FeatureRequest.of("bnn_karakas")]
        if "window" in plan:
            reqs.append(FeatureRequest.of("bnn_triggers", **plan["window"]))
        return reqs

    def operators(self) -> dict[str, Any]:
        return {}
