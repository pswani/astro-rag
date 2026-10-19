"""CALC-9: the same inputs and profile give byte-identical outputs, across runs and processes."""

import subprocess
import sys
from pathlib import Path

from astro.calc.context import ChartContext, NormalizedBirth
from astro.calc.core.canonical import canonical_json, content_hash
from astro.calc.core.timescale import jd_from_civil
from astro.calc.engine import FeatureRequest as R
from astro.calc.engine import InMemoryCache
from astro.calc.registry import default_engine
from astro.methods.bnn.features import features as bnn_features

from .helpers import ephemeris, profile, refdata

W = {"start": "2026-01-01T00:00:00+00:00", "end": "2027-01-01T00:00:00+00:00"}
REQUESTS = [R.of("positions"), R.of("houses"), R.of("relations"), R.of("friendship"),
            R.of("vargas"), R.of("panchanga"), R.of("vimshottari"),
            R.of("dasha_active", as_of="2026-10-19T00:00:00+00:00"),
            R.of("transit_positions", as_of="2026-10-19T00:00:00+00:00"),
            R.of("transit_events", bodies=("saturn", "jupiter"), **W),
            R.of("transit_states", **W), R.of("eclipses", **W), R.of("bnn_relations"),
            R.of("bnn_karakas"), R.of("bnn_triggers", **W)]


def full_run_hash(cache=None) -> str:
    c = ChartContext("chart:det", NormalizedBirth(jd_from_civil(1985, 3, 14, 1.2), 18.52, 73.85,
                                                  uncertainty_minutes=5),
                     profile("bnn_v1"), ephemeris(), refdata(), {"native_gender": "male"})
    out = default_engine(cache, extra=bnn_features()).run(c, REQUESTS)
    assert all(r.status.value == "ok" for r in out.values()), {
        k.feature_id: (v.status, v.detail) for k, v in out.items() if v.status.value != "ok"}
    return content_hash([out[r] for r in REQUESTS])


def test_rerun_is_byte_identical_and_cache_is_transparent():
    a = full_run_hash()
    b = full_run_hash()
    cache = InMemoryCache()
    c1 = full_run_hash(cache)
    c2 = full_run_hash(cache)  # served from cache
    assert a == b == c1 == c2


def test_identical_in_a_fresh_process():
    here = full_run_hash()
    root = Path(__file__).resolve().parents[2]
    code = ("from tests.calc.test_determinism import full_run_hash; print(full_run_hash())")
    out = subprocess.run([sys.executable, "-c", code], cwd=root, capture_output=True, text=True,
                         check=True)
    assert out.stdout.strip() == here


def test_canonical_bytes_are_stable_for_a_result():
    c = ChartContext("chart:det", NormalizedBirth(2451545.0, 0.0, 0.0), profile(), ephemeris(),
                     refdata())
    (r,) = default_engine().run(c, [R.of("positions")]).values()
    assert canonical_json(r) == canonical_json(r.model_copy())
