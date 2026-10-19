"""Swiss Ephemeris adapter: the only module that imports swisseph (design D6, calc-review M1).

- Swiss Ephemeris keeps global state, so every call sets the sidereal mode under a lock.
- It falls back to the Moshier model silently when a file is missing; every result's return
  flag is checked and a fallback raises `out_of_range` (design §7.1).
- Files listed in the profile must exist with the pinned SHA-256.
"""

from __future__ import annotations

import hashlib
import threading
from pathlib import Path
from typing import Literal

import swisseph as swe

from astro.calc.core.angles import norm360
from astro.calc.core.status import CalcError, Reason
from astro.calc.ephemeris.port import Body, BodyState, Eclipse, EphemerisInfo
from astro.calc.profile import CalcProfile

_LOCK = threading.RLock()
_CURRENT_PATH: list[str | None] = [None]  # the path this module last set (process-global state)

_SIDM = {
    "lahiri": swe.SIDM_LAHIRI,
    "raman": swe.SIDM_RAMAN,
    "krishnamurti": swe.SIDM_KRISHNAMURTI,
    "true_chitra": swe.SIDM_TRUE_CITRA,
}
_PLANETS = {
    "sun": swe.SUN, "moon": swe.MOON, "mars": swe.MARS, "mercury": swe.MERCURY,
    "jupiter": swe.JUPITER, "venus": swe.VENUS, "saturn": swe.SATURN,
}
_HSYS = {"whole_sign": b"W", "sripati": b"S"}
_RISE = {
    "hindu_rising": swe.BIT_HINDU_RISING,
    "upper_limb_refraction": 0,
}


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


class SwissEphemeris:
    def __init__(self, ephe_dir: Path, profile: CalcProfile) -> None:
        self._dir = Path(ephe_dir)
        shas: dict[str, str] = {}
        for f in profile.ephemeris.files:
            p = self._dir / f.name
            if not p.exists():
                raise CalcError(Reason.EPHEMERIS_UNAVAILABLE, f"missing ephemeris file {p}")
            actual = _sha256(p)
            if actual != f.sha256:
                raise CalcError(Reason.EPHEMERIS_UNAVAILABLE, f"{f.name}: SHA-256 {actual}")
            shas[f.name] = actual
        if swe.version != profile.ephemeris.version:
            raise CalcError(Reason.EPHEMERIS_UNAVAILABLE,
                            f"swisseph {swe.version} != profile {profile.ephemeris.version}")
        self._info = EphemerisInfo("swisseph", swe.version, shas)
        self._files = set(shas)
        self._path = str(self._dir.resolve())

    # -- helpers ----------------------------------------------------------------------------
    def _prepare(self, profile: CalcProfile, jd_ut: float) -> None:
        if profile.ephemeris.files and {f.name for f in profile.ephemeris.files} - self._files:
            raise CalcError(Reason.EPHEMERIS_UNAVAILABLE, "profile files not verified")
        if not profile.is_covered(jd_ut):
            c = profile.ephemeris.coverage
            raise CalcError(Reason.OUT_OF_RANGE,
                            f"JD {jd_ut} outside ephemeris coverage [{c.start_jd}, {c.end_jd})")
        if _CURRENT_PATH[0] != self._path:
            swe.set_ephe_path(self._path)  # closes open files: only when it changes
            _CURRENT_PATH[0] = self._path
        swe.set_sid_mode(_SIDM[profile.ayanamsa.id], 0, 0)  # cheap; other code may change it

    def _calc(self, jd_ut: float, code: int, flags: int, file_index: int | None):
        """calc_ut, then verify the file actually read is one we verified. Other code in the
        process can change the global ephemeris path; if it did, reset it and recompute."""
        used = ""
        for attempt in range(2):
            xx, ret = swe.calc_ut(jd_ut, code, flags)
            fell_back = not ret & swe.FLG_SWIEPH
            if file_index is None:
                if not fell_back:
                    return xx
            else:
                used = swe.get_current_file_data(file_index)[0]
                if not fell_back and used and str(Path(used).resolve().parent) == self._path:
                    return xx
            if attempt == 0:  # the global path may have been changed elsewhere: reset, retry
                swe.set_ephe_path(self._path)
                _CURRENT_PATH[0] = self._path
        self._check(ret, jd_ut)  # a fallback after the reset: genuinely out of range
        raise CalcError(Reason.EPHEMERIS_UNAVAILABLE, f"ephemeris file in use is {used!r}")

    @staticmethod
    def _flags(profile: CalcProfile) -> int:
        fl = swe.FLG_SWIEPH | swe.FLG_SPEED | swe.FLG_SIDEREAL
        if not profile.position.apparent:  # geometric: no light-time or aberration (G-C12)
            fl |= swe.FLG_TRUEPOS
        return fl

    @staticmethod
    def _check(retflag: int, jd_ut: float) -> None:
        if not retflag & swe.FLG_SWIEPH:
            raise CalcError(Reason.OUT_OF_RANGE,
                            f"Swiss Ephemeris fell back to another model at JD {jd_ut}")

    # -- port -------------------------------------------------------------------------------
    def info(self) -> EphemerisInfo:
        return self._info

    def body(self, body: Body, jd_ut: float, profile: CalcProfile) -> BodyState:
        with _LOCK:
            self._prepare(profile, jd_ut)
            if body in ("rahu", "ketu"):
                node = swe.MEAN_NODE if profile.nodes.model == "mean" else swe.TRUE_NODE
                # the mean node is analytic; the true node reads the Moon file
                xx = self._calc(jd_ut, node, self._flags(profile),
                                None if node == swe.MEAN_NODE else 1)
                lon, lat, speed = xx[0], xx[1], xx[3]
                if body == "ketu":
                    lon, lat = lon + 180.0, -lat
                return BodyState(norm360(lon), lat, speed)
            xx = self._calc(jd_ut, _PLANETS[body], self._flags(profile),
                            1 if body == "moon" else 0)
            return BodyState(norm360(xx[0]), xx[1], xx[3])

    def ayanamsa(self, jd_ut: float, profile: CalcProfile) -> float:
        with _LOCK:
            self._prepare(profile, jd_ut)
            fl = swe.FLG_SWIEPH | (0 if profile.ayanamsa.nutation else swe.FLG_NONUT)
            ret, aya = swe.get_ayanamsa_ex_ut(jd_ut, fl)
            self._check(ret, jd_ut)
            return aya

    def _houses(self, jd_ut: float, lat: float, lon: float, profile: CalcProfile):
        with _LOCK:
            self._prepare(profile, jd_ut)
            try:
                return swe.houses_ex(jd_ut, lat, lon, _HSYS[profile.house_system],
                                     swe.FLG_SIDEREAL)
            except swe.Error as e:
                raise CalcError(Reason.UNSUPPORTED_FEATURE, f"houses: {e}") from e

    def ascendant(self, jd_ut: float, lat: float, lon: float, profile: CalcProfile) -> float:
        return norm360(self._houses(jd_ut, lat, lon, profile)[1][0])

    def cusps(self, jd_ut: float, lat: float, lon: float,
              profile: CalcProfile) -> tuple[float, ...]:
        return tuple(norm360(c) for c in self._houses(jd_ut, lat, lon, profile)[0][:12])

    def rise_set(self, jd_ut: float, lat: float, lon: float, elevation_m: float,
                 kind: Literal["rise", "set"], profile: CalcProfile) -> float | None:
        """First sunrise or sunset at or after `jd_ut`; None if the Sun does not rise or set."""
        with _LOCK:
            self._prepare(profile, jd_ut)
            rsmi = (swe.CALC_RISE if kind == "rise" else swe.CALC_SET) | _RISE[
                profile.sunrise.definition]
            res, tret = swe.rise_trans(jd_ut, swe.SUN, rsmi, (lon, lat, elevation_m),
                                       0.0, 0.0, swe.FLG_SWIEPH)
            if res == -2:
                return None
            if res != 0:  # pragma: no cover - swisseph raises on fatal errors
                raise CalcError(Reason.TOOL_ERROR, f"rise_trans returned {res}")
            return tret[0]

    def eclipses(self, jd_start: float, jd_end: float, profile: CalcProfile) -> list[Eclipse]:
        out: list[Eclipse] = []
        with _LOCK:
            self._prepare(profile, jd_start)
            self._prepare(profile, jd_end)
            for kind in ("solar", "lunar"):
                t = jd_start
                while True:
                    if kind == "solar":
                        ret, tret = swe.sol_eclipse_when_glob(t, swe.FLG_SWIEPH, 0, False)
                    else:
                        ret, tret = swe.lun_eclipse_when(t, swe.FLG_SWIEPH, 0, False)
                    jd_max = tret[0]
                    if jd_max >= jd_end:
                        break
                    body = "sun" if kind == "solar" else "moon"
                    lon = self.body(body, jd_max, profile).longitude
                    out.append(Eclipse(kind, jd_max, _eclipse_type(ret, kind), lon))
                    t = jd_max + 1.0
        return sorted(out, key=lambda e: e.jd_max)

    def delta_t_seconds(self, jd_ut: float) -> float:
        with _LOCK:
            return swe.deltat(jd_ut) * 86400.0


def _eclipse_type(ret: int, kind: str) -> str:
    if ret & swe.ECL_TOTAL:
        return "total"
    if kind == "solar" and ret & swe.ECL_ANNULAR_TOTAL:
        return "hybrid"
    if kind == "solar" and ret & swe.ECL_ANNULAR:
        return "annular"
    if ret & swe.ECL_PARTIAL:
        return "partial"
    if kind == "lunar" and ret & swe.ECL_PENUMBRAL:
        return "penumbral"
    return "other"
