"""Civil dates and UTC datetimes ↔ Julian Day (UT).

Meeus, *Astronomical Algorithms* (2nd ed.), ch. 7. Gregorian and proleptic-Julian calendars are
both supported; the caller states which one a date is in, nothing is inferred from the year.
"""

from __future__ import annotations

import math
from datetime import UTC, datetime, timedelta
from typing import Literal

Calendar = Literal["gregorian", "julian"]

_J2000 = 2451545.0
_J2000_DT = datetime(2000, 1, 1, 12, tzinfo=UTC)


def jd_from_civil(year: int, month: int, day: int, hour: float = 0.0,
                  calendar: Calendar = "gregorian") -> float:
    """JD for a civil date at `hour` (UT, fractional hours)."""
    y, m = (year - 1, month + 12) if month <= 2 else (year, month)
    if calendar == "gregorian":
        a = math.floor(y / 100)
        b = 2 - a + math.floor(a / 4)
    elif calendar == "julian":
        b = 0
    else:  # pragma: no cover - guarded by Literal at call sites
        raise ValueError(f"unsupported calendar {calendar!r}")
    return (math.floor(365.25 * (y + 4716)) + math.floor(30.6001 * (m + 1))
            + day + b - 1524.5 + hour / 24.0)


def civil_from_jd(jd: float, calendar: Calendar = "gregorian") -> tuple[int, int, int, float]:
    """Inverse of `jd_from_civil`: (year, month, day, hour)."""
    z = math.floor(jd + 0.5)
    f = jd + 0.5 - z
    if calendar == "gregorian":
        alpha = math.floor((z - 1867216.25) / 36524.25)
        a = z + 1 + alpha - math.floor(alpha / 4)
    else:
        a = z
    b = a + 1524
    c = math.floor((b - 122.1) / 365.25)
    d = math.floor(365.25 * c)
    e = math.floor((b - d) / 30.6001)
    day = b - d - math.floor(30.6001 * e)
    month = e - 1 if e < 14 else e - 13
    year = c - 4716 if month > 2 else c - 4715
    return int(year), int(month), int(day), f * 24.0


def julian_to_gregorian(year: int, month: int, day: int) -> tuple[int, int, int]:
    """Convert a Julian-calendar date to the proleptic Gregorian date of the same day."""
    y, m, d, _ = civil_from_jd(jd_from_civil(year, month, day, 12.0, "julian"), "gregorian")
    return y, m, d


def jd_from_utc(dt: datetime) -> float:
    """JD (UT) for an aware datetime."""
    if dt.tzinfo is None:
        raise ValueError("naive datetime: a UTC offset is required")
    delta = dt.astimezone(UTC) - _J2000_DT
    return _J2000 + delta.days + (delta.seconds + delta.microseconds / 1e6) / 86400.0


def utc_from_jd(jd: float) -> datetime:
    """Aware UTC datetime for a JD (UT), rounded to the microsecond."""
    micros = round((jd - _J2000) * 86400e6)
    return _J2000_DT + timedelta(microseconds=micros)


def weekday_index(jd_local_civil: float) -> int:
    """0 = Sunday … 6 = Saturday for a JD expressed on a local civil time scale."""
    return int((math.floor(jd_local_civil + 0.5) + 1) % 7)


MINUTE = 1.0 / 1440.0
SECOND = 1.0 / 86400.0
