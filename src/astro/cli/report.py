"""Assemble a natal chart report from birth input: normalize → engine → one object."""

from __future__ import annotations

import os
import secrets
from dataclasses import dataclass, field
from datetime import UTC, datetime, time, timedelta, timezone, tzinfo
from typing import Any

from astro.calc.context import ChartContext
from astro.calc.core.status import CalcError, Reason, Status
from astro.calc.engine import Engine
from astro.calc.ephemeris.swiss import SwissEphemeris
from astro.calc.model import FeatureResult
from astro.calc.profile import CalcProfile, load_profile
from astro.calc.refdata import load_refdata
from astro.methods.base import MethodProfile, load_registry
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
    method: str = "parashari"
    profile_id: str | None = None   # default: the method profile's default calc profile
    vargas: tuple[str, ...] = ("D1", "D9", "D10")   # charts drawn
    varga_table: tuple[str, ...] = ("D1", "D9", "D10")  # signs tabulated
    method_given: bool = False
    as_of: datetime | None = None   # for the current dasha; default: now
    native_gender: str | None = None
    elevation_m: float = 0.0
    place_query: str | None = None
    place_source: str | None = None


@dataclass
class ChartReport:
    request: ChartRequest
    normalization: Normalization
    profile: CalcProfile | None = None
    method: MethodProfile | None = None
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
            "method": self.method.model_dump(mode="json") if self.method else None,
            "profile": self.profile.model_dump(mode="json") if self.profile else None,
            "chart_id": self.chart_id,
            "as_of": self.as_of.isoformat() if self.as_of else None,
            "results": {k: v.model_dump(mode="json") for k, v in self.results.items()},
        }


class ChartKeyError(ValueError):
    pass


def _chart_key() -> bytes:
    """Chart IDs are keyed (design §5.3). Set ASTRO_CHART_KEY (hex) for stable IDs."""
    env = os.environ.get("ASTRO_CHART_KEY")
    if not env:
        return secrets.token_bytes(32)
    try:
        key = bytes.fromhex(env)
    except ValueError as e:
        raise ChartKeyError("ASTRO_CHART_KEY must be hexadecimal") from e
    if len(key) < 16:
        raise ChartKeyError("ASTRO_CHART_KEY must have at least 32 hex digits")
    return key


def build(req: ChartRequest) -> ChartReport:
    home = astro_home()
    # a chart is a calculation, so a draft method's features may be used (design §7.10);
    # the report states the method's status
    method, adapter = load_registry(home / "profiles" / "method").get(req.method,
                                                                      purpose="calculation")
    profile_id = req.profile_id or method.default_calc_profile
    if profile_id not in method.calc_profiles:
        raise CalcError(Reason.UNSUPPORTED_PROFILE,
                        f"{profile_id} is not a calculation profile of method {method.id} "
                        f"({', '.join(method.calc_profiles)})")
    profile = load_profile(home / "profiles" / "calc" / f"{profile_id}.yaml")
    birth = BirthInput(
        year=req.year, month=req.month, day=req.day, calendar=req.calendar,
        local_time=req.local_time,
        time_precision="unknown" if req.local_time is None else req.precision,  # type: ignore
        uncertainty_minutes=req.uncertainty_minutes, latitude=req.latitude,
        longitude=req.longitude, elevation_m=req.elevation_m, timezone=req.timezone,
        utc_offset_minutes=req.utc_offset_minutes,
        place_provenance=req.place.provenance(req.place_source or "gazetteer",
                                              req.place_query or req.place.name)
        if req.place else None)
    norm = normalize_birth(birth, expected_tzdata=profile.time.tzdata)
    report = ChartReport(req, norm, profile, method)
    if not report.ok:
        return report
    zone = norm.provenance["offset"].get("zone")
    report.local_tz = load_zone(zone) if zone else timezone(
        timedelta(minutes=norm.provenance["offset"]["minutes"]))
    eph = SwissEphemeris(ephemeris_dir(home), profile)
    refdata = load_refdata(home / "ontology")
    report.chart_id = chart_id(_chart_key(), norm.birth, profile.id)
    inputs = {"native_gender": req.native_gender} if req.native_gender else {}
    ctx = ChartContext(report.chart_id, norm.birth, profile, eph, refdata, inputs)
    report.as_of = (req.as_of or datetime.now(UTC)).astimezone(UTC)
    vargas = tuple(dict.fromkeys((*req.vargas, *req.varga_table)))
    plan = {"as_of": report.as_of.isoformat(), "vargas": vargas}
    requests = adapter.features(plan)
    out = Engine(adapter.feature_set()).run(ctx, requests)
    report.results = {r.feature_id: out[r] for r in requests}
    return report
