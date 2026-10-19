"""Regression tests for the D11 review findings of round 5: value-based end points, canonical
angle pairs, shared stations."""

from astro.calc.context import ChartContext, NormalizedBirth
from astro.calc.core.timescale import MINUTE
from astro.calc.engine import FeatureRequest as R
from astro.calc.features.common import angle_changes, sign_changes, station_times
from astro.calc.registry import default_engine

from .fake_ephemeris import FakeEphemeris
from .helpers import profile, refdata

T0 = 2451545.0
U = 60.0
LO = T0 - U * MINUTE


def ctx(eph):
    return ChartContext("chart:r5", NormalizedBirth(T0, 18.5, 73.8, uncertainty_minutes=U),
                        profile(), eph, refdata())


def sign_fact(eph, body):
    (pos,) = default_engine().run(ctx(eph), [R.of("positions")]).values()
    return pos.fact("sign", f"graha:{body}")


def test_direct_crossing_exactly_at_the_start_is_not_a_change():
    # the Moon reaches 30° exactly at t − u: Taurus holds over the whole closed interval
    f = sign_fact(FakeEphemeris({"moon": lambda t: 30.0 + 13.0 * (t - LO)}), "moon")
    assert f.value == "rashi:taurus" and f.sensitivity == "stable"


def test_backward_crossing_exactly_at_the_start_is_a_change():
    # Mars is exactly at 30° (Taurus) at t − u and moves back into Aries straight after
    f = sign_fact(FakeEphemeris({"mars": lambda t: 30.0 - 1.0 * (t - LO)}), "mars")
    assert f.value == "rashi:aries" and f.sensitivity == "sensitive"
    assert abs(f.margin_minutes[0] - U) < 1e-6 and f.margin_minutes[1] is None


def test_angle_pairs_are_solved_once_for_any_orb():
    c = ctx(FakeEphemeris({}))
    a = angle_changes(c, "mars", "venus", (8.3, 351.7))
    b = angle_changes(c, "venus", "mars", (8.3, 351.7))
    assert a == b
    assert len([k for k in c.memo if k[0] == "angle"]) == 1


def test_stations_are_found_once_and_shared():
    c = ctx(FakeEphemeris({"mars": lambda t: 10.0 + (t - T0) ** 2}))  # a station at t
    sign_changes(c, "mars")
    station_times(c, "mars")
    assert len([k for k in c.memo if k[0] == "stations"]) == 1
