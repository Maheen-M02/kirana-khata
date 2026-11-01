from __future__ import annotations

import pytest

from app.nlu.resolver import (
    CustomerRef,
    disambiguation_question,
    new_alias,
    normalise_name,
    phonetic_key,
    resolve,
    score,
)
from app.nlu.translit import romanise, skeleton

RAMESH = CustomerRef(1, "Ramesh Sharma", ("Sharma ji",))
SURESH = CustomerRef(2, "Suresh Sharma")
GUPTA = CustomerRef(3, "Anil Gupta", ("Gupta ji",))
PATIL = CustomerRef(4, "Patil Kaka")
SHOP = [GUPTA, PATIL]


@pytest.mark.parametrize(
    ("raw", "norm"),
    [
        ("Sharma ji", "sharma"), ("sharmaji", "sharma"), ("शर्मा जी", "sharma"),
        ("Sharmaa Uncle", "sharma"), ("Ramesh bhai", "ramesh"), ("रमेश भाई", "ramesh"),
        ("Meena didi", "mina"), ("पाटील काकांनी", "patil"), ("Khan sahab", "khan"),
    ],
)  # fmt: skip
def test_normalise_strips_honorifics_and_script(raw: str, norm: str) -> None:
    assert normalise_name(raw) == norm


@pytest.mark.parametrize(
    ("spoken", "candidate"),
    [("Sharma ji", "sharmaa"), ("Gupta", "gupata"), ("verma", "वर्मा"), ("Shrma", "Sharma"),
     ("Kulkarni", "Kulkarnee"), ("Choudhary", "chaudhari")],
)  # fmt: skip
def test_stt_spelling_drift_still_scores_high(spoken: str, candidate: str) -> None:
    assert score(spoken, candidate) >= 85


def test_different_people_score_low() -> None:
    assert score("Gupta ji", "Sharma") < 60
    assert score("Patil", "Pandey") < 80


def test_unique_match_auto_picks() -> None:
    r = resolve("गुप्ता जी", SHOP)
    assert r.kind == "matched"
    assert r.customer == GUPTA
    assert r.question is None


def test_two_sharmas_trigger_question() -> None:
    r = resolve("Sharma ji", [RAMESH, SURESH, GUPTA])
    assert r.kind == "ambiguous"
    assert {c.customer.id for c in r.candidates} == {1, 2}
    assert r.question == "Kaun se Sharma ji: Ramesh ya Suresh?"


def test_unknown_name_offers_new_customer() -> None:
    r = resolve("Bunty", SHOP)
    assert r.kind == "new"
    assert r.question == "Naya customer 'Bunty' bana doon?"


def test_full_name_disambiguates() -> None:
    r = resolve("Suresh Sharma", [RAMESH, SURESH])
    assert r.kind == "matched"
    assert r.customer == SURESH


def test_empty_spoken_is_none() -> None:
    assert resolve(None, SHOP).kind == "none"
    assert resolve("ji", SHOP).kind == "none"


def test_new_alias_learns_only_new_variants() -> None:
    assert new_alias("Gupta uncle", GUPTA) is None  # normalises to an existing name
    assert new_alias("Anil bhai", GUPTA) == "Anil Bhai"


def test_question_for_single_weak_candidate() -> None:
    assert disambiguation_question("Sharma", [RAMESH]) == "Sharma matlab Ramesh Sharma?"


def test_phonetic_key_ignores_aspiration_and_vowel_length() -> None:
    assert phonetic_key("Bhatt") == phonetic_key("Bat")
    assert phonetic_key("Sharmaa") == phonetic_key("Sarma")


@pytest.mark.parametrize(
    ("deva", "latin"),
    [("उधार", "udhaar"), ("जमा", "jamaa"), ("नमकीन", "namkeen"), ("कितना", "kitnaa"),
     ("शर्मा", "sharmaa"), ("हज़ार", "hazaar"), ("डेढ़", "derh"), ("नहीं", "naheen"),
     ("१२०", "120"), ("रुपये।", "rupye.")],
)  # fmt: skip
def test_romanise(deva: str, latin: str) -> None:
    assert romanise(deva) == latin


def test_skeleton_is_spelling_tolerant() -> None:
    assert skeleton("udhaar") == skeleton("udhar") == skeleton("Udhhaar")
    assert skeleton("theek") == skeleton("thik")
    assert skeleton("saat") != skeleton("saath")  # 7 vs 60 must stay apart
