"""Regression tests for the D11 review findings of round 6: changes next to t, the facts'
own rules at the edges, degenerate target sets."""

from astro.calc.context import ChartContext, NormalizedBirth
from astro.calc.core.timescale import MINUTE, SECOND
from astro.calc.engine import FeatureRequest as R
from astro.calc.features.common import assess_angle, assess_lon, target_changes
from astro.calc.registry import default_engine

from .fake_ephemeris import FakeEphemeris
from .helpers import profile, refdata

T0 = 2451545.0
U = 60.0
LO = T0 - U * MINUTE


def ctx(eph, prof=None):
    return ChartContext("chart:r6", NormalizedBirth(T0, 18.5, 73.8, uncertainty_minutes=U),
                        prof or profile(), eph, refdata())


def run(eph, feature, prof=None):
    (r,) = default_engine().run(ctx(eph, prof), [R.of(feature)]).values()
    return r


def test_a_change_a_hair_before_t_has_a_margin_of_about_zero():
    for offset in (0.01, 0.02, -0.01):
        moon = lambda t, o=offset: 30.0 + 13.0 * (t - T0 + o * SECOND)  # noqa: E731
        f = run(FakeEphemeris({"moon": moon}), "positions").fact("sign", "graha:moon")
        assert f.sensitivity == "sensitive"
        margin = f.margin_minutes[0] if offset > 0 else f.margin_minutes[1]
        assert margin is not None and margin < 0.01, (offset, f.margin_minutes)


def test_empty_and_single_target_sets():
    c = ctx(FakeEphemeris({"moon": lambda t: 100.0 + 13.0 * (t - T0)}))
    assert assess_angle(c, "mars", "venus", (), lambda x: x).sensitivity == "stable"
    a = assess_lon(c, "moon", target_changes(c, "moon", [100.1]), lambda lon: lon >= 100.1)
    assert a.sensitivity == "sensitive" and abs(a.margins[1] - 0.1 / 13 * 1440) < 0.01


def test_conjunction_exactly_at_the_orb_edge_holds():
    # Mars–Venus is a hair inside 8.3° at t − u and closing: conjunct over the whole interval
    # (exactly 8.3° is not representable: 100 − 91.7 rounds to 8.300000000000011)
    p = profile().model_copy(update={"conjunction": profile().conjunction.model_copy(
        update={"mode": "orb", "orb_deg": 8.3})})
    eph = FakeEphemeris({"venus": lambda t: 100.0,
                         "mars": lambda t: 91.7 + 1e-7 + 1.0 * (t - LO),
                         "sun": lambda t: 300.0, "mercury": lambda t: 250.0})
    a = run(eph, "aspects", p)
    f = a.fact("conjunct_with", "graha:mars", frame="rashi")
    assert f.value == ("graha:venus",) and f.sensitivity == "stable"


def test_gandanta_edge_at_the_start_is_decided_by_the_rule():
    # a hair outside the arc at t − u (not gandanta) and moving in: the rule, not a sector
    # proxy, decides that the start of the interval differs
    arc = profile().gandanta.arc_deg
    eph = FakeEphemeris({"mars": lambda t: 360.0 - arc - 1e-7 + 1.0 * (t - LO)})
    f = run(eph, "condition").fact("gandanta", "graha:mars")
    assert f.value is True and f.sensitivity == "sensitive"
    assert abs(f.margin_minutes[0] - U) < 0.01
