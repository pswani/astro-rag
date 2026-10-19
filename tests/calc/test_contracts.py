import copy
from datetime import UTC, datetime
from pathlib import Path

import pytest
from pydantic import ValidationError
from ruamel.yaml import YAML

from astro.calc.core.status import CalcError, Reason
from astro.calc.model import ChartFact, DashaPeriod, fact_id
from astro.calc.profile import CalcProfile, load_profile, load_profiles
from astro.calc.refdata import IntegrityError, YamlReferenceData

ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture(scope="module")
def ref():
    return YamlReferenceData(ROOT / "ontology")


def _profile_dict():
    return YAML(typ="safe").load((ROOT / "profiles/calc/parashari_v1.yaml").read_text())


def test_profiles_load_and_hash_is_stable():
    profs = load_profiles(ROOT / "profiles/calc")
    assert set(profs) == {"parashari_v1", "bnn_v1"}
    p = profs["parashari_v1"]
    assert p.content_hash == load_profile(ROOT / "profiles/calc/parashari_v1.yaml").content_hash
    assert p.content_hash != profs["bnn_v1"].content_hash
    assert profs["bnn_v1"].retro_in_previous_sign is True


@pytest.mark.parametrize("mutate", [
    lambda d: d.update(ayanamsa={"id": "fagan_bradley"}),    # unknown enum value
    lambda d: d.update(house_system="koch"),                 # not a supported system
    lambda d: d.update(unknown_setting=1),                   # unknown key
    lambda d: d["nodes"].pop("retrograde"),                  # missing required setting
    lambda d: d.update(provisional=["nodes.nonexistent"]),   # bad provisional path
])
def test_unknown_or_missing_settings_are_refused(tmp_path, mutate):
    d = _profile_dict()
    mutate(d)
    f = tmp_path / "parashari_v9.yaml"
    YAML().dump(d, f)
    with pytest.raises(CalcError) as e:
        load_profile(f)
    assert e.value.reason is Reason.UNSUPPORTED_PROFILE


def test_profile_is_frozen():
    p = CalcProfile.model_validate(_profile_dict())
    with pytest.raises(ValidationError):
        p.house_system = "sripati"  # type: ignore[misc]


def test_coverage():
    p = CalcProfile.model_validate(_profile_dict())
    assert p.is_covered(2451545.0)
    assert not p.is_covered(2378496.5)
    assert not p.is_covered(2597641.5)


def test_refdata_lookups(ref):
    assert ref.rashi_id(0) == "rashi:aries" and ref.sign_lord(9) == "graha:saturn"
    assert ref.own_signs("graha:mars") == (0, 7)
    assert ref.nakshatra_id(1) == "nakshatra:bharani"
    assert ref.nakshatra_lord(26) == "graha:mercury"
    assert ref.natural_friendship("graha:saturn", "graha:sun") == "enemy"
    assert ref.natural_friendship("graha:moon", "graha:saturn") == "neutral"
    assert ref.natural_friendship("graha:rahu", "graha:sun") is None
    assert sum(y for _, y in ref.dasha_sequence("vimshottari")) == 120
    assert ref.tithi_id(14) == "tithi:shukla_purnima"
    assert ref.tithi_id(29) == "tithi:krishna_amavasya"
    assert ref.karana_id(0) == "karana:kimstughna" and ref.karana_id(1) == "karana:bava"
    assert ref.karana_id(56) == "karana:vishti" and ref.karana_id(59) == "karana:naga"
    assert ref.nitya_yoga_id(26) == "nitya_yoga:vaidhriti"
    assert ref.vara(0) == ("vara:sunday", "graha:sun")
    assert ref.karaka_roles("bnn", "graha:saturn") == ("karaka_role:bnn.karma",
                                                       "karaka_role:bnn.career")
    assert ref.native_karaka("bnn", "female") == "graha:venus"
    assert ref.status == "provisional"


def test_karana_cycle(ref):
    movable = [ref.karana_id(k) for k in range(1, 57)]
    assert movable[:7] == movable[7:14] and len(set(movable)) == 7


def test_refdata_integrity_failures(tmp_path):
    import shutil
    shutil.copytree(ROOT / "ontology", tmp_path / "o")
    y = YAML()
    path = tmp_path / "o/rashis.yaml"
    data = y.load(path.read_text())
    bad = copy.deepcopy(data)
    bad["rashis"][0]["lord"] = "pluto"
    y.dump(bad, path)
    with pytest.raises(IntegrityError):
        YamlReferenceData(tmp_path / "o")


def test_fact_typing():
    ok = ChartFact(id="c/sign/graha:sun", kind="sign", subject="graha:sun", value="rashi:leo",
                   profile_id="parashari_v1")
    assert ok.sensitivity == "stable"
    with pytest.raises(ValidationError):
        ChartFact(id="x", kind="house", subject="graha:sun", value="3", profile_id="p")
    with pytest.raises(ValidationError):
        ChartFact(id="x", kind="house", subject="graha:sun", value=True, profile_id="p")
    with pytest.raises(ValidationError):
        ChartFact(id="x", kind="sign", subject="graha:sun", value=None, profile_id="p")
    with pytest.raises(ValidationError):
        ChartFact(id="x", kind="no_such_kind", subject="graha:sun", value=1, profile_id="p")
    unknown = ChartFact(id="x", kind="sign", subject="lagna", value=None, profile_id="p",
                        sensitivity="unknown")
    assert unknown.value is None
    assert fact_id("chart:ab", "house", "graha:saturn", "lagna", "D1") == \
        "chart:ab/house/graha:saturn/lagna/D1"


def test_dasha_period_order():
    t = datetime(2000, 1, 1, tzinfo=UTC)
    with pytest.raises(ValidationError):
        DashaPeriod(id="x", system="vimshottari", level="MD", lord="graha:sun", start_utc=t,
                    end_utc=t, parent_id=None, sequence=0, profile_id="p")
