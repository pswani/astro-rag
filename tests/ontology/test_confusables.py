"""KNW-12 acceptance: ambiguous-term fixtures resolve or ask without merging entities
(phase1-foundations §3.7)."""

from functools import cache
from pathlib import Path

import pytest

from astro.ontology import load_ontology
from astro.ontology.matcher import AliasMatcher

ROOT = Path(__file__).resolve().parents[2]


@cache
def matcher() -> AliasMatcher:
    return AliasMatcher(load_ontology(ROOT / "ontology"))


def only(text, reserved=None):
    (span,) = matcher().match(text, reserved)
    return span


RESOLVED = [
    ("Siddha yoga at birth", "nitya_yoga:siddha"),
    ("Gajakesari yoga", "yoga:gajakesari"),
    ("Gaja Kesari yoga", "yoga:gajakesari"),
    ("Bhadra yoga", "yoga:bhadra"),
    ("Nadi koota", "koota:nadi"),
    ("Bhrigu Nandi Nadi", "school:bnn"),
    ("BNN", "school:bnn"),
    ("Nadi astrology", "school:nadi_other"),
    ("Makara", "rashi:capricorn"),
    ("10th house", "bhava:10"),
    ("tenth bhava", "bhava:10"),
    ("दशम भाव", "bhava:10"),
    ("शनि", "graha:saturn"),
    ("Śani", "graha:saturn"),
    ("Shani", "graha:saturn"),
    ("Saturn", "graha:saturn"),
    ("Krishna paksha", "paksha:krishna"),
    ("Krishna", "deity:krishna"),
    ("Shukla Ekadashi", "tithi:shukla_ekadashi"),
    ("Brahma", "deity:brahma"),
    ("Brahma yoga", "nitya_yoga:brahma"),
    ("Shiva yoga", "nitya_yoga:shiva"),
    ("Mula", "nakshatra:mula"),
    ("mula trikona", "dignity:moolatrikona"),
    ("मङ्गल", "graha:mars"),
    ("मंगल", "graha:mars"),
    ("Hora lagna", "special_lagna:hora_lagna"),
    ("Navamsa", "varga:D9"),
]

AMBIGUOUS = [
    ("Vajra yoga", {"nitya_yoga:vajra", "yoga:vajra"}),
    ("Shula yoga", {"nitya_yoga:shula", "yoga:shula"}),
    ("Bhadra", {"karana:vishti", "yoga:bhadra"}),
    ("nadi", {"koota:nadi", "school:bnn", "school:nadi_other"}),
    ("Ekadashi", {"tithi:shukla_ekadashi", "tithi:krishna_ekadashi"}),
    ("Shukla", {"paksha:shukla", "nitya_yoga:shukla"}),
    ("Vyatipata", {"nitya_yoga:vyatipata", "upagraha:vyatipata"}),
    ("Guru", {"graha:jupiter"}),   # one candidate: Jupiter, or an ordinary word
    ("Kanya", {"rashi:virgo"}),
    ("Hora", {"varga:D2"}),
]


@pytest.mark.parametrize(("text", "entity"), RESOLVED)
def test_resolves(text, entity):
    span = only(text)
    assert not span.ambiguous and span.entity_id == entity
    assert text.startswith(span.text)


@pytest.mark.parametrize(("text", "candidates"), AMBIGUOUS)
def test_reports_ambiguity_without_picking(text, candidates):
    span = only(text)
    assert span.ambiguous and span.entity_id is None
    assert set(span.candidates) == candidates


def test_a_stored_person_makes_a_graha_name_ambiguous():
    span = matcher().match("Ravi's career", {"Ravi": ["person:p_1"]})[0]
    assert span.ambiguous and set(span.candidates) == {"graha:sun", "person:p_1"}
    assert only("Ravi").entity_id == "graha:sun"


def test_longest_match_wins_and_spans_do_not_overlap():
    spans = matcher().match("Neecha Bhanga Raja yoga cancels the debilitation")
    assert [(s.text, s.entity_id) for s in spans] == [
        ("Neecha Bhanga Raja yoga", "yoga:neecha_bhanga_raja"),
        ("debilitation", "dignity:debilitated")]


def test_signs_and_houses_stay_apart():
    spans = matcher().match("Saturn in Makara in the 10th house")
    assert [s.entity_id for s in spans] == ["graha:saturn", "rashi:capricorn", "bhava:10"]


def test_bare_ordinal_is_left_to_the_planner():
    assert [s.entity_id for s in matcher().match("Saturn in the 10th")] == ["graha:saturn"]


def test_mixed_script_sentence():
    spans = matcher().match("शनि दशम भाव में, गुरु की दृष्टि")
    assert [(s.text, s.entity_id, s.ambiguous) for s in spans] == [
        ("शनि", "graha:saturn", False), ("दशम भाव", "bhava:10", False),
        ("गुरु", None, True)]
