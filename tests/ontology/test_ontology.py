"""Ontology loading, folding and integrity checks (design §8, phase1-foundations §3.2–§3.5)."""

import re
import shutil
import unicodedata
from pathlib import Path

import pytest

from astro.calc.refdata import YamlReferenceData
from astro.cli.main import main
from astro.ontology import OntologyError, load_ontology
from astro.ontology.fold import fold, key, tokens

from .test_confusables import matcher

ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture
def onto_dir(tmp_path) -> Path:
    d = tmp_path / "ontology"
    shutil.copytree(ROOT / "ontology", d)
    return d


def edit(d: Path, name: str, old: str, new: str) -> None:
    p = d / f"{name}.yaml"
    text = p.read_text(encoding="utf-8")
    assert old in text, old
    p.write_text(text.replace(old, new, 1), encoding="utf-8")


def errors(d: Path, editions=()) -> str:
    with pytest.raises(OntologyError) as e:
        load_ontology(d, editions)
    return "\n".join(e.value.errors)


# -- the shipped ontology ---------------------------------------------------------------------

def test_shipped_ontology_loads_with_every_knw1_kind():
    o = load_ontology(ROOT / "ontology")
    counts = {k: len(o.of_kind(k)) for k in o.kinds()}
    assert counts["graha"] == 9 and counts["rashi"] == 12 and counts["nakshatra"] == 27
    assert counts["bhava"] == 12 and counts["tithi"] == 30 and counts["vara"] == 7
    assert counts["nitya_yoga"] == 27 and counts["karana"] == 11 and counts["varga"] == 16
    for kind in ("dignity", "paksha", "yoga", "upagraha", "special_lagna", "deity", "topic",
                 "school", "koota", "dasha_system", "karaka_scheme", "point", "bhava_group"):
        assert counts[kind] > 0, kind
    assert o.status == "provisional"


def test_cli_check_and_match(capsys):
    assert main(["ontology", "check"]) == 0
    assert "ontology OK" in capsys.readouterr().out
    assert main(["ontology", "match", "Shani in the 10th house",
                 "--reserve", "Shani=person:p_1"]) == 0
    out = capsys.readouterr().out
    assert "Shani  →  ambiguous: graha:saturn | person:p_1" in out and "bhava:10" in out
    assert main(["ontology", "match", "x", "--reserve", "bad"]) == 2


def test_review_pack_lists_every_entity(tmp_path):
    out = tmp_path / "pack.md"
    assert main(["ontology", "review-pack", "--out", str(out)]) == 0
    text = out.read_text(encoding="utf-8")
    o = load_ontology(ROOT / "ontology")
    assert all(f"`{eid}`" in text for eid in o.entities)


# -- folding and tokens -----------------------------------------------------------------------

def test_devanagari_words_keep_their_vowel_signs():
    assert [t for _, _, t in tokens("शनि की दशा")] == ["शनि", "की", "दशा"]
    assert [t for _, _, t in tokens("श्लोक १२॥ शनि।")] == ["श्लोक", "१२", "शनि"]


def test_folding():
    assert fold("Śani") == fold("sani") == "sani"
    assert fold("मङ्गल") == fold("मंगल")
    assert fold("पूर्वाषाढ़ा") == fold("पूर्वाषाढा")    # nukta dropped
    assert key("Shani's") == ("shani", "s")


def test_decomposed_input_matches_and_offsets_refer_to_nfc():
    text = unicodedata.normalize("NFD", "Śani in Mūla")
    s1, s2 = matcher().match(text)
    nfc = unicodedata.normalize("NFC", text)
    assert (s1.entity_id, s2.entity_id) == ("graha:saturn", "nakshatra:mula")
    assert nfc[s1.start:s1.end] == s1.text == "Śani"


# -- versions ---------------------------------------------------------------------------------

def test_alias_edit_leaves_the_calculation_version_unchanged(onto_dir):
    before = YamlReferenceData(onto_dir).version
    onto_before = load_ontology(onto_dir).version
    edit(onto_dir, "grahas", "Shanee,", "Shanee, Shanii,")
    assert YamlReferenceData(onto_dir).version == before
    assert load_ontology(onto_dir).version != onto_before


def test_calculation_edit_changes_the_calculation_version(onto_dir):
    before = YamlReferenceData(onto_dir).version
    edit(onto_dir, "grahas", "exaltation: {sign: rashi:aries, degree: 10}",
         "exaltation: {sign: rashi:aries, degree: 11}")
    edit(onto_dir, "grahas", "debilitation: {sign: rashi:libra, degree: 10}",
         "debilitation: {sign: rashi:libra, degree: 11}")
    assert YamlReferenceData(onto_dir).version != before


# -- integrity checks (one mutation per rule) -------------------------------------------------

def test_rule1_unknown_reference(onto_dir):
    edit(onto_dir, "bhavas", "karakas: [graha:venus]", "karakas: [graha:pluto]")
    assert "bhava:7.karakas: unknown graha:pluto" in errors(onto_dir)


def test_rule2_plain_name_on_two_entities(onto_dir):
    edit(onto_dir, "grahas", "names: [Jupiter,", "names: [Jupiter, Saturn,")
    assert re.search(r"alias 'saturn' is a plain name of \['graha:jupiter', 'graha:saturn'\]",
                     errors(onto_dir))


def test_rule3_plain_here_ambiguous_there(onto_dir):
    edit(onto_dir, "yogas", "vajra: {category: nabhasa, ambiguous_names:",
         "vajra: {category: nabhasa, names:")
    assert "make it ambiguous everywhere" in errors(onto_dir)


def test_rule4_disputed_view_needs_a_source(onto_dir):
    edit(onto_dir, "grahas", "own_signs: []          # co-lordship of Aquarius",
         "exaltation: [{sign: rashi:taurus}, {sign: rashi:gemini, source: x:1}]\n"
         "    own_signs: []          # co-lordship of Aquarius")
    assert "graha:rahu.exaltation: every disputed view needs a source" in errors(onto_dir)


def test_rule5_reviewed_file_must_cite_a_registered_edition(onto_dir):
    edit(onto_dir, "dignities", "status: provisional", "status: reviewed")
    assert "dignities.yaml: reviewed, so source" in errors(onto_dir)
    edit(onto_dir, "dignities", 'source: "BPHS ch. 3 (edition: requirements open question 1)"',
         "source: bphs_test_2000:3")
    assert "dignities.yaml: reviewed" in errors(onto_dir, editions=["other_1999"])
    o = load_ontology(onto_dir, editions=["bphs_test_2000"])
    assert o.file_status["dignities.yaml"] == "reviewed" and o.status == "provisional"


def test_rule7_calculation_values_must_be_entities(onto_dir):
    edit(onto_dir, "dignities", "  own: {names:", "  own_sign: {names:")
    assert "the calculation emits dignity:own" in errors(onto_dir)


def test_rule8_core_entities_need_both_scripts(onto_dir):
    edit(onto_dir, "rashis", "[Aries, Mesha, Meṣa, मेष]", "[Aries, Mesha, Meṣa]")
    assert "rashi:aries: needs a Latin and a Devanagari name" in errors(onto_dir)


def test_rule9_ordinals_are_unique(onto_dir):
    edit(onto_dir, "bhavas", "ordinals: [2nd, second,", "ordinals: [2nd, first,")
    assert "ordinal 'first' used by bhava:1 and bhava:2" in errors(onto_dir)


def test_rule9_ordinals_are_single_words(onto_dir):
    edit(onto_dir, "bhavas", "ordinals: [3rd, third,", "ordinals: [3rd, the third,")
    assert "ordinal 'the third' must be one word" in errors(onto_dir)


def test_misspelt_field_is_refused(onto_dir):
    edit(onto_dir, "topics", "career: {tier: core,", "career: {teir: core,")
    assert "topic:career" in errors(onto_dir)


def test_calculation_table_checks_still_run(onto_dir):
    edit(onto_dir, "nakshatras", "{id: bharani, lord: venus,", "{id: bharani, lord: sun,")
    assert "Vimshottari order" in errors(onto_dir)
