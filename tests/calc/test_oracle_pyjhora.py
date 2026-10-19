"""Convention cross-check against PyJHora (test-only oracle, AGPL; design D6, B7.2).

PyJHora calls the same Swiss Ephemeris, so this checks conventions (sidereal flags, indexing,
varga and dasha logic), not raw astronomy. Settings are matched to PyJHora's defaults: true
geometric positions (FLG_TRUEPOS), the true node (const._RAHU = SE_TRUE_NODE) and a
365.256364-day dasha year. Tolerances are NFR-1:
planets ≤ 10″, Lagna ≤ 30″, dasha boundaries ≤ 2 days.
"""

from __future__ import annotations

import contextlib
import io

import pytest

from astro.calc.context import ChartContext, NormalizedBirth
from astro.calc.core.angles import signed_diff
from astro.calc.core.timescale import jd_from_civil, jd_from_utc
from astro.calc.engine import FeatureRequest as R
from astro.calc.registry import default_engine

from .helpers import ephemeris, profile, refdata

with contextlib.redirect_stdout(io.StringIO()):
    drik = pytest.importorskip("jhora.panchanga.drik")
    from jhora import const, utils
    from jhora.horoscope.chart import charts
    from jhora.horoscope.dhasa.graha import vimsottari

pytestmark = pytest.mark.oracle

# (name, lat, lon, tz hours, (y, m, d), (h, m, s))
CHARTS = [
    ("pune", 18.52, 73.85, 5.5, (1985, 3, 14), (6, 42, 0)),
    ("chennai", 13.08, 80.27, 5.5, (1962, 8, 27), (23, 55, 0)),
    ("delhi", 28.61, 77.21, 5.5, (2001, 1, 1), (0, 5, 0)),
    ("new_york", 40.71, -74.01, -5.0, (1975, 12, 2), (14, 30, 0)),
    ("sydney", -33.87, 151.21, 10.0, (1990, 7, 15), (4, 10, 0)),
    ("london", 51.51, -0.13, 0.0, (1850, 11, 30), (19, 0, 0)),
    ("sao_paulo", -23.55, -46.63, -3.0, (2015, 2, 20), (12, 0, 0)),
    ("tokyo", 35.68, 139.69, 9.0, (2120, 5, 5), (5, 55, 0)),
]

BODY_CODES = [("sun", const._SUN), ("moon", const._MOON), ("mars", const._MARS),
              ("mercury", const._MERCURY), ("jupiter", const._JUPITER),
              ("venus", const._VENUS), ("saturn", const._SATURN), ("rahu", const._RAHU),
              ("ketu", const._KETU)]
ARCSEC = 1 / 3600


def matched_profile():
    p = profile()
    return p.model_copy(update={
        "position": p.position.model_copy(update={"apparent": False}),
        "nodes": p.nodes.model_copy(update={"model": "true", "retrograde": "by_speed"}),
        "dasha": p.dasha.model_copy(update={"year_days": const.sidereal_year}),
    })


def run(chart):
    name, lat, lon, tz, dob, tob = chart
    place = drik.Place(name, lat, lon, tz)
    jd_local = utils.julian_day_number(dob, tob)
    jd_ut = jd_local - tz / 24.0
    prof = matched_profile()
    ctx = ChartContext(f"chart:{name}", NormalizedBirth(jd_ut, lat, lon), prof, ephemeris(),
                       refdata())
    reqs = {k: R.of(k) for k in ("positions", "panchanga", "vimshottari")}
    reqs["vargas"] = R.of("vargas", vargas=("D1", "D9", "D10"))
    out = default_engine().run(ctx, list(reqs.values()))
    drik.set_ayanamsa_mode("LAHIRI")
    return place, jd_local, jd_ut, {k: out[v] for k, v in reqs.items()}


@pytest.fixture(scope="module", params=CHARTS, ids=[c[0] for c in CHARTS])
def chart(request):
    with contextlib.redirect_stdout(io.StringIO()):
        return run(request.param)


def test_positions_within_10_arcsec(chart):
    place, jd_local, jd_ut, res = chart
    pos = res["positions"]
    for name, code in BODY_CODES:
        ours = pos.fact("longitude", f"graha:{name}").value
        theirs = drik.sidereal_longitude(jd_ut, code)
        assert abs(signed_diff(ours, theirs)) <= 10 * ARCSEC, name


def test_lagna_within_30_arcsec(chart):
    place, jd_local, jd_ut, res = chart
    sign, deg, nak, pada = drik.ascendant(jd_local, place)[:4]
    ours = res["positions"].fact("longitude", "lagna").value
    assert abs(signed_diff(ours, sign * 30 + deg)) <= 30 * ARCSEC
    assert res["positions"].fact("pada", "lagna").value == pada


def test_panchanga_limbs(chart):
    place, jd_local, jd_ut, res = chart
    pan = res["panchanga"]
    ref = refdata()
    assert pan.fact("tithi", "panchanga:tithi").value == ref.tithi_id(
        drik.tithi(jd_local, place)[0] - 1)
    assert pan.fact("nakshatra", "panchanga:nakshatra").value == ref.nakshatra_id(
        drik.nakshatra(jd_local, place)[0] - 1)
    assert pan.fact("nitya_yoga", "panchanga:nitya_yoga").value == ref.nitya_yoga_id(
        drik.yogam(jd_local, place)[0] - 1)
    assert pan.fact("karana", "panchanga:karana").value == ref.karana_id(
        drik.karana(jd_local, place)[0] - 1)
    assert pan.fact("vara", "panchanga:vara").value == ref.vara(drik.vaara(jd_local, place))[0]


# PyJHora's own planet order (0 = Sun … 8 = Ketu), used by its chart and dasha functions
JHORA_ORDER = ["sun", "moon", "mars", "mercury", "jupiter", "venus", "saturn", "rahu", "ketu"]


@pytest.mark.parametrize("factor", [9, 10])
def test_varga_signs(chart, factor):
    """chart_method=1 is "Traditional Parasara", our declared construction. (drik.dhasavarga
    uses the cyclic parivritti formula, which differs from Parashari D10.)"""
    place, jd_local, jd_ut, res = chart
    with contextlib.redirect_stdout(io.StringIO()):
        theirs = charts.divisional_chart(jd_local, place, divisional_chart_factor=factor,
                                         chart_method=1)
    for planet, (sign, _deg) in theirs:
        subj = "lagna" if planet == "L" else f"graha:{JHORA_ORDER[planet]}"
        if planet not in ("L", *range(9)):
            continue
        ours = res["vargas"].fact("varga_sign", subj, varga=f"D{factor}").value
        assert ours == refdata().rashi_id(sign), (subj, factor)


def test_vimshottari_ad_starts_match(chart):
    """PyJHora's default is the *true* sidereal year (measured per chart); a fixed-length year
    is our convention, so the oracle is run with its mean sidereal year. Agreement is then
    exact; NFR-1 only requires 2 days."""
    place, jd_local, jd_ut, res = chart
    with contextlib.redirect_stdout(io.StringIO()):
        _, theirs = vimsottari.get_vimsottari_dhasa_bhukthi(
            jd_local, place, dhasa_level_index=2,
            dhasa_duration_type=const.DHASA_YEAR_DURATION.MEAN_SIDEREAL_YEAR)
    ours = [p for p in res["vimshottari"].periods if p.level == "AD"]
    assert len(theirs) >= 81
    for (lords, (y, m, d, h), _dur), mine in zip(theirs, ours, strict=False):
        assert mine.lord == f"graha:{JHORA_ORDER[lords[-1]]}"
        their_start = jd_from_civil(y, m, d, h) - place.timezone / 24.0
        assert abs(jd_from_utc(mine.start_utc) - their_start) <= 1 / 1440
