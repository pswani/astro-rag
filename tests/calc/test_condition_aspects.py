"""D1–D4: place provenance, Placidus, condition (CALC-2), aspects and conjunctions (REL-1)."""

import pytest

from astro.calc.context import ChartContext, NormalizedBirth
from astro.calc.core.status import Status
from astro.calc.core.timescale import jd_from_civil
from astro.calc.engine import FeatureRequest as R
from astro.calc.features.condition import dignity_of
from astro.calc.registry import default_engine

from .fake_ephemeris import FakeEphemeris
from .helpers import ephemeris, profile, refdata

PUNE_JD = jd_from_civil(1985, 3, 14, 1.2)
T0 = 2451545.0


def ctx(eph=None, prof=None, u=0.0, jd=T0, lat=18.52, lon=73.85, known=True):
    return ChartContext("chart:a", NormalizedBirth(jd, lat, lon, time_known=known,
                                                   uncertainty_minutes=u),
                        prof or profile(), eph or ephemeris(), refdata())


def run(c, *reqs):
    out = default_engine().run(c, list(reqs))
    return [out[r] for r in reqs]


def variant(**changes):
    p = profile()
    upd = {}
    for dotted, value in changes.items():
        section, field = dotted.split("__")
        upd[section] = getattr(p, section).model_copy(update={field: value})
    return p.model_copy(update=upd)


# -- dignity -----------------------------------------------------------------------------------

@pytest.mark.parametrize("graha,lon,expected", [
    ("moon", 31.0, "exalted"), ("moon", 40.0, "moolatrikona"),          # Taurus 1°, 10°
    ("mercury", 160.0, "exalted"), ("mercury", 167.0, "moolatrikona"),  # Virgo 10°, 17°
    ("mercury", 175.0, "own"), ("mercury", 70.0, "own"),                # Virgo 25°, Gemini
    ("sun", 125.0, "moolatrikona"), ("sun", 145.0, "own"),              # Leo 5°, 25°
    ("sun", 10.0, "exalted"), ("sun", 190.0, "debilitated"),
    ("saturn", 15.0, "debilitated"), ("mars", 5.0, "moolatrikona"), ("mars", 215.0, "own"),
    ("jupiter", 95.0, "exalted"), ("venus", 355.0, "exalted"), ("venus", 170.0, "debilitated"),
])
def test_dignity_rules(graha, lon, expected):
    assert dignity_of(ctx(), f"graha:{graha}", lon, "friend") == expected


def test_dignity_falls_back_to_the_lord_relationship_and_nodes_unknown():
    assert dignity_of(ctx(), "graha:sun", 75.0, "great_friend") == "great_friend"
    (c,) = run(ctx(eph=ephemeris(), jd=PUNE_JD), R.of("condition"))
    assert c.fact("dignity", "graha:rahu").value is None
    assert c.fact("dignity", "graha:saturn").value == "dignity:great_enemy"
    assert c.fact("dignity", "graha:venus").value == "dignity:exalted"


def test_natural_friendship_basis():
    p = variant(dignity__friendship_basis="natural")
    (c,) = run(ctx(eph=ephemeris(), jd=PUNE_JD, prof=p), R.of("condition"))
    assert c.fact("dignity", "graha:saturn").value == "dignity:enemy"  # no "great_" grades


# -- combustion, graha yuddha, gandanta, sandhi --------------------------------------------------

def test_combustion_uses_the_retrograde_orb():
    direct = FakeEphemeris({"sun": lambda t: 100.0, "mercury": lambda t: 113.0 + 0.1 * (t - T0)})
    retro = FakeEphemeris({"sun": lambda t: 100.0, "mercury": lambda t: 113.0 - 0.1 * (t - T0)})
    (d,) = run(ctx(eph=direct), R.of("condition"))
    (r,) = run(ctx(eph=retro), R.of("condition"))
    assert d.fact("combust", "graha:mercury").value is True     # 13° ≤ 14°
    assert r.fact("combust", "graha:mercury").value is False    # 13° > 12° when retrograde
    assert d.fact("combust", "graha:sun").value is False
    assert d.fact("sun_distance", "graha:mercury").value == pytest.approx(13.0)


def test_combustion_edge_inside_uncertainty_is_sensitive():
    eph = FakeEphemeris({"sun": lambda t: 100.0, "mars": lambda t: 116.95 + 2.0 * (t - T0)})
    (c,) = run(ctx(eph=eph, u=60), R.of("condition"))
    f = c.fact("combust", "graha:mars")
    assert f.value is True and f.sensitivity == "sensitive"  # reaches 17° within 36 min
    assert 30 < f.margin_minutes[1] < 40


@pytest.mark.parametrize("rule,winner", [("north_latitude", "graha:mars"),
                                         ("lesser_longitude", "graha:mars")])
def test_graha_yuddha(rule, winner):
    eph = FakeEphemeris({"mars": lambda t: 50.0, "venus": lambda t: 50.6})
    (c,) = run(ctx(eph=eph, prof=variant(graha_yuddha__winner=rule)), R.of("condition"))
    wars = [r for r in c.relations if r.kind == "graha_yuddha"]
    assert [(w.source, w.target) for w in wars] == [(winner, "graha:venus")]
    assert c.fact("graha_yuddha", "graha:venus").value == "loser"
    assert c.fact("graha_yuddha", "graha:jupiter").value == "none"


def test_gandanta_and_sandhi():
    eph = FakeEphemeris({"moon": lambda t: 118.5, "sun": lambda t: 30.4, "mars": lambda t: 45.0})
    (c,) = run(ctx(eph=eph), R.of("condition"))
    assert c.fact("gandanta", "graha:moon").value is True        # Cancer 28.5°: near 120°
    assert c.fact("rashi_sandhi", "graha:moon").value is False   # 1.5° from the boundary
    assert c.fact("rashi_sandhi", "graha:sun").value is True     # Taurus 0.4°
    assert c.fact("gandanta", "graha:mars").value is False
    unknown = run(ctx(eph=eph, known=False, u=720), R.of("condition"))[0]
    assert unknown.fact("gandanta", "lagna").value is None


# -- aspects and conjunctions -------------------------------------------------------------------

def test_special_aspects_and_houses():
    eph = FakeEphemeris({"mars": lambda t: 10.0, "saturn": lambda t: 100.0,
                         "jupiter": lambda t: 190.0, "sun": lambda t: 280.0,
                         "moon": lambda t: 310.0}, asc=lambda t: 5.0)
    (a,) = run(ctx(eph=eph), R.of("aspects"))
    ref = refdata()
    signs = lambda s: [ref.rashi_index(x) for x in a.fact("aspects_signs", s, frame="rashi").value]  # noqa: E731,E501
    assert signs("graha:mars") == [3, 6, 7]       # Aries → Cancer, Libra, Scorpio
    assert signs("graha:jupiter") == [10, 0, 2]   # Libra → Aquarius, Aries, Gemini
    assert signs("graha:saturn") == [5, 9, 0]     # Cancer → Virgo, Capricorn, Aries
    assert signs("graha:rahu") == []              # node aspects off by default
    assert set(a.fact("aspected_by", "graha:mars", frame="rashi").value) == {
        "graha:jupiter", "graha:saturn"}
    assert "graha:mars" in a.fact("aspected_by", "bhava:4", frame="lagna").value


def test_node_aspects_variant():
    (a,) = run(ctx(prof=variant(aspects__nodes="fifth_seventh_ninth")), R.of("aspects"))
    assert len(a.fact("aspects_signs", "graha:rahu", frame="rashi").value) == 3


def test_conjunction_modes():
    eph = FakeEphemeris({"mars": lambda t: 29.0, "venus": lambda t: 31.0,
                         "jupiter": lambda t: 33.0, "sun": lambda t: 200.0,
                         "moon": lambda t: 230.0})
    (same,) = run(ctx(eph=eph), R.of("aspects"))
    assert same.fact("conjunct_with", "graha:mars", frame="rashi").value == ()
    assert same.fact("conjunct_with", "graha:venus", frame="rashi").value == ("graha:jupiter",)
    p = profile().model_copy(update={"conjunction": profile().conjunction.model_copy(
        update={"mode": "orb", "orb_deg": 3.0})})
    (orb,) = run(ctx(eph=eph, prof=p), R.of("aspects"))
    assert orb.fact("conjunct_with", "graha:mars", frame="rashi").value == ("graha:venus",)


def test_conjunction_orb_is_required_for_orb_mode():
    from pydantic import ValidationError

    from astro.calc.profile import Conjunction
    with pytest.raises(ValidationError):
        Conjunction(mode="orb")
    with pytest.raises(ValidationError):
        Conjunction(mode="same_sign", orb_deg=5)


# -- Placidus, place provenance ---------------------------------------------------------------

def test_placidus_and_polar_latitudes():
    p = profile().model_copy(update={"house_system": "placidus"})
    pos, h = run(ctx(prof=p, jd=PUNE_JD), R.of("positions"), R.of("houses", frames=("lagna",)))
    assert all(1 <= h.fact("house", f"graha:{b}", frame="lagna").value <= 12
               for b in ("sun", "moon", "saturn"))
    pos, h = run(ctx(prof=p, jd=PUNE_JD, lat=70.0, lon=19.0), R.of("positions"),
                 R.of("houses", frames=("lagna", "chandra")))
    assert pos.fact("sign", "lagna").value is not None   # the Lagna never needs cusps
    assert h.status is Status.OK
    assert h.fact("house", "graha:sun", frame="lagna").value is None
    assert h.fact("house", "graha:sun", frame="chandra").value is not None
    assert "placidus" in h.provenance["unavailable"]["lagna"]


def test_place_provenance_is_recorded():
    from datetime import time

    from astro.normalize.birth import BirthInput, normalize_birth
    n = normalize_birth(BirthInput(year=1985, month=3, day=14, local_time=time(6, 42),
                                   latitude=18.52, longitude=73.85, timezone="Asia/Kolkata"))
    assert n.provenance["place"]["source"] == "coordinates"
    n2 = normalize_birth(BirthInput(year=1985, month=3, day=14, latitude=18.52, longitude=73.85,
                                    timezone="Asia/Kolkata",
                                    place_provenance={"source": "gazetteer", "query": "Pune"}))
    assert n2.provenance["place"]["query"] == "Pune"
