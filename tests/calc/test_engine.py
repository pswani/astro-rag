from dataclasses import dataclass

import pytest

from astro.calc.context import ChartContext, NormalizedBirth
from astro.calc.core.status import CalcError, Reason, Status
from astro.calc.engine import Engine, FeatureRequest, InMemoryCache
from astro.calc.model import FeatureResult

from .helpers import ephemeris, profile, refdata


def ctx():
    return ChartContext("chart:test", NormalizedBirth(2451545.0, 18.5, 73.8), profile(),
                        ephemeris(), refdata())


@dataclass
class Stub:
    id: str
    needs: tuple = ()
    error: Exception | None = None
    calls: int = 0

    def requires(self, params):
        return [FeatureRequest.of(n) for n in self.needs]

    def compute(self, ctx, deps, params):
        self.calls += 1
        if self.error:
            raise self.error
        return FeatureResult(feature_id=self.id, status=Status.OK,
                             provenance={"deps": sorted(d.feature_id for d in deps)})


def test_dependency_order_and_memo():
    a, b, c = Stub("a"), Stub("b", ("a",)), Stub("c", ("a", "b"))
    eng = Engine([a, b, c])
    out = eng.run(ctx(), [FeatureRequest.of("c"), FeatureRequest.of("b")])
    assert out[FeatureRequest.of("c")].provenance["deps"] == ["a", "b"]
    assert a.calls == 1 and b.calls == 1  # shared dependency computed once
    assert out[FeatureRequest.of("c")].provenance["profile"] == "parashari_v1"


def test_cycle_is_reported():
    eng = Engine([Stub("a", ("b",)), Stub("b", ("a",))])
    out = eng.run(ctx(), [FeatureRequest.of("a")])
    assert out[FeatureRequest.of("a")].reason is Reason.DEPENDENCY_CYCLE


def test_failure_stays_local_and_propagates_as_unknown():
    eng = Engine([Stub("bad", error=CalcError(Reason.OUT_OF_RANGE, "x")), Stub("dep", ("bad",)),
                  Stub("crash", error=ZeroDivisionError("boom")), Stub("fine")])
    out = eng.run(ctx(), [FeatureRequest.of(n) for n in ("dep", "crash", "fine")])
    bad = FeatureRequest.of("bad")
    res = eng.run(ctx(), [bad])[bad]
    assert res.status is Status.UNSUPPORTED and res.reason is Reason.OUT_OF_RANGE
    assert out[FeatureRequest.of("dep")].status is Status.UNKNOWN
    assert out[FeatureRequest.of("dep")].reason is Reason.DEPENDENCY_UNAVAILABLE
    assert out[FeatureRequest.of("crash")].status is Status.FAILED
    assert out[FeatureRequest.of("crash")].reason is Reason.TOOL_ERROR
    assert out[FeatureRequest.of("fine")].status is Status.OK


def test_unknown_feature():
    out = Engine([]).run(ctx(), [FeatureRequest.of("nope")])
    assert out[FeatureRequest.of("nope")].reason is Reason.UNSUPPORTED_FEATURE


def test_cache_hits_and_key_depends_on_profile_and_params():
    a = Stub("a")
    cache = InMemoryCache()
    eng = Engine([a], cache)
    eng.run(ctx(), [FeatureRequest.of("a")])
    eng.run(ctx(), [FeatureRequest.of("a")])
    assert a.calls == 1
    c2 = ctx()
    c2.profile = profile("bnn_v1")
    assert eng.cache_key(ctx(), FeatureRequest.of("a")) != eng.cache_key(c2,
                                                                         FeatureRequest.of("a"))
    assert eng.cache_key(ctx(), FeatureRequest.of("a", x=1)) != eng.cache_key(
        ctx(), FeatureRequest.of("a", x=2))


def test_request_params_are_canonical():
    assert FeatureRequest.of("v", vargas=["D9", "D10"], depth=2) == FeatureRequest.of(
        "v", depth=2, vargas=("D9", "D10"))
    with pytest.raises(ValueError):
        Engine([Stub("a"), Stub("a")])
