import shutil

import pytest
import swisseph as swe

from astro.calc.core.angles import norm360
from astro.calc.core.status import CalcError, Reason
from astro.calc.core.timescale import jd_from_civil, utc_from_jd
from astro.calc.ephemeris.swiss import SwissEphemeris

from .helpers import EPHE, ephemeris, profile

JD = jd_from_civil(1985, 3, 14, 1.2)
PUNE = (18.52, 73.85)


def test_planets_match_direct_swisseph():
    e, p = ephemeris(), profile()
    swe.set_ephe_path(str(EPHE))
    swe.set_sid_mode(swe.SIDM_LAHIRI)
    for name, code in [("sun", swe.SUN), ("moon", swe.MOON), ("saturn", swe.SATURN)]:
        xx, _ = swe.calc_ut(JD, code, swe.FLG_SWIEPH | swe.FLG_SPEED | swe.FLG_SIDEREAL)
        s = e.body(name, JD, p)
        assert s.longitude == pytest.approx(xx[0], abs=1e-12)
        assert s.speed == pytest.approx(xx[3], abs=1e-12)


def test_ketu_opposes_rahu():
    e, p = ephemeris(), profile()
    r, k = e.body("rahu", JD, p), e.body("ketu", JD, p)
    assert norm360(k.longitude - r.longitude) == pytest.approx(180.0, abs=1e-12)
    assert k.speed == r.speed and k.latitude == -r.latitude
    assert r.speed < 0  # mean node always moves backwards


def test_out_of_coverage_is_refused():
    with pytest.raises(CalcError) as e:
        ephemeris().body("sun", jd_from_civil(1500, 1, 1), profile())
    assert e.value.reason is Reason.OUT_OF_RANGE


def test_moshier_fallback_is_refused_even_if_coverage_is_wrong():
    p = profile()
    wide = p.model_copy(update={"ephemeris": p.ephemeris.model_copy(update={
        "coverage": p.ephemeris.coverage.model_copy(update={"start_jd": 0.0})})})
    with pytest.raises(CalcError) as e:
        ephemeris().body("sun", jd_from_civil(1500, 1, 1), wide)
    assert e.value.reason is Reason.OUT_OF_RANGE
    assert "fell back" in str(e.value)


def test_missing_or_altered_file_is_refused(tmp_path):
    for f in EPHE.iterdir():
        shutil.copy(f, tmp_path / f.name)
    (tmp_path / "seas_18.se1").unlink()
    with pytest.raises(CalcError) as e:
        SwissEphemeris(tmp_path, profile())
    assert e.value.reason is Reason.EPHEMERIS_UNAVAILABLE
    shutil.copy(EPHE / "seas_18.se1", tmp_path / "seas_18.se1")
    with (tmp_path / "sepl_18.se1").open("ab") as fh:
        fh.write(b"x")
    with pytest.raises(CalcError):
        SwissEphemeris(tmp_path, profile())


def test_ayanamsa_nutation_switch_and_positions_unaffected():
    p = profile()
    e = ephemeris()
    with_nut = e.ayanamsa(JD, p)
    p2 = p.model_copy(update={"ayanamsa": p.ayanamsa.model_copy(update={"nutation": False})})
    without = e.ayanamsa(JD, p2)
    assert 23.6 < with_nut < 23.7 and abs(with_nut - without) < 20 / 3600
    assert e.body("sun", JD, p).longitude == e.body("sun", JD, p2).longitude


def test_ascendant_and_cusps():
    e, p = ephemeris(), profile()
    asc = e.ascendant(JD, *PUNE, p)
    cusps = e.cusps(JD, *PUNE, p)
    assert cusps[0] == pytest.approx(asc // 30 * 30)  # whole-sign cusps start the sign
    sri = e.cusps(JD, *PUNE, p.model_copy(update={"house_system": "sripati"}))
    assert len(sri) == 12 and len(set(round(c, 6) for c in sri)) == 12


def test_sunrise_pune_and_polar_night():
    e, p = ephemeris(), profile()
    rise = e.rise_set(jd_from_civil(1985, 3, 14, 0), *PUNE, 0.0, "rise", p)
    t = utc_from_jd(rise)
    assert (t.hour, t.minute) == (1, 17)  # 06:47 IST
    sset = e.rise_set(rise, *PUNE, 0.0, "set", p)
    assert 0.45 < sset - rise < 0.55
    tromso = (69.65, 18.96)
    assert e.rise_set(jd_from_civil(2020, 12, 15, 0), *tromso, 0.0, "rise", p) is None


def test_known_eclipses():
    e, p = ephemeris(), profile()
    ecl = e.eclipses(jd_from_civil(2024, 1, 1), jd_from_civil(2025, 12, 31), p)
    solar = [x for x in ecl if x.kind == "solar" and x.eclipse_type == "total"]
    lunar = [x for x in ecl if x.kind == "lunar" and x.eclipse_type == "total"]
    assert utc_from_jd(solar[0].jd_max).strftime("%Y-%m-%d %H") == "2024-04-08 18"
    assert utc_from_jd(lunar[0].jd_max).strftime("%Y-%m-%d %H") == "2025-03-14 06"
    assert all(a.jd_max <= b.jd_max for a, b in zip(ecl, ecl[1:], strict=False))


def test_delta_t_recorded():
    assert 50 < ephemeris().delta_t_seconds(JD) < 60  # ~54.6 s in 1985
