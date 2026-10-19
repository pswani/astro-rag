"""Typed results of the calculation service (design §7.2, §7.7; calc-review §3.3, M5)."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from astro.calc.core.status import Reason, Status

Sensitivity = Literal["stable", "sensitive", "unknown"]
FactValue = bool | int | float | str | tuple[str, ...] | None

# kind -> python type of `value` (checked by ChartFact). Keep in sync with the features.
FACT_KINDS: dict[str, type | tuple[type, ...]] = {
    "longitude": float,          # sidereal degrees [0, 360)
    "latitude": float,           # ecliptic degrees
    "speed": float,              # degrees/day in longitude
    "retrograde": bool,
    "sign": str,                 # rashi:*
    "degree_in_sign": float,
    "nakshatra": str,            # nakshatra:*
    "pada": int,                 # 1..4
    "nakshatra_lord": str,       # graha:*
    "house": int,                # 1..12 in `frame`
    "house_sign": str,           # rashi:* of a house in `frame`
    "lord_of": str,              # graha:* ruling a house (subject = bhava:N)
    "occupants": tuple,          # graha:* tuple (subject = bhava:N)
    "dispositor_chain": tuple,   # graha:* tuple starting at subject's dispositor
    "dispositor_terminal": str,  # own_sign | cycle
    "varga_sign": str,           # rashi:* in `varga`
    "vargottama": bool,
    "ayanamsa": float,
    "tithi": str, "paksha": str, "karana": str, "nitya_yoga": str, "vara": str,
    "limb_start": str, "limb_end": str,   # ISO UTC instants (subject = the limb ID)
    "sunrise": str, "sunset": str,        # ISO UTC instants
    "karaka_role": tuple,        # role IDs in a karaka scheme
    "native_karaka": str,        # graha:* signifying the native under a scheme
    "transit_house": int,        # house of a transiting body from a natal reference
    "transit_distance": float,   # signed degrees transit − natal point
    "dasha_balance": float,      # years of the first MD remaining at birth
    "dasha_sandhi": bool,        # as-of instant within the profile margin of a boundary
}


def _check_value(kind: str, value: Any) -> None:
    expected = FACT_KINDS.get(kind)
    if expected is None:
        raise ValueError(f"unknown fact kind {kind!r}")
    ok = isinstance(value, expected)
    if expected is float and isinstance(value, bool):
        ok = False
    if expected is int and isinstance(value, bool):
        ok = False
    if expected is tuple and ok:
        ok = all(isinstance(v, str) for v in value)
    if not ok:
        raise ValueError(f"fact kind {kind!r} needs {expected}, got {type(value).__name__}")


class ChartFact(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    id: str
    kind: str
    subject: str
    value: FactValue
    unit: str | None = None
    frame: str | None = None
    varga: str = "D1"
    profile_id: str
    sensitivity: Sensitivity = "stable"
    margin_minutes: tuple[float | None, float | None] = (None, None)
    provenance: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _typed(self) -> ChartFact:
        if self.value is None:
            if self.sensitivity != "unknown":
                raise ValueError("value None requires sensitivity 'unknown'")
            if self.kind not in FACT_KINDS:
                raise ValueError(f"unknown fact kind {self.kind!r}")
        else:
            _check_value(self.kind, self.value)
        return self


def fact_id(chart_id: str, kind: str, subject: str, frame: str | None = None,
            varga: str | None = None) -> str:
    """`<chart>/<kind>/<subject>[/<frame>][/<varga>]` (design §5.3)."""
    parts = [chart_id, kind, subject]
    if frame:
        parts.append(frame)
    if varga:
        parts.append(varga)
    return "/".join(parts)


class Relation(BaseModel):
    """A typed edge (REL-3): aspect system, frame and counting convention are explicit."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    id: str
    kind: Literal["parivartana", "dispositor", "friendship", "bnn_link", "conjunction"]
    source: str
    target: str
    system: str
    frame: str = "rashi"
    counting: Literal["inclusive"] = "inclusive"
    direction: Literal["forward", "backward", "mutual"] = "forward"
    value: str | int | float | None = None
    varga: str = "D1"
    profile_id: str
    sensitivity: Sensitivity = "stable"
    provenance: dict[str, Any] = Field(default_factory=dict)


class DashaPeriod(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    id: str
    system: str
    level: Literal["MD", "AD", "PD", "SD"]
    lord: str
    start_utc: datetime
    end_utc: datetime  # half-open
    parent_id: str | None
    sequence: int
    profile_id: str
    boundary_margin_days: tuple[float | None, float | None] = (None, None)

    @model_validator(mode="after")
    def _ordered(self) -> DashaPeriod:
        if not self.start_utc < self.end_utc:
            raise ValueError("dasha period must have start < end")
        return self


class TransitEvent(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    id: str
    kind: Literal["ingress", "station", "conjunction", "contact", "return", "eclipse", "state"]
    body: str
    target: str | None = None       # rashi:*, nakshatra:*, natal point, or state ID
    start_utc: datetime
    end_utc: datetime | None = None  # for states (half-open)
    motion: Literal["direct", "retrograde"] | None = None
    detail: dict[str, Any] = Field(default_factory=dict)
    profile_id: str


class FeatureResult(BaseModel):
    """One feature's output for one chart, with a feature-level status (M5)."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    feature_id: str
    params: tuple[tuple[str, Any], ...] = ()
    status: Status
    reason: Reason | None = None
    detail: str = ""
    facts: tuple[ChartFact, ...] = ()
    relations: tuple[Relation, ...] = ()
    periods: tuple[DashaPeriod, ...] = ()
    events: tuple[TransitEvent, ...] = ()
    provenance: dict[str, Any] = Field(default_factory=dict)

    def fact(self, kind: str, subject: str, frame: str | None = None,
             varga: str = "D1") -> ChartFact:
        for f in self.facts:
            if f.kind == kind and f.subject == subject and f.frame == frame and f.varga == varga:
                return f
        raise KeyError((kind, subject, frame, varga))
