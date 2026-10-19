"""Ground truth for derived-fact sensitivity (CALC-7): every derived fact is re-evaluated at
u = 0 on a fine grid across [t − u, t + u]. A fact must be `sensitive` exactly when the sampled
values differ, and its margins must match the first sampled change on each side."""

import pytest

from astro.calc.context import ChartContext, NormalizedBirth
from astro.calc.core.timescale import MINUTE
from astro.calc.engine import FeatureRequest as R
from astro.calc.registry import default_engine

from .fake_ephemeris import FakeEphemeris
from .helpers import profile, refdata

T0 = 2451545.0
U = 180.0  # minutes
STEP = 2.0  # sampling grid, minutes

DERIVED = {("aspects", "aspected_by"), ("aspects", "conjunct_with"),
           ("condition", "dignity"), ("condition", "combust"),
           ("condition", "graha_yuddha"), ("relations", "occupants"), ("houses", "house")}


def sky(variant: int) -> FakeEphemeris:
    """A busy synthetic sky: a fast Lagna, the Moon crossing signs, a station near the Sun,
    planets close enough to go to war."""
    ts = T0 + 2 / 24  # a station two hours after birth
    lons = {
        0: {"moon": lambda t: 29.8 + 13.0 * (t - T0), "sun": lambda t: 100.0,
            "mercury": lambda t: 113.0 + 0.5 * (t - ts) ** 2,
            "mars": lambda t: 200.0 + 1.0 * (t - T0), "venus": lambda t: 200.05,
            "jupiter": lambda t: 95.0, "saturn": lambda t: 155.0,
            "rahu": lambda t: 60.0},
        1: {"moon": lambda t: 118.5 + 13.0 * (t - T0), "sun": lambda t: 59.7 + 1.0 * (t - T0),
            "mercury": lambda t: 61.0, "mars": lambda t: 330.4, "venus": lambda t: 330.9,
            "jupiter": lambda t: 240.0, "saturn": lambda t: 300.0, "rahu": lambda t: 10.0},
    }[variant]
    return FakeEphemeris(lons, asc=lambda t: 15.0 + 360.0 * (t - T0))


def facts_at(eph, prof, t, u):
    c = ChartContext("chart:g", NormalizedBirth(t, 18.5, 73.8, uncertainty_minutes=u), prof,
                     eph, refdata())
    out = default_engine().run(c, [R.of(f) for f, _ in DERIVED])
    return {(f.kind, f.subject, f.frame): f for (feat, kind) in DERIVED
            for f in out[R.of(feat)].facts if f.kind == kind}


@pytest.mark.parametrize("variant", [0, 1])
@pytest.mark.parametrize("winner,houses", [("north_latitude", "whole_sign"),
                                           ("lesser_longitude", "whole_sign"),
                                           ("north_latitude", "placidus"),
                                           ("lesser_longitude", "sripati")])
def test_derived_sensitivity_matches_sampling(variant, winner, houses):
    eph = sky(variant)  # the fake's cusps are equal houses from the Lagna: a cusp system
    prof = profile().model_copy(update={
        "graha_yuddha": profile().graha_yuddha.model_copy(update={"winner": winner}),
        "house_system": houses})
    at_t = facts_at(eph, prof, T0, U)
    n = int(U / STEP)
    samples = [facts_at(eph, prof, T0 + k * STEP * MINUTE, 0.0) for k in range(-n, n + 1)]
    checked = 0
    for key, fact in at_t.items():
        values = [s[key].value for s in samples]
        changes = [k for k in range(-n, n + 1) if values[k + n] != fact.value]
        assert (fact.sensitivity == "sensitive") == bool(changes), (key, fact.value, values)
        if changes:
            checked += 1
            before = [-k for k in changes if k < 0]
            after = [k for k in changes if k > 0]
            mb, ma = fact.margin_minutes
            if after:  # the first sampled change lies within one step of the solved margin
                assert ma is not None and ma <= min(after) * STEP + 1e-6
                assert ma > (min(after) - 1) * STEP - 1e-6
            if before:
                assert mb is not None and mb <= min(before) * STEP + 1e-6
                assert mb > (min(before) - 1) * STEP - 1e-6
    assert checked >= 3  # the sky is busy enough to exercise the method


def test_station_switches_the_combustion_orb():
    eph = sky(0)  # Mercury 13° from the Sun, retrograde until a station two hours later
    f = facts_at(eph, profile(), T0, U)[("combust", "graha:mercury", None)]
    assert f.value is False and f.sensitivity == "sensitive"  # orb 12 now, 14 after


def test_lords_of_no_sign_are_stable():
    eph = FakeEphemeris({"moon": lambda t: 70.0}, asc=lambda t: 29.95 + 360.0 * (t - T0))
    c = ChartContext("chart:g", NormalizedBirth(T0, 18.5, 73.8, uncertainty_minutes=5),
                     profile(), eph, refdata())
    (cx,) = default_engine().run(c, [R.of("dasha_context",
                                          as_of="2000-01-02T00:00:00+00:00")]).values()
    md = cx.fact("lord_houses", "dasha:vimshottari:MD")
    assert cx.fact("period_lord", "dasha:vimshottari:MD").value == "graha:rahu"
    assert md.value == () and md.sensitivity == "stable"
