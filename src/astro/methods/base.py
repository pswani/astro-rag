"""Method adapters (design §7.10, NFR-9).

A method is a profile (`profiles/method/<id>.yaml`) plus an adapter that contributes features
and, later, namespaced predicate operators. Adding a method adds a profile, an adapter, ontology
entries, rule cards, topic maps and eval cases, with no change to core code paths. Adapters are
discovered through the `astro.methods` entry-point group, so an installed package can add one.
"""

from __future__ import annotations

from collections.abc import Mapping
from importlib.metadata import entry_points
from pathlib import Path
from typing import Any, Literal, Protocol

from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator
from ruamel.yaml import YAML

from astro.calc.core.status import CalcError, Reason
from astro.calc.engine import Feature, FeatureRequest


class MethodProfile(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    id: str = Field(pattern=r"^[a-z][a-z0-9_]*$")
    school: str
    lineage: str
    description: str
    status: Literal["draft", "active", "withdrawn"]
    calc_profiles: tuple[str, ...]
    default_calc_profile: str
    supported_topics: tuple[str, ...] = ()
    rule_families: tuple[str, ...] = ()
    core_sources: tuple[str, ...] = ()
    optional_inputs: tuple[str, ...] = ()
    known_gaps: tuple[str, ...] = ()

    @model_validator(mode="after")
    def _default_listed(self) -> MethodProfile:
        if self.default_calc_profile not in self.calc_profiles:
            raise ValueError("default_calc_profile must be one of calc_profiles")
        return self


class MethodAdapter(Protocol):
    method_id: str

    def feature_set(self) -> list[Feature]: ...
    def required_inputs(self, intent: str) -> set[str]: ...
    def features(self, plan: Mapping[str, Any]) -> list[FeatureRequest]: ...
    def operators(self) -> dict[str, Any]: ...


def load_method_profile(path: Path) -> MethodProfile:
    try:
        return MethodProfile.model_validate(YAML(typ="safe").load(Path(path).read_text()))
    except ValidationError as e:
        raise CalcError(Reason.UNSUPPORTED_PROFILE, f"{path}: {e}") from e


class MethodRegistry:
    def __init__(self, profile_dir: Path) -> None:
        self.profiles = {p.stem: load_method_profile(p)
                         for p in sorted(Path(profile_dir).glob("*.yaml"))}
        for pid, prof in self.profiles.items():
            if prof.id != pid:
                raise CalcError(Reason.UNSUPPORTED_PROFILE, f"{pid}.yaml declares id {prof.id}")
        self.adapters: dict[str, MethodAdapter] = {}
        for ep in entry_points(group="astro.methods"):
            adapter = ep.load()()
            self.adapters[adapter.method_id] = adapter

    def get(self, method_id: str, *, allow_draft: bool = False
            ) -> tuple[MethodProfile, MethodAdapter]:
        """The method's profile and adapter. Only `active` methods run unless `allow_draft`
        (design §7.10); anything else is `unsupported_method`, never another school."""
        prof = self.profiles.get(method_id)
        adapter = self.adapters.get(method_id)
        if prof is None or adapter is None:
            raise CalcError(Reason.UNSUPPORTED_METHOD, f"no method {method_id!r}")
        if prof.status == "withdrawn" or (prof.status == "draft" and not allow_draft):
            raise CalcError(Reason.UNSUPPORTED_METHOD, f"method {method_id} is {prof.status}")
        return prof, adapter
