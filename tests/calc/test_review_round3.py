"""Regression tests for the D11 review findings (round 2)."""

from types import SimpleNamespace

import pytest
from pydantic import ValidationError

from astro.calc.context import ChartContext, NormalizedBirth
from astro.calc.core.status import Reason
from astro.calc.core.timescale import jd_from_civil
from astro.calc.engine import FeatureRequest as R
from astro.calc.profile import Combustion
from astro.calc.registry import default_engine
from astro.methods import base as method_base
from astro.methods.base import MethodRegistry
from astro.normalize.gazetteer import CityTable

from .fake_ephemeris import FakeEphemeris
from .helpers import ROOT, ephemeris, profile, refdata

PUNE_JD = jd_from_civil(1985, 3, 14, 1.2)
T0 = 2451545.0
FAR = {"sun": lambda t: 150.0, "mercury": lambda t: 155.0, "venus": lambda t: 160.0,
       "mars": lambda t: 165.0, "rahu": lambda t: 75.0}


def ctx(eph=None, prof=None, u=0.0, jd=T0, lat=18.52, lon=73.85, known=True):
    return ChartContext("chart:r3", NormalizedBirth(jd, lat, lon, time_known=known,
                                                   uncertainty_minutes=u),
                        prof or profile(), eph or ephemeris(), refdata())


def run(c, *reqs):
    out = default_engine().run(c, list(reqs))
    return [out[r] for r in reqs]


def test_aspect_received_from_a_body_that_could_change_sign():
    # Moon 0.2° before the end of Aries, moving 13°/day: inside ±30 min it enters Taurus,
    # whose 7th sign is Scorpio, where Saturn is
    eph = FakeEphemeris({**FAR, "moon": lambda t: 29.8 + 13.0 * (t - T0),
                         "saturn": lambda t: 215.0, "jupiter": lambda t: 250.0})
    (a,) = run(ctx(eph=eph, u=30), R.of("aspects"))
    f = a.fact("aspected_by", "graha:saturn", frame="rashi")
    assert "graha:moon" not in f.value and f.sensitivity == "sensitive"


def test_unrelated_sensitive_moon_leaves_other_conjunctions_stable():
    # unknown time: the Moon's sign is sensitive, but Saturn and Jupiter share Capricorn far away
    eph = FakeEphemeris({**FAR, "moon": lambda t: 25.0 + 13.0 * (t - T0),
                         "saturn": lambda t: 280.0, "jupiter": lambda t: 285.0})
    (pos, a) = run(ctx(eph=eph, u=720, known=False), R.of("positions"), R.of("aspects"))
    assert pos.fact("sign", "graha:moon").sensitivity == "sensitive"
    f = a.fact("conjunct_with", "graha:saturn", frame="rashi")
    assert f.value == ("graha:jupiter",) and f.sensitivity == "stable"


def test_lord_houses_follow_the_lagna_sensitivity():
    # Lagna 0.05° before a sign boundary moving 1°/4 min: the lordships can shift
    eph = FakeEphemeris({}, asc=lambda t: 29.95 + 360.0 * (t - T0))
    (cx,) = run(ctx(eph=eph, u=5), R.of("dasha_context", as_of="2001-01-01T00:00:00+00:00"))
    assert cx.fact("lord_houses", "dasha:vimshottari:MD").sensitivity == "sensitive"


def test_incomplete_combustion_orbs_are_refused_at_load():
    with pytest.raises(ValidationError):
        Combustion(orbs={"mercury": 14, "venus": 10})
    with pytest.raises(ValidationError):
        Combustion(orbs={g: 10 for g in ("moon", "mars", "mercury", "jupiter", "venus",
                                         "saturn", "pluto")})


def test_plugins_cannot_replace_builtins_and_bad_plugins_are_isolated(monkeypatch):
    impostor = SimpleNamespace(method_id="parashari")
    nameless = SimpleNamespace()
    eps = [SimpleNamespace(name="ext", load=lambda: lambda: impostor),
           SimpleNamespace(name="bad", load=lambda: lambda: nameless)]
    monkeypatch.setattr(method_base, "entry_points", lambda group: eps)
    reg = MethodRegistry(ROOT / "profiles" / "method")
    assert type(reg.adapters["parashari"]).__name__ == "ParashariAdapter"
    assert "already registered" in reg.broken["ext"] and "bad" in reg.broken


def test_house_aspects_under_cusp_systems_use_their_own_frame():
    p = profile().model_copy(update={"house_system": "placidus"})
    (a,) = run(ctx(prof=p, jd=PUNE_JD), R.of("aspects"))
    assert a.fact("aspected_by", "bhava:4", frame="lagna_rashi").value is not None
    with pytest.raises(KeyError):
        a.fact("aspected_by", "bhava:4", frame="lagna")
    assert a.provenance["house_aspects"] == {"frame": "lagna_rashi", "counting": "whole_sign"}


def test_undefined_cusps_report_an_explicit_reason():
    p = profile().model_copy(update={"house_system": "placidus"})
    (h,) = run(ctx(prof=p, jd=PUNE_JD, lat=70.0, lon=19.0), R.of("houses"))
    assert h.reason is Reason.UNSUPPORTED_FEATURE and "lagna" in h.detail


@pytest.mark.parametrize("query,code", [("London, UK", "GB"), ("New York City, USA", "US"),
                                        ("Dubai, UAE", "AE")])
def test_country_aliases(query, code):
    r = CityTable().lookup(query)
    assert r.status == "found" and r.place.country_code == code
