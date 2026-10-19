"""D5–D8: double transit and node axis, period-lord context, method adapters, vargas."""

import pytest
from hypothesis import given
from hypothesis import strategies as st

from astro.calc.context import ChartContext, NormalizedBirth
from astro.calc.core.status import CalcError, Reason, Status
from astro.calc.core.timescale import jd_from_civil
from astro.calc.engine import FeatureRequest as R
from astro.calc.features.vargas import varga_sign
from astro.calc.registry import default_engine
from astro.methods.base import MethodRegistry

from .fake_ephemeris import FakeEphemeris
from .helpers import ROOT, ephemeris, profile, refdata

PUNE_JD = jd_from_civil(1985, 3, 14, 1.2)
T0 = 2461041.5  # 2026-01-01
W = {"start": "2026-01-01T00:00:00+00:00", "end": "2027-01-01T00:00:00+00:00"}


def ctx(eph=None, jd=PUNE_JD, u=5.0):
    return ChartContext("chart:s", NormalizedBirth(jd, 18.52, 73.85, uncertainty_minutes=u),
                        profile(), eph or ephemeris(), refdata())


def run(c, *reqs):
    out = default_engine().run(c, list(reqs))
    return [out[r] for r in reqs]


def test_double_transit_on_a_synthetic_sky():
    # Jupiter fixed in Aries (aspects Leo 5th, Libra 7th, Sagittarius 9th); Saturn fixed in
    # Aquarius (aspects Aries 3rd, Leo 7th, Scorpio 10th): both reach Aries and Leo.
    eph = FakeEphemeris({"jupiter": lambda t: 10.0, "saturn": lambda t: 310.0,
                         "moon": lambda t: 125.0})
    (st_,) = run(ctx(eph=eph, jd=T0 - 9000, u=0), R.of("transit_states", **W))
    dt = {e.detail["sign"]: e for e in st_.events if e.target == "state:double_transit"}
    assert set(dt) == {"rashi:aries", "rashi:leo"}
    assert dt["rashi:leo"].detail["house_from_moon"] == 1
    ids = [e.id for e in st_.events]
    assert len(ids) == len(set(ids))


def test_node_axis_over_natal_points():
    eph = FakeEphemeris({"rahu": lambda t: 45.0 - 0.05 * (t - T0), "moon": lambda t: 40.0,
                         "sun": lambda t: 220.0})
    (st_,) = run(ctx(eph=eph, jd=T0 - 9000, u=0), R.of("transit_states", **W))
    axis = {(e.detail["natal_point"], e.detail["node"]) for e in st_.events
            if e.target == "state:node_axis"}
    assert ("graha:moon", "graha:rahu") in axis      # Rahu in Taurus over the natal Moon
    assert ("graha:sun", "graha:ketu") in axis       # Ketu in Scorpio over the natal Sun


def test_period_lord_context():
    (cx,) = run(ctx(), R.of("dasha_context", as_of="2026-10-19T00:00:00+00:00"))
    assert cx.status is Status.OK
    assert cx.fact("period_lord", "dasha:vimshottari:MD").value == "graha:mars"
    assert cx.fact("lord_houses", "dasha:vimshottari:MD").value == ("bhava:3", "bhava:10")
    refs = cx.fact("context_refs", "dasha:vimshottari:MD").value
    assert any("/dignity/graha:mars" in r for r in refs)
    assert any("/house/graha:mars/lagna" in r for r in refs)
    assert cx.fact("from_md_lord", "dasha:vimshottari:AD").value == 1   # Rahu with Mars
    assert cx.fact("md_lord_friendship", "dasha:vimshottari:AD").value is None  # node: unknown
    assert set(cx.provenance["missing"]) == {"strength", "functional_role", "karakatva"}


def test_method_registry_and_gating():
    reg = MethodRegistry(ROOT / "profiles" / "method")
    assert {"parashari", "bnn"} <= set(reg.adapters)
    prof, adapter = reg.get("bnn", allow_draft=True)
    assert prof.default_calc_profile == "bnn_v1" and "native_gender" in prof.optional_inputs
    ids = {f.id for f in adapter.feature_set()}
    assert {"bnn_relations", "bnn_karakas", "bnn_triggers", "positions"} <= ids
    reqs = [r.feature_id for r in adapter.features({"as_of": "2026-10-19T00:00:00+00:00"})]
    assert "dasha_context" in reqs and "bnn_relations" in reqs
    with pytest.raises(CalcError) as e:
        reg.get("bnn")  # draft methods do not run by default (design §7.10)
    assert e.value.reason is Reason.UNSUPPORTED_METHOD
    with pytest.raises(CalcError):
        reg.get("kp", allow_draft=True)


def test_method_profile_validation(tmp_path):
    (tmp_path / "x.yaml").write_text(
        "id: x\nschool: x\nlineage: x\ndescription: x\nstatus: draft\n"
        "calc_profiles: [a_v1]\ndefault_calc_profile: b_v1\n")
    with pytest.raises(CalcError):
        MethodRegistry(tmp_path)


# -- vargas (VAR-2) ----------------------------------------------------------------------------

@pytest.mark.parametrize("varga,lon,sign", [
    ("D2", 10.0, 4), ("D2", 20.0, 3), ("D2", 40.0, 3), ("D2", 50.0, 4),  # hora: Leo / Cancer
    ("D3", 12.0, 4), ("D3", 25.0, 8),                                   # 1st, 5th, 9th
    ("D4", 10.0, 3),                                                    # 1st, 4th, 7th, 10th
    ("D7", 35.0, 8),            # Taurus 5°: part 1 counted from the 7th (Scorpio)
    ("D16", 95.0, 2),           # Cancer 5°: part 2 from Aries (movable)
    ("D24", 1.0, 4), ("D24", 31.0, 3),                                  # odd Leo, even Cancer
    ("D27", 125.0, 4), ("D27", 31.0, 3),  # Leo 5°: part 4 from Aries; Taurus 1°: Cancer
    ("D30", 3.0, 0), ("D30", 7.0, 10), ("D30", 15.0, 8), ("D30", 20.0, 2), ("D30", 27.0, 6),
    ("D30", 33.0, 1), ("D30", 40.0, 5), ("D30", 45.0, 11), ("D30", 52.0, 9), ("D30", 58.0, 7),
    ("D40", 30.0, 6), ("D60", 0.0, 0), ("D60", 30.25, 1), ("D60", 30.5, 2),
])
def test_varga_constructions(varga, lon, sign):
    assert varga_sign(lon, refdata().varga_spec(varga)) == sign


def test_table_boundaries_belong_to_the_later_part():
    d30 = refdata().varga_spec("D30")
    assert varga_sign(5.0, d30) == 10 and varga_sign(4.999999, d30) == 0
    b = d30.boundaries()
    assert 5.0 in b and 30 + 12.0 in b and len(b) == 12 * 5


@given(st.floats(0, 359.999999), st.sampled_from(["D3", "D4", "D7", "D12", "D16", "D20", "D24",
                                                   "D27", "D40", "D45", "D60"]))
def test_equal_parts_change_only_at_part_boundaries(lon, varga):
    spec = refdata().varga_spec(varga)
    w = 30.0 / spec.divisions
    sign = int(lon // 30.0)
    part = min(int((lon - 30.0 * sign) * spec.divisions // 30.0), spec.divisions - 1)
    inside = 30.0 * sign + (part + 0.5) * w  # the middle of the same part, same sign
    assert varga_sign(lon, spec) == varga_sign(inside, spec)


def test_d30_sensitivity_uses_its_own_boundaries():
    eph = FakeEphemeris({"mars": lambda t: 4.99 + 0.5 * (t - T0)})  # crosses 5° in ~29 min
    c = ctx(eph=eph, jd=T0, u=60)
    (v,) = run(c, R.of("vargas", vargas=("D30",)))
    f = v.fact("varga_sign", "graha:mars", varga="D30")
    assert f.value == "rashi:aries" and f.sensitivity == "sensitive"


def test_bad_table_is_rejected(tmp_path):
    import shutil

    from ruamel.yaml import YAML

    from astro.calc.refdata import IntegrityError, YamlReferenceData
    shutil.copytree(ROOT / "ontology", tmp_path / "o")
    y = YAML()
    data = y.load((tmp_path / "o/vargas.yaml").read_text())
    data["vargas"]["D30"]["table"]["odd"][-1][0] = 29
    y.dump(data, tmp_path / "o/vargas.yaml")
    with pytest.raises(IntegrityError):
        YamlReferenceData(tmp_path / "o")
