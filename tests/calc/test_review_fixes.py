"""Regression tests for the B7.4 review findings."""

import shutil
from dataclasses import dataclass
from datetime import date, time

import pytest
import swisseph as swe
from pydantic import ValidationError

from astro.calc.context import ChartContext, NormalizedBirth
from astro.calc.core.status import Reason, Status
from astro.calc.core.timescale import jd_from_civil
from astro.calc.engine import Engine
from astro.calc.engine import FeatureRequest as R
from astro.calc.model import FeatureResult
from astro.calc.registry import default_engine
from astro.normalize.birth import BirthInput

from .helpers import EPHE, ephemeris, profile, refdata

PUNE_JD = jd_from_civil(1985, 3, 14, 1.2)


def ctx(prof=None):
    return ChartContext("chart:r", NormalizedBirth(PUNE_JD, 18.52, 73.85,
                                                   uncertainty_minutes=5),
                        prof or profile(), ephemeris(), refdata())


def test_event_ids_are_unique_with_all_kinds():
    (ev,) = default_engine().run(ctx(), [R.of(
        "transit_events", bodies=("moon",), kinds=("sign", "nakshatra", "pada", "station",
                                                   "conjunction"),
        start="2026-01-01T00:00:00+00:00", end="2026-03-01T00:00:00+00:00")]).values()
    ids = [e.id for e in ev.events]
    assert len(ids) == len(set(ids))
    assert any(".nakshatra/" in i for i in ids) and any(".pada." in i for i in ids)


@dataclass
class Stub:
    id: str
    needs: tuple = ()
    bad_requires: bool = False

    def requires(self, params):
        if self.bad_requires:
            raise ValueError("bad params")
        return [R.of(n) for n in self.needs]

    def compute(self, ctx, deps, params):
        return FeatureResult(feature_id=self.id, status=Status.OK)


def test_cycle_does_not_fail_unrelated_features():
    eng = Engine([Stub("a", ("b",)), Stub("b", ("a",)), Stub("c", ("a",)), Stub("free")])
    out = eng.run(ctx(), [R.of("a"), R.of("c"), R.of("free")])
    assert out[R.of("a")].reason is Reason.DEPENDENCY_CYCLE
    assert out[R.of("c")].reason in (Reason.DEPENDENCY_UNAVAILABLE, Reason.DEPENDENCY_CYCLE)
    assert out[R.of("free")].status is Status.OK


def test_errors_outside_compute_stay_feature_local():
    from astro.calc.engine import InMemoryCache
    eng = Engine([Stub("bad", bad_requires=True), Stub("free")], InMemoryCache())
    out = eng.run(ctx(), [R.of("bad"), R.of("free"), R.of("free", when=date(2026, 1, 1))])
    assert out[R.of("bad")].status is Status.FAILED
    assert out[R.of("free")].status is Status.OK
    assert out[R.of("free", when=date(2026, 1, 1))].reason is Reason.TOOL_ERROR  # cache key


def test_aware_local_time_is_rejected():
    with pytest.raises(ValidationError):
        BirthInput(year=1985, month=3, day=14, local_time=time.fromisoformat("06:42+05:30"),
                   latitude=18.5, longitude=73.8, timezone="Asia/Kolkata")


def test_transit_node_retrograde_follows_profile():
    p = profile().model_copy(update={"nodes": profile().nodes.model_copy(
        update={"model": "true", "retrograde": "always"})})
    out = default_engine().run(ctx(p), [R.of("positions"), R.of(
        "transit_positions", as_of="2026-10-19T00:00:00+00:00")])
    tr = out[R.of("transit_positions", as_of="2026-10-19T00:00:00+00:00")]
    assert tr.fact("retrograde", "graha:rahu", frame="transit").value is True
    assert out[R.of("positions")].fact("retrograde", "graha:rahu").value is True


def test_dasha_active_input_errors_are_missing_input():
    out = default_engine().run(ctx(), [R.of("dasha_active", as_of="2026-10-19T00:00"),
                                       R.of("dasha_active")])
    for r in out.values():
        assert r.reason is Reason.MISSING_INPUT, r.detail


def test_dasha_active_uses_profile_levels_and_unknown_sandhi():
    p = profile().model_copy(update={"dasha": profile().dasha.model_copy(
        update={"levels": ("MD", "AD")})})
    (act,) = default_engine().run(ctx(p), [R.of(
        "dasha_active", as_of="2026-10-19T00:00:00+00:00")]).values()
    assert [x.level for x in act.periods] == ["MD", "AD"]
    (shallow,) = default_engine().run(ctx(), [R.of(
        "dasha_active", depth=1, as_of="2026-10-19T00:00:00+00:00")]).values()
    ad = shallow.fact("dasha_sandhi", "dasha:vimshottari:AD")
    assert ad.value is None and ad.sensitivity == "unknown"
    (bad_depth,) = default_engine().run(ctx(), [R.of("vimshottari", depth="x")]).values()
    assert bad_depth.reason is Reason.UNSUPPORTED_FEATURE


@pytest.mark.parametrize("copy_files", [False, True])
def test_external_ephemeris_path_change_is_detected(tmp_path, copy_files):
    """Other code (e.g. PyJHora) may change the global path; files in use must stay ours."""
    e, p = ephemeris(), profile()
    expected = e.body("saturn", PUNE_JD, p)
    if copy_files:
        for f in EPHE.iterdir():
            shutil.copy(f, tmp_path / f.name)
    swe.set_ephe_path(str(tmp_path))
    assert e.body("saturn", PUNE_JD + 1e-6, p).longitude == pytest.approx(
        expected.longitude, abs=1e-6)
    used = swe.get_current_file_data(0)[0]
    assert str(EPHE.resolve()) in used
