"""The ephemeris interface the calculation service depends on."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, Protocol

from astro.calc.profile import CalcProfile

Body = Literal["sun", "moon", "mars", "mercury", "jupiter", "venus", "saturn", "rahu", "ketu"]
BODIES: tuple[Body, ...] = ("sun", "moon", "mars", "mercury", "jupiter", "venus", "saturn",
                            "rahu", "ketu")


@dataclass(frozen=True)
class BodyState:
    longitude: float   # sidereal, degrees [0, 360)
    latitude: float    # ecliptic, degrees
    speed: float       # degrees/day in longitude


@dataclass(frozen=True)
class EphemerisInfo:
    engine: str
    version: str
    files_sha256: dict[str, str]


@dataclass(frozen=True)
class Eclipse:
    kind: Literal["solar", "lunar"]
    jd_max: float
    eclipse_type: str          # total | annular | partial | hybrid | penumbral
    longitude: float           # sidereal longitude of the eclipsed luminary at maximum


class Ephemeris(Protocol):
    def info(self) -> EphemerisInfo: ...
    def body(self, body: Body, jd_ut: float, profile: CalcProfile) -> BodyState: ...
    def ayanamsa(self, jd_ut: float, profile: CalcProfile) -> float: ...
    def ascendant(self, jd_ut: float, lat: float, lon: float, profile: CalcProfile) -> float: ...
    def cusps(self, jd_ut: float, lat: float, lon: float,
              profile: CalcProfile) -> tuple[float, ...]: ...
    def rise_set(self, jd_ut: float, lat: float, lon: float, elevation_m: float,
                 kind: Literal["rise", "set"], profile: CalcProfile) -> float | None: ...
    def eclipses(self, jd_start: float, jd_end: float, profile: CalcProfile) -> list[Eclipse]: ...
    def delta_t_seconds(self, jd_ut: float) -> float: ...
