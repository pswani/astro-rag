from datetime import UTC, datetime

import pytest

from astro.calc.context import ChartContext, NormalizedBirth
from astro.calc.core.angles import houses_apart, sign_index
from astro.calc.core.status import Reason, Status
from astro.calc.core.timescale import jd_from_civil, jd_from_utc
from astro.calc.engine import FeatureRequest as R
from astro.calc.registry import default_engine
from astro.methods.bnn.features import features as bnn_features

from .fake_ephemeris import FakeEphemeris
from .helpers import ephemeris, profile, refdata

PUNE_JD = jd_from_civil(1985, 3, 14, 1.2)
W = {"start": "2026-01-01T00:00:00+00:00", "end": "2028-01-01T00:00:00+00:00"}


def ctx(jd=PUNE_JD, u=5.0, known=True, eph=None, prof=None, inputs=None):
    return ChartContext("chart:t", NormalizedBirth(jd, 18.52, 73.85, time_known=known,
                                                   uncertainty_minutes=u),
                        prof or profile(), eph or ephemeris(), refdata(), inputs or {})


def run(c, *reqs):
    out = default_engine(extra=bnn_features()).run(c, list(reqs))
    return [out[r] for r in reqs]


def test_transit_positions_relative_to_natal():
    natal, tr = run(ctx(), R.of("positions"),
                    R.of("transit_positions", as_of="2026-10-19T00:00:00+00:00"))
    ref = refdata()
    sat_sign = ref.rashi_index(tr.fact("sign", "graha:saturn", frame="transit").value)
    moon_sign = ref.rashi_index(natal.fact("sign", "graha:moon").value)
    assert tr.fact("transit_house", "graha:saturn", frame="natal_chandra").value == \
        houses_apart(moon_sign, sat_sign)
    d = tr.fact("transit_distance", "graha:saturn", frame="natal:graha:mercury").value
    assert -180 < d <= 180


def test_transit_house_from_lagna_unknown_without_time():
    (tr,) = run(ctx(u=720, known=False),
                R.of("transit_positions", as_of="2026-10-19T00:00:00+00:00"))
    assert tr.fact("transit_house", "graha:saturn", frame="natal_lagna").value is None
    assert tr.fact("transit_house", "graha:saturn", frame="natal_chandra").value is not None


def test_retrograde_loop_gives_all_three_crossings_of_a_natal_point():
    """TRN-2 acceptance on real data: Saturn over natal Mercury in 2026–27."""
    (ev,) = run(ctx(), R.of("transit_events", bodies=("saturn",), **W))
    hits = [e for e in ev.events if e.kind == "conjunction" and e.target == "graha:mercury"]
    assert [e.motion for e in hits] == ["direct", "retrograde", "direct"]
    stations = [e for e in ev.events if e.kind == "station"]
    assert [e.detail["turns"] for e in stations][:2] == ["retrograde", "direct"]
    assert stations[0].start_utc.date().isoformat() in ("2026-07-26", "2026-07-27")
    # events are ordered and each ingress lands on its boundary
    assert all(a.start_utc <= b.start_utc for a, b in zip(ev.events, ev.events[1:],
                                                          strict=False))


def test_ingress_times_are_on_the_boundary():
    (ev,) = run(ctx(), R.of("transit_events", bodies=("jupiter",), kinds=("sign", "pada"),
                            **W))
    eph, prof = ephemeris(), profile()
    for e in ev.events:
        lon = eph.body("jupiter", jd_from_utc(e.start_utc), prof).longitude
        width = 30.0 if e.detail["ingress"] == "sign" else 10 / 3
        assert min(lon % width, width - lon % width) < 1e-4
    assert any(e.detail["ingress"] == "pada" for e in ev.events)


def test_window_limits_and_bad_windows():
    long = {"start": "2026-01-01T00:00:00+00:00", "end": "2028-06-01T00:00:00+00:00"}
    (moon,) = run(ctx(), R.of("transit_events", bodies=("moon",), kinds=("sign",), **long))
    assert moon.status is Status.UNSUPPORTED and moon.reason is Reason.UNSUPPORTED_WINDOW
    huge = {"start": "2026-01-01T00:00:00+00:00", "end": "2035-01-01T00:00:00+00:00"}
    (sat,) = run(ctx(), R.of("transit_events", bodies=("saturn",), **huge))
    assert sat.reason is Reason.UNSUPPORTED_WINDOW
    (inv,) = run(ctx(), R.of("transit_events", start=W["end"], end=W["start"]))
    assert inv.reason is Reason.UNSUPPORTED_WINDOW
    (naive,) = run(ctx(), R.of("transit_events", start="2026-01-01T00:00:00", end=W["end"]))
    assert naive.reason is Reason.MISSING_INPUT


def test_contact_when_a_planet_turns_back_short_of_a_natal_point():
    t0 = 2461041.5  # 2026-01-01
    # Saturn rises to a maximum of 99.6° at t0 + 100 d, natal Sun at 100°: no crossing
    sat = lambda t: 99.6 - 1e-4 * (t - t0 - 100) ** 2  # noqa: E731
    fake = FakeEphemeris({"saturn": sat, "sun": lambda t: 100.0, "mercury": lambda t: 200.0})
    (ev,) = run(ctx(jd=t0 - 5000, u=0, eph=fake),
                R.of("transit_events", bodies=("saturn",), kinds=("conjunction",),
                     contact_orb_deg=1.0, **W))
    contact = [e for e in ev.events if e.kind == "contact"]
    assert [(e.target, round(e.detail["distance_deg"], 3)) for e in contact] == [
        ("graha:sun", 0.4)]


def test_named_states_sade_sati_phases():
    t0 = 2461041.5
    fake = FakeEphemeris({"saturn": lambda t: 285.0 + 0.1 * (t - t0),  # Capricorn → Aries
                          "moon": lambda t: 305.0})                   # natal Moon in Aquarius
    window = {"start": "2026-01-01T00:00:00+00:00", "end": "2030-12-01T00:00:00+00:00"}
    (st,) = run(ctx(jd=t0 - 5000, u=0, eph=fake), R.of("transit_states", **window))
    phases = [(e.detail["phase"], e.start_utc.date().isoformat())
              for e in st.events if e.target == "state:sade_sati_phase"]
    assert [p for p, _ in phases] == ["rising", "peak", "setting"]
    sade = [e for e in st.events if e.target == "state:sade_sati"]
    assert len(sade) == 1 and sade[0].detail["clipped_start"]
    # 0.1°/day: Aquarius at 300° is reached 150 days after t0, Pisces at 330° after 450
    assert phases[1][1] == "2026-05-31" and phases[2][1] == "2027-03-27"


def test_eclipses_with_natal_contacts():
    (ec,) = run(ctx(), R.of("eclipses", start="2024-01-01T00:00:00+00:00",
                            end="2025-12-31T00:00:00+00:00"))
    solar = [e for e in ec.events if e.detail["eclipse"] == "solar"
             and e.detail["type"] == "total"]
    assert solar[0].start_utc.date().isoformat() == "2024-04-08"
    for e in ec.events:
        assert all(h["distance_deg"] <= e.detail["orb_deg"] for h in e.detail["contacts"])


# -- BNN ---------------------------------------------------------------------------------------

def bnn_ctx(lons, **kw):
    return ctx(eph=FakeEphemeris(lons), u=0, prof=profile("bnn_v1"), **kw)


def test_bnn_links_and_retro_variant():
    t0 = 2451545.0
    lons = {"jupiter": lambda t: 10.0,                      # Aries
            "saturn": lambda t: 130.0,                      # Leo: 5th from Aries
            "mars": lambda t: 32.0 - 0.3 * (t - t0),        # Taurus, retrograde
            "venus": lambda t: 190.0}                       # Libra: 7th from Aries
    (rel,) = run(bnn_ctx(lons, jd=t0), R.of("bnn_relations"))
    links = {(r.source, r.target, r.value): r.provenance["via"] for r in rel.relations
             if r.kind == "bnn_link"}
    assert links[("graha:jupiter", "graha:saturn", 5)] == "sign"
    assert links[("graha:jupiter", "graha:venus", 7)] == "sign"
    assert links[("graha:jupiter", "graha:mars", 2)] == "sign"
    # retrograde Mars also counts in Aries: conjunct Jupiter through the variant
    assert links[("graha:jupiter", "graha:mars", 1)] == "retro_previous_sign"
    (plain,) = run(ctx(eph=FakeEphemeris(lons), u=0, jd=t0), R.of("bnn_relations"))
    assert ("graha:jupiter", "graha:mars", 1) not in {
        (r.source, r.target, r.value) for r in plain.relations}


def test_bnn_karakas_and_native_gender_optional():
    (k,) = run(bnn_ctx({}), R.of("bnn_karakas"))
    assert k.fact("karaka_role", "graha:saturn", frame="bnn").value == (
        "karaka_role:bnn.karma", "karaka_role:bnn.career")
    assert k.fact("native_karaka", "native", frame="bnn").value is None
    (k2,) = run(bnn_ctx({}, inputs={"native_gender": "female"}), R.of("bnn_karakas"))
    assert k2.fact("native_karaka", "native", frame="bnn").value == "graha:venus"


def test_bnn_triggers():
    """TRN-6: Jupiter entering a trine to natal Venus is a trigger."""
    (tr,) = run(ctx(), R.of("bnn_triggers", **W))
    natal = run(ctx(), R.of("positions"))[0]
    ref = refdata()
    for e in tr.events:
        natal_sign = ref.rashi_index(natal.fact("sign", e.target).value)
        entered = ref.rashi_index(e.detail["entered"])
        assert houses_apart(natal_sign, entered) in (1, 5, 9)
    assert {e.body for e in tr.events} <= {"graha:jupiter", "graha:saturn", "graha:rahu",
                                           "graha:ketu"}
    assert tr.events


def test_transit_sign_index_matches_position():
    (tr,) = run(ctx(), R.of("transit_positions", as_of=datetime(2026, 10, 19, tzinfo=UTC)
                            .isoformat()))
    lon = tr.fact("longitude", "graha:jupiter", frame="transit").value
    assert tr.fact("sign", "graha:jupiter", frame="transit").value == refdata().rashi_id(
        sign_index(lon))


@pytest.mark.parametrize("feature", ["transit_states", "eclipses", "bnn_triggers"])
def test_window_features_need_a_window(feature):
    (r,) = run(ctx(), R.of(feature))
    assert r.reason is Reason.MISSING_INPUT
