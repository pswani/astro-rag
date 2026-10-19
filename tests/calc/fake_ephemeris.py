"""A scriptable ephemeris for synthetic charts (calc-review M1: features depend on the port)."""

from __future__ import annotations

from collections.abc import Callable

from astro.calc.core.angles import norm360
from astro.calc.ephemeris.port import BODIES, BodyState, EphemerisInfo

H = 1e-4


class FakeEphemeris:
    """Each body's longitude is a function of JD; speed is a numerical derivative."""

    def __init__(self, lons: dict[str, Callable[[float], float]],
                 asc: Callable[[float], float] = lambda t: 15.0 + 360.0 * (t % 1.0)) -> None:
        self.lons = {b: lons.get(b, (lambda c: (lambda t: c))(10.0 + 30 * i))
                     for i, b in enumerate(BODIES)}
        if "rahu" in lons and "ketu" not in lons:
            self.lons["ketu"] = lambda t: lons["rahu"](t) + 180.0
        self.asc = asc

    def info(self) -> EphemerisInfo:
        return EphemerisInfo("fake", "0", {})

    def body(self, body, jd_ut, profile) -> BodyState:
        f = self.lons[body]
        speed = (f(jd_ut + H) - f(jd_ut - H)) / (2 * H)
        if body in ("rahu", "ketu") and speed == 0:
            speed = -0.05
        return BodyState(norm360(f(jd_ut)), 0.0, speed)

    def ayanamsa(self, jd_ut, profile) -> float:
        return 24.0

    def ascendant(self, jd_ut, lat, lon, profile) -> float:
        return norm360(self.asc(jd_ut))

    def cusps(self, jd_ut, lat, lon, profile):
        a = self.ascendant(jd_ut, lat, lon, profile)
        return tuple(norm360(a + 30 * i) for i in range(12))

    def rise_set(self, jd_ut, lat, lon, elevation_m, kind, profile):
        base = int(jd_ut) + (0.25 if kind == "rise" else 0.75)
        return base if base >= jd_ut else base + 1.0

    def eclipses(self, jd_start, jd_end, profile):
        return []

    def delta_t_seconds(self, jd_ut) -> float:
        return 0.0
