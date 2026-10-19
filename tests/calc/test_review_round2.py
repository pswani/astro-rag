"""Regression tests for the D11 review findings (round 1)."""

from types import SimpleNamespace

import pytest

from astro.calc.context import ChartContext, NormalizedBirth
from astro.calc.core.timescale import jd_from_civil
from astro.calc.engine import FeatureRequest as R
from astro.calc.registry import default_engine
from astro.methods import base as method_base
from astro.methods.base import MethodRegistry

from .fake_ephemeris import FakeEphemeris
from .helpers import ROOT, ephemeris, profile, refdata

PUNE_JD = jd_from_civil(1985, 3, 14, 1.2)
T0 = 2451545.0


def ctx(eph=None, prof=None, u=0.0, jd=T0, lat=18.52, lon=73.85):
    return ChartContext("chart:r2", NormalizedBirth(jd, lat, lon, uncertainty_minutes=u),
                        prof or profile(), eph or ephemeris(), refdata())


def run(c, *reqs):
    out = default_engine().run(c, list(reqs))
    return [out[r] for r in reqs]


def test_undefined_cusps_make_occupants_unknown():
    p = profile().model_copy(update={"house_system": "placidus"})
    (rel,) = run(ctx(prof=p, jd=PUNE_JD, lat=70.0, lon=19.0), R.of("relations"))
    occ = rel.fact("occupants", "bhava:1", frame="lagna")
    assert occ.value is None and occ.sensitivity == "unknown"
    assert rel.fact("lord_of", "bhava:1", frame="lagna").value is not None  # sign-based
    assert rel.fact("occupants", "bhava:1", frame="chandra").value is not None


def test_a_planet_losing_any_war_is_a_loser():
    eph = FakeEphemeris({"mars": lambda t: 50.0, "mercury": lambda t: 50.5,
                         "venus": lambda t: 51.0})
    p = profile().model_copy(update={"graha_yuddha": profile().graha_yuddha.model_copy(
        update={"winner": "lesser_longitude"})})
    (c,) = run(ctx(eph=eph, prof=p), R.of("condition"))
    assert c.fact("graha_yuddha", "graha:mars").value == "winner"
    assert c.fact("graha_yuddha", "graha:mercury").value == "loser"  # beat Venus, lost to Mars
    assert c.fact("graha_yuddha", "graha:venus").value == "loser"
    assert len([r for r in c.relations if r.kind == "graha_yuddha"]) == 3


def test_lesser_longitude_across_zero_aries():
    eph = FakeEphemeris({"mars": lambda t: 359.6, "venus": lambda t: 0.3})
    p = profile().model_copy(update={"graha_yuddha": profile().graha_yuddha.model_copy(
        update={"winner": "lesser_longitude"})})
    (c,) = run(ctx(eph=eph, prof=p), R.of("condition"))
    war = next(r for r in c.relations if r.kind == "graha_yuddha")
    assert (war.source, war.target) == ("graha:mars", "graha:venus")  # Mars is behind


def test_orb_conjunction_sensitivity_uses_the_orb():
    # Moon 8.1° behind Saturn, closing at ~13°/day: reaches the 8° orb in ~11 min
    eph = FakeEphemeris({"saturn": lambda t: 108.1, "moon": lambda t: 100.0 + 13.2 * (t - T0),
                         "sun": lambda t: 250.0, "mercury": lambda t: 300.0})
    p = profile().model_copy(update={"conjunction": profile().conjunction.model_copy(
        update={"mode": "orb", "orb_deg": 8.0})})
    (a,) = run(ctx(eph=eph, prof=p, u=30), R.of("aspects"))
    f = a.fact("conjunct_with", "graha:moon", frame="rashi")
    assert f.value == () and f.sensitivity == "sensitive"


def test_relations_share_the_default_houses_request():
    from astro.calc.features.relations import Relations
    assert R.of("houses") in Relations().requires({})


def test_builtin_methods_without_entry_points_and_broken_plugins(monkeypatch):
    def broken():
        raise ImportError("missing dependency")
    eps = [SimpleNamespace(name="broken", load=lambda: broken())]
    monkeypatch.setattr(method_base, "entry_points", lambda group: eps)
    reg = MethodRegistry(ROOT / "profiles" / "method")
    assert {"parashari", "bnn"} <= set(reg.adapters)
    assert "missing dependency" in reg.broken["broken"]
    reg.get("parashari", purpose="calculation")


def test_withdrawn_method_never_runs(tmp_path):
    import shutil
    shutil.copytree(ROOT / "profiles" / "method", tmp_path / "m")
    p = tmp_path / "m" / "bnn.yaml"
    p.write_text(p.read_text().replace("status: draft", "status: withdrawn"))
    reg = MethodRegistry(tmp_path / "m")
    from astro.calc.core.status import CalcError
    with pytest.raises(CalcError):
        reg.get("bnn", purpose="calculation")
