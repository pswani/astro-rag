"""Assemble a natal chart report from birth input: normalize → engine → one object."""

from __future__ import annotations

import os
import secrets
from dataclasses import dataclass, field
from datetime import UTC, datetime, time, timedelta, timezone, tzinfo
from typing import Any

from astro.calc.context import ChartContext
from astro.calc.core.status import Status
from astro.calc.engine import FeatureRequest as R
from astro.calc.ephemeris.swiss import SwissEphemeris
from astro.calc.model import FeatureResult
from astro.calc.profile import CalcProfile, load_profile
from astro.calc.refdata import YamlReferenceData
from astro.calc.registry import default_engine
from astro.normalize.birth import BirthInput, Normalization, chart_id, load_zone, normalize_birth
from astro.normalize.gazetteer import Place
from astro.resources import astro_home, ephemeris_dir


@dataclass
class ChartRequest:
    year: int
    month: int
    day: int
    local_time: time | None
    latitude: float
    longitude: float
    place: Place | None = None
    timezone: str | None = None
    utc_offset_minutes: int | None = None
    calendar: str = "gregorian"
    precision: str = "minute"
    uncertainty_minutes: float | None = None
    profile_id: str = "parashari_v1"
    vargas: tuple[str, ...] = ("D1", "D9", "D10")
    as_of: datetime | None = None   # for the current dasha; default: now
    native_gender: str | None = None
    elevation_m: float = 0.0


@dataclass
class ChartReport:
    request: ChartRequest
    normalization: Normalization
    profile: CalcProfile | None = None
    chart_id: str | None = None
    results: dict[str, FeatureResult] = field(default_factory=dict)
    local_tz: tzinfo | None = None
    as_of: datetime | None = None

    @property
    def ok(self) -> bool:
        return self.normalization.status == "ok"

    def get(self, feature: str) -> FeatureResult | None:
        r = self.results.get(feature)
        return r if r is not None and r.status is Status.OK else None

    def to_local(self, dt: datetime) -> datetime:
        return dt.astimezone(self.local_tz) if self.local_tz else dt

    def to_json(self) -> dict[str, Any]:
        n = self.normalization
        return {
            "input": {k: (v.isoformat() if hasattr(v, "isoformat") else v)
                      for k, v in self.request.__dict__.items() if k != "place"},
            "place": self.request.place.__dict__ if self.request.place else None,
            "normalization": n.model_dump(mode="json"),
            "profile": self.profile.model_dump(mode="json") if self.profile else None,
            "chart_id": self.chart_id,
            "as_of": self.as_of.isoformat() if self.as_of else None,
            "results": {k: v.model_dump(mode="json") for k, v in self.results.items()},
        }


def _chart_key() -> bytes:
    """Chart IDs are keyed (design §5.3). Set ASTRO_CHART_KEY (hex) for stable IDs."""
    env = os.environ.get("ASTRO_CHART_KEY")
    return bytes.fromhex(env) if env else secrets.token_bytes(32)


def build(req: ChartRequest) -> ChartReport:
    home = astro_home()
    profile = load_profile(home / "profiles" / "calc" / f"{req.profile_id}.yaml")
    birth = BirthInput(
        year=req.year, month=req.month, day=req.day, calendar=req.calendar,
        local_time=req.local_time,
        time_precision="unknown" if req.local_time is None else req.precision,  # type: ignore
        uncertainty_minutes=req.uncertainty_minutes, latitude=req.latitude,
        longitude=req.longitude, elevation_m=req.elevation_m, timezone=req.timezone,
        utc_offset_minutes=req.utc_offset_minutes)
    norm = normalize_birth(birth, expected_tzdata=profile.time.tzdata)
    report = ChartReport(req, norm, profile)
    if not report.ok:
        return report
    zone = norm.provenance["offset"].get("zone")
    report.local_tz = load_zone(zone) if zone else timezone(
        timedelta(minutes=norm.provenance["offset"]["minutes"]))
    eph = SwissEphemeris(ephemeris_dir(home), profile)
    refdata = YamlReferenceData(home / "ontology")
    report.chart_id = chart_id(_chart_key(), norm.birth, profile.id)
    inputs = {"native_gender": req.native_gender} if req.native_gender else {}
    ctx = ChartContext(report.chart_id, norm.birth, profile, eph, refdata, inputs)
    report.as_of = (req.as_of or datetime.now(UTC)).astimezone(UTC)
    requests = {
        "positions": R.of("positions"),
        "houses": R.of("houses"),
        "vargas": R.of("vargas", vargas=req.vargas),
        "panchanga": R.of("panchanga"),
        "vimshottari": R.of("vimshottari"),
        "dasha_active": R.of("dasha_active", as_of=report.as_of.isoformat()),
    }
    out = default_engine().run(ctx, list(requests.values()))
    report.results = {k: out[r] for k, r in requests.items()}
    return report
