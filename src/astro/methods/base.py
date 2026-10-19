"""Method adapters (design §7.10, NFR-9).

A method is a profile (`profiles/method/<id>.yaml`) plus an adapter that contributes features
and, later, namespaced predicate operators. Adding a method adds a profile, an adapter, ontology
entries, rule cards, topic maps and eval cases, with no change to core code paths. The built-in
adapters are registered directly; installed packages can add more through the `astro.methods`
entry-point group, and a plugin that fails to load is reported without affecting the others.

Status gate (design §7.10): only `active` methods produce readings (rule evaluation, evidence
bundles). Calculations, which do not depend on reviewed rules, may use a `draft` method's
features and default profile; a `withdrawn` method is never used.
"""

from __future__ import annotations

from collections.abc import Mapping
from functools import cache
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
        from astro.methods.bnn import BnnAdapter
        from astro.methods.parashari import ParashariAdapter

        self.adapters: dict[str, MethodAdapter] = {
            a.method_id: a for a in (ParashariAdapter(), BnnAdapter())}
        self.broken: dict[str, str] = {}
        builtins = set(self.adapters)
        for ep in entry_points(group="astro.methods"):
            if ep.name in builtins:
                continue  # built-ins are registered above, whatever the install metadata says
            try:
                adapter = ep.load()()
                method_id = adapter.method_id
                if not isinstance(method_id, str):
                    raise TypeError("method_id must be a string")
            except Exception as e:  # noqa: BLE001 - one bad plugin must not block the others
                self.broken[ep.name] = f"{type(e).__name__}: {e}"
                continue
            if method_id in self.adapters:  # a plugin never replaces a built-in or another
                self.broken[ep.name] = f"method {method_id!r} is already registered"
                continue
            self.adapters[method_id] = adapter

    def get(self, method_id: str, *, purpose: Literal["reading", "calculation"] = "reading"
            ) -> tuple[MethodProfile, MethodAdapter]:
        """The method's profile and adapter, gated by status for the purpose (module doc).
        Anything not allowed is `unsupported_method`, never another school."""
        prof = self.profiles.get(method_id)
        adapter = self.adapters.get(method_id)
        if prof is None or adapter is None:
            detail = self.broken.get(method_id, "not installed")
            raise CalcError(Reason.UNSUPPORTED_METHOD, f"no method {method_id!r} ({detail})")
        allowed = {"reading": ("active",), "calculation": ("active", "draft")}[purpose]
        if prof.status not in allowed:
            raise CalcError(Reason.UNSUPPORTED_METHOD,
                            f"method {method_id} is {prof.status}: not available for {purpose}")
        return prof, adapter


@cache
def _load_registry(profile_dir: Path, stamp: tuple) -> MethodRegistry:
    return MethodRegistry(profile_dir)


def load_registry(profile_dir: Path) -> MethodRegistry:
    """Method profiles and adapters, discovered once per version of the profile files.
    Plugins installed while the process runs need `_load_registry.cache_clear()`."""
    d = Path(profile_dir).resolve()
    stamp = tuple(sorted((p.name, p.stat().st_mtime_ns) for p in d.glob("*.yaml")))
    return _load_registry(d, stamp)
