"""Birth input → normalized instant (INP-1…INP-3, design §6.2, §6.3).

- Dates keep their calendar; Julian dates are converted with provenance, anything else is
  `needs_input` asking for a verified conversion (no silent reinterpretation).
- Offsets come from the pinned `tzdata` package (never the host's database) or from an explicit,
  documented UTC offset. A DST gap is `invalid_local_time`; a fold returns both candidates.
- An unknown time uses local noon with u = 12 h: Lagna-dependent facts become `unknown`.
"""

from __future__ import annotations

import hmac
import importlib.resources
import re
from collections.abc import Callable
from datetime import UTC, date, datetime, time, timedelta
from typing import Literal
from zoneinfo import ZoneInfo

import tzdata
from pydantic import BaseModel, ConfigDict, Field, field_validator

from astro.calc.context import NormalizedBirth
from astro.calc.core.canonical import canonical_json
from astro.calc.core.status import Reason
from astro.calc.core.timescale import jd_from_utc, julian_to_gregorian

Precision = Literal["minute", "rounded_5", "rounded_15", "hour", "unknown"]
DEFAULT_UNCERTAINTY = {"minute": 2.0, "rounded_5": 3.0, "rounded_15": 8.0, "hour": 30.0}
UNKNOWN_TIME_U = 720.0
_ZONE_NAME = re.compile(r"^[A-Za-z][A-Za-z0-9_+\-]*(/[A-Za-z0-9_+\-]+)*$")


class BirthInput(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    year: int
    month: int = Field(ge=1, le=12)
    day: int = Field(ge=1, le=31)
    calendar: str = "gregorian"
    local_time: time | None = None
    time_precision: Precision = "minute"
    time_source: Literal["certificate", "family", "rounded", "rectified", "unknown"] = "unknown"
    uncertainty_minutes: float | None = Field(default=None, ge=0, le=720)
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)
    elevation_m: float = 0.0
    timezone: str | None = None
    utc_offset_minutes: int | None = Field(default=None, ge=-16 * 60, le=16 * 60)
    time_standard_note: str | None = None
    # how the coordinates were obtained (INP-1): gazetteer match, or supplied directly
    place_provenance: dict | None = None

    @field_validator("local_time")
    @classmethod
    def _naive_clock_time(cls, v: time | None) -> time | None:
        if v is not None and v.tzinfo is not None:
            raise ValueError("local_time is a clock reading without an offset; give the zone "
                             "in `timezone` or a documented offset in `utc_offset_minutes`")
        return v


class Normalization(BaseModel):
    model_config = ConfigDict(frozen=True)

    status: Literal["ok", "needs_input", "unsupported"]
    reason: Reason | None = None
    detail: str = ""
    birth: NormalizedBirth | None = None
    utc: datetime | None = None
    candidates_utc: tuple[datetime, ...] = ()
    provenance: dict = Field(default_factory=dict)
    assumptions: tuple[str, ...] = ()


def load_zone(name: str) -> ZoneInfo:
    """A zone from the pinned tzdata package, never from the host's database."""
    if not _ZONE_NAME.match(name) or ".." in name:
        raise KeyError(name)
    res = importlib.resources.files("tzdata.zoneinfo").joinpath(*name.split("/"))
    if not res.is_file():
        raise KeyError(name)
    with res.open("rb") as fh:
        return ZoneInfo.from_file(fh, key=name)


def timezonefinder_lookup(lat: float, lon: float) -> str | None:
    """Default coordinates → IANA zone lookup (optional `geo` extra)."""
    from timezonefinder import TimezoneFinder

    return TimezoneFinder().timezone_at(lat=lat, lng=lon)


def _julian_month_days(year: int, month: int) -> int:
    if month == 2:
        return 29 if year % 4 == 0 else 28
    return 30 if month in (4, 6, 9, 11) else 31


def _needs(reason: Reason, detail: str, **kw) -> Normalization:
    return Normalization(status="needs_input", reason=reason, detail=detail, **kw)


def normalize_birth(inp: BirthInput, *, expected_tzdata: str | None = None,
                    tz_lookup: Callable[[float, float], str | None] | None = None
                    ) -> Normalization:
    prov: dict = {"tzdata": tzdata.IANA_VERSION,
                  "place": inp.place_provenance or {"source": "coordinates",
                                                    "latitude": inp.latitude,
                                                    "longitude": inp.longitude}}
    assumptions: list[str] = []
    if expected_tzdata is not None and expected_tzdata != tzdata.IANA_VERSION:
        return Normalization(status="unsupported", reason=Reason.UNSUPPORTED_PROFILE,
                             detail=f"tzdata {tzdata.IANA_VERSION} != profile {expected_tzdata}")

    # 1. date and calendar
    if inp.calendar == "gregorian":
        try:
            date(inp.year, inp.month, inp.day)
        except ValueError as e:
            return _needs(Reason.MISSING_INPUT, f"invalid Gregorian date: {e}")
        y, m, d = inp.year, inp.month, inp.day
    elif inp.calendar == "julian":
        if inp.day > _julian_month_days(inp.year, inp.month):
            return _needs(Reason.MISSING_INPUT, "invalid Julian date")
        y, m, d = julian_to_gregorian(inp.year, inp.month, inp.day)
        prov["calendar_conversion"] = {
            "from": {"calendar": "julian", "date": [inp.year, inp.month, inp.day]},
            "to": {"calendar": "gregorian", "date": [y, m, d]},
            "converter": "astro.calc.core.timescale (Meeus ch. 7)"}
    else:
        return _needs(Reason.UNSUPPORTED_CALENDAR,
                      f"no converter for calendar {inp.calendar!r}; supply a verified "
                      "Gregorian or Julian date with its source")
    if not 1 <= y <= 9999:
        return Normalization(status="unsupported", reason=Reason.OUT_OF_RANGE,
                             detail="years outside 1..9999 need an explicit UTC offset path")

    # 2. time and precision
    time_known = inp.local_time is not None and inp.time_precision != "unknown"
    local_t = inp.local_time if time_known else time(12, 0)
    if time_known:
        u = inp.uncertainty_minutes if inp.uncertainty_minutes is not None \
            else DEFAULT_UNCERTAINTY[inp.time_precision]
    else:
        u = UNKNOWN_TIME_U
    local = datetime.combine(date(y, m, d), local_t)
    prov["time"] = {"known": time_known, "precision": inp.time_precision,
                    "source": inp.time_source, "uncertainty_minutes": u}

    # 3. offset
    if inp.utc_offset_minutes is not None:
        utc = (local - timedelta(minutes=inp.utc_offset_minutes)).replace(tzinfo=UTC)
        prov["offset"] = {"source": "documented_standard", "minutes": inp.utc_offset_minutes,
                          "note": inp.time_standard_note}
    else:
        zone_name = inp.timezone
        zone_src = "supplied"
        if zone_name is None:
            zone_name = (tz_lookup or timezonefinder_lookup)(inp.latitude, inp.longitude)
            zone_src = "coordinates_lookup"
            if zone_name is None:
                return _needs(Reason.MISSING_INPUT,
                              "no time zone for these coordinates; supply an IANA zone or a "
                              "documented UTC offset")
        try:
            zone = load_zone(zone_name)
        except KeyError:
            return _needs(Reason.MISSING_INPUT, f"unknown IANA time zone {zone_name!r}")
        a = local.replace(tzinfo=zone, fold=0)
        b = local.replace(tzinfo=zone, fold=1)
        if a.astimezone(UTC).astimezone(zone).replace(tzinfo=None) != local:
            return _needs(Reason.INVALID_LOCAL_TIME,
                          f"{local} does not exist in {zone_name} (DST gap)",
                          provenance=prov)
        if a.utcoffset() != b.utcoffset():
            cands = (a.astimezone(UTC), b.astimezone(UTC))
            return _needs(Reason.AMBIGUOUS_LOCAL_TIME,
                          f"{local} occurs twice in {zone_name} (DST fold)",
                          candidates_utc=cands, provenance=prov)
        utc = a.astimezone(UTC)
        offset_min = a.utcoffset().total_seconds() / 60
        prov["offset"] = {"source": f"tzdata:{zone_src}", "zone": zone_name,
                          "minutes": offset_min, "abbreviation": a.tzname()}
        if y < 1970 or offset_min % 15:
            assumptions.append(
                f"UTC offset {offset_min:+g} min for {zone_name} is taken from the IANA history; "
                "it is not proof of the clock standard actually used")

    birth = NormalizedBirth(jd_ut=jd_from_utc(utc), latitude=inp.latitude,
                            longitude=inp.longitude, elevation_m=inp.elevation_m,
                            time_known=time_known, uncertainty_minutes=u)
    if not time_known:
        assumptions.append("birth time unknown: computed at local noon; Lagna facts unknown")
    return Normalization(status="ok", birth=birth, utc=utc, provenance=prov,
                         assumptions=tuple(assumptions))


def chart_id(key: bytes, birth: NormalizedBirth, profile_id: str) -> str:
    """`chart:<HMAC-SHA256(key, normalized input + profile)>[:12]` (design §5.3)."""
    if len(key) < 16:
        raise ValueError("chart-ID key must be at least 16 bytes")
    msg = canonical_json({"birth": birth.__dict__, "profile": profile_id})
    return "chart:" + hmac.new(key, msg, "sha256").hexdigest()[:12]
