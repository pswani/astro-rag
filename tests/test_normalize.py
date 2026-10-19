from datetime import UTC, datetime, time

import pytest

from astro.calc.core.status import Reason
from astro.normalize.birth import BirthInput, chart_id, load_zone, normalize_birth

PUNE = {"latitude": 18.52, "longitude": 73.85}


def norm(**kw):
    base = {"year": 1985, "month": 3, "day": 14, "local_time": time(6, 42), **PUNE,
            "timezone": "Asia/Kolkata"}
    base.update(kw)
    return normalize_birth(BirthInput(**base), tz_lookup=lambda lat, lon: None)


def test_basic_ist():
    r = norm()
    assert r.status == "ok" and r.utc == datetime(1985, 3, 14, 1, 12, tzinfo=UTC)
    assert r.birth.uncertainty_minutes == 2.0 and r.birth.time_known
    assert r.provenance["offset"]["minutes"] == 330


@pytest.mark.parametrize("precision,u", [("rounded_5", 3), ("rounded_15", 8), ("hour", 30)])
def test_precision_defaults(precision, u):
    assert norm(time_precision=precision).birth.uncertainty_minutes == u
    assert norm(time_precision=precision, uncertainty_minutes=1).birth.uncertainty_minutes == 1


def test_unknown_time_is_local_noon_whole_day():
    r = norm(local_time=None)
    assert r.status == "ok" and not r.birth.time_known
    assert r.birth.uncertainty_minutes == 720
    assert r.utc == datetime(1985, 3, 14, 6, 30, tzinfo=UTC)
    assert any("unknown" in a for a in r.assumptions)


def test_dst_gap_and_fold():
    gap = norm(year=2021, month=3, day=14, local_time=time(2, 30), timezone="America/New_York",
               **{"latitude": 40.7, "longitude": -74.0})
    assert gap.status == "needs_input" and gap.reason is Reason.INVALID_LOCAL_TIME
    fold = norm(year=2021, month=11, day=7, local_time=time(1, 30),
                timezone="America/New_York", **{"latitude": 40.7, "longitude": -74.0})
    assert fold.status == "needs_input" and fold.reason is Reason.AMBIGUOUS_LOCAL_TIME
    a, b = fold.candidates_utc
    assert (b - a).total_seconds() == 3600


def test_historical_offset_is_labelled_not_prompted():
    # Kolkata before 1942 used several standards; no age-based prompt, only an assumption.
    r = norm(year=1890, month=6, day=1, timezone="Asia/Kolkata")
    assert r.status == "ok"
    assert r.assumptions and "IANA history" in r.assumptions[0]


def test_documented_offset_bypasses_zone():
    r = norm(year=1890, month=6, day=1, timezone=None, utc_offset_minutes=353,
             time_standard_note="Madras time per certificate")
    assert r.status == "ok" and r.provenance["offset"]["source"] == "documented_standard"
    assert r.utc == datetime(1890, 6, 1, 0, 49, tzinfo=UTC)


def test_julian_calendar_with_provenance():
    r = norm(year=1700, month=2, day=29, calendar="julian", timezone=None,
             utc_offset_minutes=0)
    assert r.status == "ok"
    assert r.provenance["calendar_conversion"]["to"]["date"] == [1700, 3, 11]


def test_other_calendar_requests_verified_conversion():
    r = norm(calendar="vikram_samvat")
    assert r.status == "needs_input" and r.reason is Reason.UNSUPPORTED_CALENDAR


def test_invalid_dates():
    assert norm(month=2, day=30).reason is Reason.MISSING_INPUT
    assert norm(year=1701, month=2, day=29, calendar="julian").reason is Reason.MISSING_INPUT


def test_missing_zone_and_lookup():
    r = norm(timezone=None)
    assert r.status == "needs_input" and r.reason is Reason.MISSING_INPUT
    found = normalize_birth(BirthInput(year=1985, month=3, day=14, local_time=time(6, 42), **PUNE),
                            tz_lookup=lambda lat, lon: "Asia/Kolkata")
    assert found.status == "ok" and found.provenance["offset"]["source"].endswith("lookup")
    assert norm(timezone="Mars/Olympus").reason is Reason.MISSING_INPUT
    assert norm(timezone="../etc/passwd").reason is Reason.MISSING_INPUT


def test_timezonefinder_default_lookup():
    pytest.importorskip("timezonefinder")
    r = normalize_birth(BirthInput(year=1985, month=3, day=14, local_time=time(6, 42), **PUNE))
    assert r.provenance["offset"]["zone"] == "Asia/Kolkata"


def test_zone_from_pinned_tzdata_and_version_check():
    assert load_zone("Asia/Kolkata").key == "Asia/Kolkata"
    r = normalize_birth(BirthInput(year=1985, month=3, day=14, **PUNE, timezone="Asia/Kolkata"),
                        expected_tzdata="1999z")
    assert r.status == "unsupported" and r.reason is Reason.UNSUPPORTED_PROFILE


def test_chart_id_is_keyed_and_deterministic():
    b = norm().birth
    k = b"k" * 32
    assert chart_id(k, b, "parashari_v1") == chart_id(k, b, "parashari_v1")
    assert chart_id(k, b, "parashari_v1") != chart_id(b"j" * 32, b, "parashari_v1")
    assert chart_id(k, b, "parashari_v1") != chart_id(k, b, "bnn_v1")
    assert chart_id(k, b, "parashari_v1").startswith("chart:")
    with pytest.raises(ValueError):
        chart_id(b"short", b, "parashari_v1")
