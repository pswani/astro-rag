from datetime import UTC, datetime, timedelta, timezone

import pytest
import swisseph as swe
from hypothesis import given
from hypothesis import strategies as st

from astro.calc.core import angles as A
from astro.calc.core import timescale as T
from astro.calc.core.canonical import canonical_json, content_hash
from astro.calc.core.intervals import Interval, segment

lons = st.floats(min_value=-1e4, max_value=1e4, allow_nan=False)


@given(lons)
def test_norm360_range(x):
    assert 0.0 <= A.norm360(x) < 360.0


@given(lons, lons)
def test_signed_diff_range_and_consistency(a, b):
    d = A.signed_diff(a, b)
    assert -180.0 < d <= 180.0
    assert A.norm360(b + d) == pytest.approx(A.norm360(a), abs=1e-6) or abs(
        A.signed_diff(b + d, a)) < 1e-6


@given(lons)
def test_indices(x):
    s, n, p = A.sign_index(x), A.nakshatra_index(x), A.pada(x)
    assert 0 <= s <= 11 and 0 <= n <= 26 and 1 <= p <= 4
    assert 0 <= A.deg_in_sign(x) < 30.0
    assert 0 <= A.nakshatra_fraction(x) < 1.0
    # pada count since Ashwini is consistent with nakshatra and pada, and with the sign
    assert n * 4 + p - 1 == A.pada_count(x)
    assert A.pada_count(x) // 9 == s  # 9 padas per sign


def test_boundaries_exact():
    assert A.sign_index(30.0) == 1
    assert A.nakshatra_index(40.0 / 3.0) == 1
    assert A.pada(10.0 / 3.0) == 2
    assert (A.nakshatra_index(30.0), A.pada(30.0)) == (2, 2)  # Krittika pada 2 starts at 30°
    for k in range(108):  # every pada boundary, as produced by multiplication
        assert A.pada_count(k * 10.0 / 3.0) == k
    assert A.nakshatra_index(359.9999999) == 26
    assert A.norm360(-1e-18) == 0.0


def test_houses_apart_inclusive():
    assert A.houses_apart(0, 0) == 1
    assert A.houses_apart(0, 1) == 2
    assert A.houses_apart(11, 0) == 2
    assert A.houses_apart(5, 4) == 12


def test_unwrap():
    assert A.unwrap([350, 355, 2, 10]) == [350, 355, 362, 370]
    assert A.unwrap([10, 2, 355]) == [10, 2, -5]


def test_modality_and_parity():
    assert [A.modality(s) for s in range(4)] == ["movable", "fixed", "dual", "movable"]
    assert A.is_odd_sign(0) and not A.is_odd_sign(1)


@given(st.integers(-4000, 6000), st.integers(1, 12), st.integers(1, 28),
       st.floats(0, 23.999), st.sampled_from(["gregorian", "julian"]))
def test_jd_matches_swisseph_and_round_trips(y, m, d, h, cal):
    flag = swe.GREG_CAL if cal == "gregorian" else swe.JUL_CAL
    jd = T.jd_from_civil(y, m, d, h, cal)
    assert jd == pytest.approx(swe.julday(y, m, d, h, flag), abs=1e-9)
    y2, m2, d2, h2 = T.civil_from_jd(jd, cal)
    assert (y2, m2, d2) == (y, m, d)
    assert h2 == pytest.approx(h, abs=1e-6)


def test_julian_gregorian_switch():
    # 1582-10-04 Julian is followed by 1582-10-15 Gregorian
    assert T.jd_from_civil(1582, 10, 4, 0, "julian") + 1 == T.jd_from_civil(1582, 10, 15, 0)
    assert T.julian_to_gregorian(1582, 10, 5) == (1582, 10, 15)


@given(st.datetimes(min_value=datetime(1, 1, 2), max_value=datetime(9998, 12, 30),
                    timezones=st.just(UTC)))
def test_utc_round_trip(dt):
    jd = T.jd_from_utc(dt)
    # a double's resolution at this JD (≈ 80 µs near JD 4.2e6), plus rounding
    tol = timedelta(microseconds=2 + abs(jd) * 86400e6 * 2.0 ** -52)
    assert abs(T.utc_from_jd(jd) - dt) <= tol


def test_jd_from_utc_rejects_naive_and_handles_offsets():
    with pytest.raises(ValueError):
        T.jd_from_utc(datetime(2000, 1, 1))
    ist = timezone(timedelta(hours=5, minutes=30))
    assert T.jd_from_utc(datetime(2000, 1, 1, 17, 30, tzinfo=ist)) == 2451545.0


def test_weekday():
    assert T.weekday_index(2451545.0) == 6  # 2000-01-01 was a Saturday
    assert T.weekday_index(T.jd_from_civil(2026, 10, 19, 12)) == 1  # Monday


def test_interval_and_segment():
    w = Interval(0, 10)
    assert w.contains(0) and not w.contains(10)
    assert w.overlaps(Interval(9, 12)) and not w.overlaps(Interval(10, 12))
    assert w.intersection(Interval(5, 20)) == Interval(5, 10)
    assert w.intersection(Interval(10, 20)) is None
    parts = segment(w, [3, 0, 10, 7, 3, 15])
    assert parts == [Interval(0, 3), Interval(3, 7), Interval(7, 10)]
    with pytest.raises(ValueError):
        Interval(3, 3)


@given(st.lists(st.integers(1, 99), max_size=20))
def test_segment_tiles_window(cuts):
    w = Interval(0, 100)
    parts = segment(w, cuts)
    assert parts[0].start == 0 and parts[-1].end == 100
    assert all(a.end == b.start for a, b in zip(parts, parts[1:], strict=False))


def test_canonical_is_order_independent_and_rounds():
    a = {"b": 1.0000000000001, "a": [1, 2], "t": datetime(2000, 1, 1, tzinfo=UTC)}
    b = {"t": datetime(2000, 1, 1, tzinfo=UTC), "a": (1, 2), "b": 1.0}
    assert canonical_json(a) == canonical_json(b)
    assert content_hash(a) == content_hash(b)
    assert canonical_json({"x": -0.0}) == canonical_json({"x": 0.0})
    with pytest.raises(ValueError):
        canonical_json({"x": float("nan")})
