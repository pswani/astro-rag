import math

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from astro.calc.core.angles import norm360
from astro.calc.core.timescale import SECOND
from astro.calc.solver import (
    contacts,
    crossings,
    find_stations,
    first_crossing_after,
    last_crossing_before,
)


def linear(rate, start=0.0):
    return lambda t: norm360(start + rate * t)


def test_linear_sign_crossings_are_exact():
    lon = linear(1.0, 5.0)  # 1°/day from 5°
    cs = crossings(lon, 0.0, 100.0, step=10.0, width=30.0)
    assert [round(c.jd, 6) for c in cs] == [25.0, 55.0, 85.0]
    assert [c.index for c in cs] == [1, 2, 3]
    assert all(c.direction == 1 for c in cs)


def test_wraps_through_zero_aries():
    lon = linear(2.0, 350.0)
    cs = crossings(lon, 0.0, 10.0, step=1.0, width=30.0)
    assert len(cs) == 1 and cs[0].jd == pytest.approx(5.0, abs=SECOND) and cs[0].index == 0


def test_retrograde_loop_returns_three_crossings():
    # longitude 20 + 5 sin(t): passes 22° forward, backward, forward
    lon = lambda t: 20 + 5 * math.sin(t)  # noqa: E731
    speed = lambda t: 5 * math.cos(t)  # noqa: E731
    cs = crossings(lon, 0.0, 2 * math.pi + 1.0, step=0.5, speed=speed, targets=[22.0])
    assert [c.direction for c in cs] == [1, -1, 1]
    for c in cs:
        assert lon(c.jd) == pytest.approx(22.0, abs=1e-5)


def test_cross_and_recross_inside_one_grid_step_is_found():
    # a station right next to a boundary: the grid alone would miss both crossings
    lon = lambda t: 29.999 + 0.01 - 0.01 * (t - 1.0) ** 2  # noqa: E731  peak 30.009 at t = 1
    speed = lambda t: -0.02 * (t - 1.0)  # noqa: E731
    without = crossings(lon, 0.0, 2.0, step=2.0, width=30.0)
    with_speed = crossings(lon, 0.0, 2.0, step=2.0, width=30.0, speed=speed)
    assert without == []
    assert [c.direction for c in with_speed] == [1, -1]


def test_station_finding_and_contact():
    lon = lambda t: 10 + (t - 3.0) ** 2  # noqa: E731  minimum 10 at t = 3
    speed = lambda t: 2 * (t - 3.0)  # noqa: E731
    st_ = find_stations(speed, 0.0, 6.0, 0.7)
    assert st_ == [pytest.approx(3.0, abs=SECOND)]
    cs = crossings(lon, 0.0, 6.0, step=0.7, speed=speed, targets=[9.9])
    assert cs == []
    ct = contacts(lon, 0.0, 6.0, st_, [9.9, 50.0], tol_deg=0.5, found=cs)
    # a target that is crossed is not a contact
    crossed = crossings(lon, 0.0, 6.0, step=0.7, speed=speed, targets=[10.2])
    assert len(crossed) == 2
    assert contacts(lon, 0.0, 6.0, st_, [10.2], tol_deg=0.5, found=crossed) == []
    assert len(ct) == 1 and ct[0].target_index == 0 and ct[0].distance == pytest.approx(0.1)


def test_exact_boundary_belongs_to_later_sector():
    lon = linear(1.0, 0.0)
    cs = crossings(lon, 0.0, 30.0, step=5.0, width=30.0)
    assert len(cs) == 1 and cs[0].jd == 30.0 and cs[0].index == 1
    # starting exactly on a boundary is not a crossing
    assert crossings(lon, 30.0, 40.0, step=5.0, width=30.0) == []


def test_last_and_first_crossing():
    lon = linear(12.0, 0.0)  # like a tithi angle: 12°/day, so tithis are 1 day long
    before = last_crossing_before(lon, 3.5, width=12.0, step=0.25, span=2.0)
    after = first_crossing_after(lon, 3.5, width=12.0, step=0.25, span=2.0)
    assert before.jd == pytest.approx(3.0, abs=SECOND)
    assert after.jd == pytest.approx(4.0, abs=SECOND)
    at = first_crossing_after(lon, 3.0, width=12.0, step=0.25, span=2.0)
    assert at.jd == pytest.approx(4.0, abs=SECOND)  # strictly after


@settings(max_examples=60, deadline=None)
@given(st.floats(-15, 15).filter(lambda r: abs(r) > 0.05), st.floats(0, 360),
       st.floats(1, 40))
def test_crossing_count_matches_sector_change(rate, start, days):
    lon = linear(rate, start)
    cs = crossings(lon, 0.0, days, step=min(5.0, 90.0 / abs(rate)), width=30.0)
    total = rate * days
    expected = abs(math.floor((start + total) / 30.0) - math.floor(start / 30.0))
    assert len(cs) == expected
    for c in cs:
        assert lon(c.jd) == pytest.approx(c.boundary, abs=1e-4) or abs(
            lon(c.jd) - c.boundary) > 359.99
