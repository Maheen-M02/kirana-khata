"""numbers_hi: >= 80 golden cases each direction + round-trip property (skill requirement)."""

from __future__ import annotations

import pytest
from hypothesis import given
from hypothesis import strategies as st

from app.nlu.numbers_hi import (
    UNIT_INDEX,
    _build_word_index,
    find_amount,
    number_words,
    parse_amount,
    speak_amount,
    tokenize,
)

# (spoken, paise)
PARSE_CASES: list[tuple[str, int]] = [
    # digits and mixed forms
    ("120", 12000), ("1,200", 120000), ("1,20,000", 12000000), ("₹120", 12000), ("120 rs", 12000),
    ("120rs", 12000), ("rs 120", 12000), ("Rs. 120", 12000), ("120/-", 12000), ("1.5k", 150000),
    ("2k", 200000), ("12.50", 1250), ("120 rupaye", 12000), ("₹ 75", 7500), ("5 hazaar", 500000),
    ("2.5 lakh", 25000000), ("3 sau", 30000), ("2 hazaar 500", 250000),
    # Hindi words 1-100 (every unique form is covered by the table test below)
    ("ek", 100), ("do sau", 20000), ("teen", 300), ("chaar", 400), ("paanch", 500),
    ("chhah", 600), ("saat", 700), ("aath", 800), ("nau", 900), ("das", 1000), ("dus", 1000),
    ("gyarah", 1100), ("barah", 1200), ("unnees", 1900), ("bees", 2000), ("bis", 2000),
    ("ikkees", 2100), ("pachchees", 2500), ("tees", 3000), ("chaalees", 4000),
    ("pachaas", 5000), ("pachas", 5000), ("pachpan", 5500), ("saath rupaye", 6000),
    ("sattar", 7000), ("pachhattar", 7500), ("assi", 8000), ("nabbe", 9000),
    ("ninyaanve", 9900), ("sau", 10000),
    # compounds and scales
    ("ek sau bees", 12000), ("sau bis", 12000), ("teen sau", 30000), ("paanch sau pachaas", 55000),
    ("ek hazaar", 100000), ("hazaar", 100000), ("hajar", 100000), ("do hajaar", 200000),
    ("ek hazaar paanch sau pachaas", 155000), ("bees hazaar", 2000000), ("ek lakh", 10000000),
    ("do laakh pachaas hazaar", 25000000), ("chaar sau ninyaanve", 49900),
    ("unchaas hazaar nau sau ninyaanve", 4999900), ("ek crore", 1000000000),
    # fractions
    ("dedh sau", 15000), ("dhai sau", 25000), ("dhai hazaar", 250000), ("dedh hazaar", 150000),
    ("sava sau", 12500), ("sava do sau", 22500), ("saade teen sau", 35000),
    ("saadhe paanch sau", 55000), ("paune do sau", 17500), ("paune teen hazaar", 275000),
    ("dedh lakh", 15000000), ("aadha", 50), ("dedh", 150), ("dhai", 250),
    # Devanagari
    ("एक सौ बीस", 12000), ("दो सौ", 20000), ("पचास रुपये", 5000), ("डेढ़ सौ", 15000),
    ("ढाई हज़ार", 250000), ("साढ़े तीन सौ", 35000), ("पौने दो सौ", 17500), ("सवा सौ", 12500),
    ("एक हजार पांच सौ", 150000), ("निन्यानवे", 9900), ("१२०", 12000), ("₹१,२००", 120000),
    # Marathi basics
    ("don", 200), ("paach", 500), ("daha", 1000), ("shambhar", 10000), ("donshe", 20000),
    ("दोनशे", 20000), ("teenshe", 30000), ("pannas", 5000), ("vees", 2000),
    # rupees + paise
    ("dus rupaye pachaas paise", 1050), ("pachaas paise", 50), ("das rupaye aur bees paise", 1020),
    # English words (codemix output)
    ("one hundred twenty", 12000), ("fifty", 5000), ("two thousand", 200000),
]  # fmt: skip

SPEAK_CASES: list[tuple[int, str]] = [
    (100, "ek rupaya"), (200, "do rupaye"), (1000, "das rupaye"), (1100, "gyaarah rupaye"),
    (1500, "pandrah rupaye"), (2000, "bees rupaye"), (2100, "ikkees rupaye"),
    (2500, "pachchees rupaye"), (3000, "tees rupaye"), (3500, "paintees rupaye"),
    (4000, "chaalees rupaye"), (4500, "paintaalees rupaye"), (5000, "pachaas rupaye"),
    (5500, "pachpan rupaye"), (6000, "saath rupaye"), (6500, "painsath rupaye"),
    (7000, "sattar rupaye"), (7500, "pachhattar rupaye"), (8000, "assi rupaye"),
    (8500, "pachaasi rupaye"), (9000, "nabbe rupaye"), (9900, "ninyaanve rupaye"),
    (10000, "ek sau rupaye"), (12000, "ek sau bees rupaye"), (12500, "ek sau pachchees rupaye"),
    (15000, "ek sau pachaas rupaye"), (17500, "ek sau pachhattar rupaye"),
    (20000, "do sau rupaye"), (25000, "do sau pachaas rupaye"), (30000, "teen sau rupaye"),
    (35000, "teen sau pachaas rupaye"), (45000, "chaar sau pachaas rupaye"),
    (49900, "chaar sau ninyaanve rupaye"), (50000, "paanch sau rupaye"),
    (75000, "saat sau pachaas rupaye"), (99900, "nau sau ninyaanve rupaye"),
    (100000, "ek hazaar rupaye"), (120000, "ek hazaar do sau rupaye"),
    (150000, "ek hazaar paanch sau rupaye"), (155000, "ek hazaar paanch sau pachaas rupaye"),
    (200000, "do hazaar rupaye"), (250000, "do hazaar paanch sau rupaye"),
    (999900, "nau hazaar nau sau ninyaanve rupaye"), (1000000, "das hazaar rupaye"),
    (2500000, "pachchees hazaar rupaye"), (4999900, "unchaas hazaar nau sau ninyaanve rupaye"),
    (5000000, "pachaas hazaar rupaye"), (9999900, "ninyaanve hazaar nau sau ninyaanve rupaye"),
    (10000000, "ek lakh rupaye"), (15000000, "ek lakh pachaas hazaar rupaye"),
    (25000000, "do lakh pachaas hazaar rupaye"), (100000000, "das lakh rupaye"),
    (1000000000, "ek crore rupaye"), (1234567800, "ek crore teyees lakh paintaalees hazaar chhah sau athattar rupaye"),
    (50, "pachaas paise"), (1, "ek paise"), (99, "ninyaanve paise"), (1050, "das rupaye aur pachaas paise"),
    (12050, "ek sau bees rupaye aur pachaas paise"), (101, "ek rupaya aur ek paise"),
    (0, "shunya rupaye"), (31000, "teen sau das rupaye"), (64000, "chhah sau chaalees rupaye"),
    (42000, "chaar sau bees rupaye"), (9000, "nabbe rupaye"), (23000, "do sau tees rupaye"),
    (17000, "ek sau sattar rupaye"), (8800, "atthaasi rupaye"), (7700, "satattar rupaye"),
    (6600, "chhiyaasath rupaye"), (5300, "tirpan rupaye"), (4400, "chauvaalees rupaye"),
    (3300, "taintees rupaye"), (2200, "baaees rupaye"), (1900, "unnees rupaye"),
    (1800, "athaarah rupaye"), (1700, "satrah rupaye"), (1600, "solah rupaye"),
    (1400, "chaudah rupaye"), (1300, "terah rupaye"), (1200, "baarah rupaye"),
    (900, "nau rupaye"), (800, "aath rupaye"), (700, "saat rupaye"), (600, "chhah rupaye"),
    (500, "paanch rupaye"), (400, "chaar rupaye"), (300, "teen rupaye"),
]  # fmt: skip


@pytest.mark.parametrize(("text", "paise"), PARSE_CASES)
def test_parse(text: str, paise: int) -> None:
    assert parse_amount(text) == paise


@pytest.mark.parametrize(("paise", "words"), SPEAK_CASES)
def test_speak(paise: int, words: str) -> None:
    assert speak_amount(paise) == words


def test_case_counts_meet_skill_minimum() -> None:
    assert len(PARSE_CASES) >= 80
    assert len(SPEAK_CASES) >= 80


def test_every_hindi_number_1_to_99_parses_from_its_canonical_word() -> None:
    # "+ rupaye": a bare trailing "do" is deliberately NOT a number ("likh do" = "write it").
    for n in range(1, 100):
        assert parse_amount(number_words(n) + " rupaye") == n * 100, number_words(n)


def test_word_index_has_no_collisions() -> None:
    assert _build_word_index() == UNIT_INDEX  # raises on any skeleton collision


@given(st.integers(min_value=1, max_value=99_99_999_99))
def test_round_trip_speak_then_parse(paise: int) -> None:
    assert parse_amount(speak_amount(paise)) == paise


@given(st.integers(min_value=1, max_value=99_99_999))
def test_number_words_round_trip(n: int) -> None:
    assert parse_amount(number_words(n) + " rupaye") == n * 100


@pytest.mark.parametrize(
    ("text", "paise", "flag"),
    [
        ("Sharma ji ne do kilo cheeni li, ek sau bees rupaye udhaar", 12000, None),
        ("शर्मा जी ने 2 kg चीनी ली, 120 रुपये उधार।", 12000, None),
        ("teen sau nahi do sau", 20000, "corrected"),
        ("Gupta ji teen sau... sorry, chaar sau", 40000, "corrected"),
        ("Sharma ji ne cheeni li", None, "amount_missing"),
        ("Raju 500 ka saman le gaya, 200 de gaya", 50000, "multiple_amounts"),
        ("ek Parle-G liya, 20 udhaar", 2000, "amount_unmarked"),
    ],
)
def test_find_amount_in_sentences(text: str, paise: int | None, flag: str | None) -> None:
    r = find_amount(text)
    assert r.paise == paise
    if flag:
        assert flag in r.flags


@pytest.mark.parametrize(
    "text",
    ["khate mein likh do", "cancel kar do", "Sharma ji ke saath gaya", "haan bilkul", ""],
)
def test_words_that_only_look_like_numbers(text: str) -> None:
    assert find_amount(text).paise is None


def test_money_never_uses_float() -> None:
    assert isinstance(parse_amount("12.35"), int)
    assert parse_amount("12.355") == 1236  # half-up on sub-paise input


def test_tokenize_splits_symbols_and_units() -> None:
    assert [t.text for t in tokenize("₹1,200 aur 2kg")] == ["rs", "1,200", "aur", "2", "kg"]
