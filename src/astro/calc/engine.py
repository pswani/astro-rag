"""Feature registry, dependency resolution and caching (CALC-8, calc-review M2).

A request names a feature and its parameters. The engine expands requirements transitively,
orders them with `graphlib`, runs each once per call and consults the cache port. Failures stay
feature-local: a failed dependency makes its dependents `unknown` (`dependency_unavailable`),
and unrelated features are unaffected (design §6.2.5).
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from graphlib import CycleError, TopologicalSorter
from typing import Any, Protocol

from astro.calc import ENGINE_VERSION
from astro.calc.context import ChartContext
from astro.calc.core.canonical import content_hash
from astro.calc.core.status import CalcError, Reason, Status
from astro.calc.model import FeatureResult


def _freeze(v: Any) -> Any:
    if isinstance(v, (list, tuple)):
        return tuple(_freeze(x) for x in v)
    if isinstance(v, dict):
        return tuple(sorted((k, _freeze(x)) for k, x in v.items()))
    return v


@dataclass(frozen=True)
class FeatureRequest:
    feature_id: str
    params: tuple[tuple[str, Any], ...] = ()

    @classmethod
    def of(cls, feature_id: str, **params: Any) -> FeatureRequest:
        return cls(feature_id, tuple(sorted((k, _freeze(v)) for k, v in params.items())))

    @property
    def param_dict(self) -> dict[str, Any]:
        return dict(self.params)


class Deps(Mapping[FeatureRequest, FeatureResult]):
    def __init__(self, results: dict[FeatureRequest, FeatureResult]) -> None:
        self._r = results

    def __getitem__(self, k: FeatureRequest) -> FeatureResult:
        return self._r[k]

    def __iter__(self):
        return iter(self._r)

    def __len__(self) -> int:
        return len(self._r)

    def get_one(self, feature_id: str) -> FeatureResult:
        matches = [v for k, v in self._r.items() if k.feature_id == feature_id]
        if len(matches) != 1:
            raise KeyError(f"{feature_id}: {len(matches)} results")
        return matches[0]


class Feature(Protocol):
    id: str

    def requires(self, params: dict[str, Any]) -> list[FeatureRequest]: ...
    def compute(self, ctx: ChartContext, deps: Deps, params: dict[str, Any]) -> FeatureResult: ...


class CachePort(Protocol):
    def get(self, key: str) -> FeatureResult | None: ...
    def put(self, key: str, result: FeatureResult) -> None: ...


class InMemoryCache:
    def __init__(self) -> None:
        self.data: dict[str, FeatureResult] = {}

    def get(self, key: str) -> FeatureResult | None:
        return self.data.get(key)

    def put(self, key: str, result: FeatureResult) -> None:
        self.data[key] = result


class Engine:
    def __init__(self, features: Iterable[Feature], cache: CachePort | None = None) -> None:
        self.features: dict[str, Feature] = {}
        for f in features:
            if f.id in self.features:
                raise ValueError(f"duplicate feature {f.id}")
            self.features[f.id] = f
        self.cache = cache

    def cache_key(self, ctx: ChartContext, req: FeatureRequest) -> str:
        return content_hash({
            "chart": ctx.chart_id, "feature": req.feature_id, "params": req.params,
            "engine": ENGINE_VERSION, "profile": ctx.profile.content_hash,
            "ephemeris": ctx.ephemeris.info().files_sha256, "refdata": ctx.refdata.version,
            "method_inputs": ctx.method_inputs,
        })

    def _graph(self, requests: Iterable[FeatureRequest]
               ) -> tuple[dict[FeatureRequest, set], dict[FeatureRequest, FeatureResult]]:
        graph: dict[FeatureRequest, set[FeatureRequest]] = {}
        failed: dict[FeatureRequest, FeatureResult] = {}
        todo = list(requests)
        while todo:
            r = todo.pop()
            if r in graph:
                continue
            feat = self.features.get(r.feature_id)
            if feat is None:
                graph[r] = set()
                continue
            try:
                deps = set(feat.requires(r.param_dict))
            except Exception as e:  # noqa: BLE001 - feature-local, like compute()
                failed[r] = _status(r, Status.FAILED, Reason.TOOL_ERROR,
                                    f"requires: {type(e).__name__}: {e}")
                deps = set()
            graph[r] = deps
            todo.extend(deps)
        return graph, failed

    def run(self, ctx: ChartContext,
            requests: Iterable[FeatureRequest]) -> dict[FeatureRequest, FeatureResult]:
        requests = list(requests)
        graph, failed = self._graph(requests)
        # Break each cycle by failing its members only; their dependents then become
        # `dependency_unavailable` and unrelated features are unaffected.
        while True:
            try:
                order = list(TopologicalSorter(graph).static_order())
                break
            except CycleError as e:
                cycle = e.args[1]
                for r in cycle:
                    failed[r] = _status(r, Status.FAILED, Reason.DEPENDENCY_CYCLE,
                                        " -> ".join(c.feature_id for c in cycle))
                    graph[r] = set()
        results: dict[FeatureRequest, FeatureResult] = {}
        for req in order:
            results[req] = failed.get(req) or self._run_one(ctx, req, graph[req], results)
        return {r: results[r] for r in requests}

    def _run_one(self, ctx: ChartContext, req: FeatureRequest, deps: set[FeatureRequest],
                 done: dict[FeatureRequest, FeatureResult]) -> FeatureResult:
        feat = self.features.get(req.feature_id)
        if feat is None:
            return _status(req, Status.UNSUPPORTED, Reason.UNSUPPORTED_FEATURE,
                           f"no feature {req.feature_id!r}")
        bad = [d for d in deps if done[d].status is not Status.OK]
        if bad:
            names = ", ".join(sorted(f"{d.feature_id}={done[d].status}" for d in bad))
            return _status(req, Status.UNKNOWN, Reason.DEPENDENCY_UNAVAILABLE, names)
        try:
            key = self.cache_key(ctx, req) if self.cache is not None else None
        except (TypeError, ValueError) as e:
            return _status(req, Status.FAILED, Reason.TOOL_ERROR, f"cache key: {e}")
        if key is not None and (hit := self.cache.get(key)) is not None:
            return hit
        try:
            result = feat.compute(ctx, Deps({d: done[d] for d in deps}), req.param_dict)
        except CalcError as e:
            status = Status.UNSUPPORTED if e.reason is not Reason.TOOL_ERROR else Status.FAILED
            result = _status(req, status, e.reason, e.detail)
        except Exception as e:  # noqa: BLE001 - feature-local failure, never a silent fallback
            result = _status(req, Status.FAILED, Reason.TOOL_ERROR, f"{type(e).__name__}: {e}")
        result = result.model_copy(update={
            "params": req.params,
            "provenance": {**result.provenance, "engine": ENGINE_VERSION,
                           "profile": ctx.profile.id,
                           "profile_hash": ctx.profile.content_hash,
                           "ephemeris": ctx.ephemeris.info().files_sha256,
                           "refdata": ctx.refdata.version},
        })
        if key is not None and result.status is Status.OK:
            self.cache.put(key, result)
        return result


def _status(req: FeatureRequest, status: Status, reason: Reason, detail: str) -> FeatureResult:
    return FeatureResult(feature_id=req.feature_id, params=req.params, status=status,
                         reason=reason, detail=detail)
