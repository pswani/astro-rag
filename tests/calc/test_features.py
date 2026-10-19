from datetime import UTC, datetime, timedelta

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from astro.calc.context import ChartContext, NormalizedBirth
from astro.calc.core.angles import houses_apart, sign_index
from astro.calc.core.status import Reason, Status
from astro.calc.core.timescale import jd_from_civil, jd_from_utc, utc_from_jd
from astro.calc.dasha.vimshottari import active_chain, periods_in, sandhi
from astro.calc.engine import FeatureRequest as R
from astro.calc.ephemeris.port import BODIES
from astro.calc.features.vargas import varga_sign
from astro.calc.registry import default_engine

from .fake_ephemeris import FakeEphemeris
from .helpers import ephemeris, profile, refdata

PUNE_JD = jd_from_civil(1985, 3, 14, 1.2)  # 06:42 IST, five minutes before sunrise


def ctx(jd=PUNE_JD, u=5.0, known=True, lat=18.52, lon=73.85, eph=None, prof=None):
    return ChartContext("chart:t", NormalizedBirth(jd, lat, lon, time_known=known,
                                                   uncertainty_minutes=u),
                        prof or profile(), eph or ephemeris(), refdata())


def run(c, *reqs):
    out = default_engine().run(c, list(reqs))
    return [out[r] for r in reqs]


# -- positions ---------------------------------------------------------------------------------

def test_positions_complete_and_typed():
    (pos,) = run(ctx(), R.of("positions"))
    assert pos.status is Status.OK
    for b in BODIES:
        for k in ("longitude", "sign", "nakshatra", "pada", "nakshatra_lord", "retrograde"):
            pos.fact(k, f"graha:{b}")
    assert pos.fact("retrograde", "graha:rahu").value is True  # mean node, profile "always"
    lagna = pos.fact("longitude", "lagna").value
    assert pos.fact("sign", "lagna").value == refdata().rashi_id(sign_index(lagna))


def test_unknown_time_makes_lagna_unknown_but_moon_assessed():
    (pos,) = run(ctx(u=720, known=False), R.of("positions"))
    for k in ("longitude", "sign", "nakshatra", "pada"):
        f = pos.fact(k, "lagna")
        assert f.value is None and f.sensitivity == "unknown"
    # the Moon moves ~13° in a day: its pada must not be presented as stable
    assert pos.fact("pada", "graha:moon").sensitivity == "sensitive"


def test_zero_uncertainty_is_stable():
    (pos,) = run(ctx(u=0), R.of("positions"))
    assert all(f.sensitivity == "stable" for f in pos.facts if f.value is not None)


def test_lagna_pada_boundary_margin():
    (pos,) = run(ctx(u=5), R.of("positions"))
    f = pos.fact("pada", "lagna")
    assert f.sensitivity == "sensitive" and 4.0 < f.margin_minutes[0] < 4.5


def test_cross_and_recross_near_station_is_sensitive():
    """CALC-7 acceptance: Mars turns 0.01° past 30°, then returns, inside [t − u, t + u]."""
    t0 = 2451545.0
    mars = lambda t: 30.005 - 0.4 * (t - t0) ** 2  # noqa: E731  peak at t0, above 30° for ±2.7 h
    c = ctx(jd=t0 + 0.2, u=12 * 60, eph=FakeEphemeris({"mars": mars}))
    (pos,) = run(c, R.of("positions"))
    f = pos.fact("sign", "graha:mars")
    assert f.sensitivity == "sensitive"
    assert f.value == "rashi:aries"  # at t0 + 0.2 d Mars is back below 30°


def test_out_of_range_is_feature_local():
    c = ctx(jd=jd_from_civil(1700, 1, 1))
    pos, pan = run(c, R.of("positions"), R.of("panchanga"))
    assert pos.status is Status.UNSUPPORTED and pos.reason is Reason.OUT_OF_RANGE
    assert pan.status is Status.UNSUPPORTED


# -- houses, relations, friendship -----------------------------------------------------------

def test_whole_sign_houses_and_frames():
    pos, houses = run(ctx(), R.of("positions"), R.of("houses"))
    ref = refdata()
    lagna_sign = ref.rashi_index(pos.fact("sign", "lagna").value)
    moon_sign = ref.rashi_index(pos.fact("sign", "graha:moon").value)
    for b in BODIES:
        s = ref.rashi_index(pos.fact("sign", f"graha:{b}").value)
        assert houses.fact("house", f"graha:{b}", frame="lagna").value == houses_apart(
            lagna_sign, s)
        if b != "moon":
            assert houses.fact("house", f"graha:{b}", frame="chandra").value == houses_apart(
                moon_sign, s)
    with pytest.raises(KeyError):
        houses.fact("house", "graha:moon", frame="chandra")
    assert houses.fact("house_sign", "bhava:1", frame="lagna").value == pos.fact(
        "sign", "lagna").value


def test_unknown_time_lagna_frame_unknown_chandra_known():
    (houses,) = run(ctx(u=720, known=False), R.of("houses"))
    assert houses.fact("house", "graha:sun", frame="lagna").value is None
    assert houses.fact("house", "graha:sun", frame="chandra").value is not None


def test_sripati_houses():
    p = profile().model_copy(update={"house_system": "sripati"})
    (houses,) = run(ctx(prof=p), R.of("houses", frames=("lagna",)))
    vals = [houses.fact("house", f"graha:{b}", frame="lagna").value for b in BODIES]
    assert all(1 <= v <= 12 for v in vals)


def test_relations():
    pos, rel = run(ctx(), R.of("positions"), R.of("relations"))
    ref = refdata()
    lagna_sign = ref.rashi_index(pos.fact("sign", "lagna").value)
    assert rel.fact("lord_of", "bhava:1", frame="lagna").value == ref.sign_lord(lagna_sign)
    occupants = [g for n in range(1, 13)
                 for g in rel.fact("occupants", f"bhava:{n}", frame="lagna").value]
    assert sorted(occupants) == sorted(f"graha:{b}" for b in BODIES)
    for b in BODIES:
        chain = rel.fact("dispositor_chain", f"graha:{b}").value
        term = rel.fact("dispositor_terminal", f"graha:{b}").value
        assert term in ("own_sign", "cycle")
        if term == "cycle":
            assert chain[-1] in chain[:-1] or chain[-1] == f"graha:{b}"


def test_parivartana_detected():
    fake = FakeEphemeris({"mars": lambda t: 45.0, "venus": lambda t: 15.0})  # Taurus / Aries
    (rel,) = run(ctx(eph=fake, u=0), R.of("relations"))
    pv = [r for r in rel.relations if r.kind == "parivartana"]
    assert [(r.source, r.target) for r in pv] == [("graha:mars", "graha:venus")]


def test_friendship():
    (fr,) = run(ctx(), R.of("friendship"))
    assert len(fr.relations) == 42 * 3
    by = {(r.system, r.source, r.target): r.value for r in fr.relations}
    for (system, a, b), v in by.items():
        if system == "temporal":
            assert by[("temporal", b, a)] == v  # 2/3/4/10/11/12 is symmetric
    assert by[("natural", "graha:saturn", "graha:sun")] == "enemy"
    assert set(v for (s, _, _), v in by.items() if s == "compound") <= {
        "great_friend", "friend", "neutral", "enemy", "great_enemy"}


# -- vargas ------------------------------------------------------------------------------------

@given(st.floats(0, 359.999999))
def test_d9_closed_form(lon):
    assert varga_sign(lon, refdata().varga_spec("D9")) == int(lon * 3 // 10) % 12


def test_d10_examples():
    d10 = refdata().varga_spec("D10")
    assert varga_sign(0.0, d10) == 0          # Aries (odd) starts from itself
    assert varga_sign(30.0, d10) == 9         # Taurus (even) starts from the 9th: Capricorn
    assert varga_sign(329.76, d10) == 7       # Aquarius 29.76° → Scorpio
    assert varga_sign(3.0, d10) == 1          # exactly on the part boundary → next part


def test_vargottama():
    fake = FakeEphemeris({"sun": lambda t: 1.0, "moon": lambda t: 5.0})
    (v,) = run(ctx(eph=fake, u=0), R.of("vargas"))
    assert v.fact("vargottama", "graha:sun").value is True     # Aries D9 part 1 = Aries
    assert v.fact("vargottama", "graha:moon").value is False   # Aries 5° → Taurus in D9


# -- panchanga ---------------------------------------------------------------------------------

def test_birth_before_sunrise_takes_previous_vara():
    """PAN-2 acceptance: 06:42 IST is before the 06:47 sunrise, so the vara is Wednesday."""
    (pan,) = run(ctx(), R.of("panchanga"))
    assert pan.fact("vara", "panchanga:vara").value == "vara:wednesday"
    assert pan.fact("sunrise", "panchanga:sunrise").value.startswith("1985-03-13T01:18")


def test_limb_intervals_contain_birth():
    (pan,) = run(ctx(), R.of("panchanga"))
    t = utc_from_jd(PUNE_JD)
    for limb in ("tithi", "karana", "nakshatra", "nitya_yoga"):
        start = datetime.fromisoformat(pan.fact("limb_start", f"panchanga:{limb}").value)
        end = datetime.fromisoformat(pan.fact("limb_end", f"panchanga:{limb}").value)
        assert start <= t < end
        assert end - start < timedelta(hours=27)


def test_polar_night_vara_unknown_limbs_known():
    c = ctx(jd=jd_from_civil(2020, 12, 15, 10), lat=69.65, lon=18.96)
    (pan,) = run(c, R.of("panchanga"))
    assert pan.status is Status.OK
    assert pan.fact("vara", "panchanga:vara").value is None
    assert pan.provenance["unavailable"]["vara"] == "no_sunrise"
    assert pan.fact("tithi", "panchanga:tithi").value.startswith("tithi:")


# -- Vimshottari -------------------------------------------------------------------------------

@pytest.fixture(scope="module")
def tree():
    (v,) = run(ctx(), R.of("vimshottari"))
    return v


def test_tree_tiles(tree):
    ps = tree.periods
    by_parent: dict = {}
    for p in ps:
        by_parent.setdefault(p.parent_id, []).append(p)
    mds = by_parent[None]
    birth = utc_from_jd(PUNE_JD)
    assert mds[0].start_utc <= birth < mds[0].end_utc
    assert mds[-1].end_utc >= birth + timedelta(days=120 * 365.2425)
    for group in by_parent.values():
        group.sort(key=lambda p: p.start_utc)
        assert all(a.end_utc == b.start_utc for a, b in zip(group, group[1:], strict=False))
    for p in ps:
        kids = by_parent.get(p.id)
        if kids:
            assert kids[0].start_utc == p.start_utc and kids[-1].end_utc == p.end_utc
            assert kids[0].lord == p.lord and len(kids) == 9


def test_first_md_is_moon_nakshatra_lord_with_balance(tree):
    pos = run(ctx(), R.of("positions"))[0]
    md = [p for p in tree.periods if p.level == "MD"][0]
    assert md.lord == pos.fact("nakshatra_lord", "graha:moon").value
    bal = tree.fact("dasha_balance", "dasha:vimshottari").value
    remaining = (md.end_utc - utc_from_jd(PUNE_JD)).total_seconds() / 86400 / 365.2425
    assert bal == pytest.approx(remaining, abs=1e-6)
    assert md.boundary_margin_days[0] > 0 > md.boundary_margin_days[1]


@settings(max_examples=40, deadline=None)
@given(st.integers(0, 120 * 365))
def test_active_chain_is_unique_containing_chain(tree, day):
    at = utc_from_jd(PUNE_JD) + timedelta(days=day, hours=7)
    chain = active_chain(tree.periods, at)
    assert [p.level for p in chain] == ["MD", "AD", "PD"]
    for p in chain:
        assert p.start_utc <= at < p.end_utc
    brute = [p for p in tree.periods if p.start_utc <= at < p.end_utc]
    assert sorted(p.id for p in brute) == sorted(p.id for p in chain)


def test_periods_in_matches_brute_force(tree):
    a = datetime(2026, 1, 1, tzinfo=UTC)
    b = datetime(2027, 6, 1, tzinfo=UTC)
    got = periods_in(tree.periods, a, b, levels=("AD", "PD"))
    brute = [p for p in tree.periods if p.level in ("AD", "PD") and p.start_utc < b
             and a < p.end_utc]
    assert sorted(p.id for p in got) == sorted(p.id for p in brute)
    with pytest.raises(ValueError):
        periods_in(tree.periods, b, a)


def test_sandhi_flags(tree):
    md = [p for p in tree.periods if p.level == "MD"][3]
    near = md.start_utc + timedelta(days=10)
    flags = sandhi(tree.periods, near, {"MD": 180, "AD": 15})
    assert flags["MD"][0] == md.start_utc and flags["MD"][1] == pytest.approx(10)
    far = md.start_utc + timedelta(days=400)
    assert sandhi(tree.periods, far, {"MD": 180})["MD"] is None


def test_dasha_active_feature():
    (act,) = run(ctx(), R.of("dasha_active", as_of="2026-10-19T00:00:00+00:00"))
    assert [p.level for p in act.periods] == ["MD", "AD", "PD"]
    assert {f.subject for f in act.facts} == {"dasha:vimshottari:MD", "dasha:vimshottari:AD"}
    (bad,) = run(ctx(), R.of("dasha_active", as_of="2300-01-01T00:00:00+00:00"))
    assert bad.reason is Reason.OUT_OF_RANGE


def test_depth_outside_profile_is_unsupported():
    (v,) = run(ctx(), R.of("vimshottari", depth=4))  # SD not in parashari_v1 levels
    assert v.status is Status.UNSUPPORTED and v.reason is Reason.UNSUPPORTED_FEATURE


def test_jd_from_utc_round_trip_for_periods(tree):
    p = tree.periods[0]
    assert utc_from_jd(jd_from_utc(p.start_utc)) == p.start_utc
