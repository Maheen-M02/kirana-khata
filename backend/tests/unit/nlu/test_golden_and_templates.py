"""Golden NLU gate (offline: rules parser) + confirmation templates."""

from __future__ import annotations

from pathlib import Path

import pytest

from app.nlu.rules import parse_rules
from app.nlu.schema import NluContext, ParsedIntent
from app.nlu.templates import (
    committed_text,
    confirm_text,
    dues_list_text,
    sales_today_text,
)
from tests.golden import GOLDEN_PATH, load_cases, score

HOLDOUT = Path(GOLDEN_PATH).with_name("golden_holdout.yaml")


@pytest.mark.parametrize("path", [GOLDEN_PATH, HOLDOUT], ids=["golden", "holdout"])
def test_rules_meet_golden_gate(path: Path) -> None:
    cases = load_cases(path)
    report = score(cases, [parse_rules(c.transcript, NluContext()) for c in cases])
    print("\n" + report.table())
    assert report.intent_accuracy >= 0.90, report.table()
    # Money safety: every amount is either right or flagged for explicit read-back.
    assert not report.amount_wrong_unflagged, report.table()


def test_golden_set_size_and_tags() -> None:
    cases = load_cases()
    assert len(cases) >= 60
    tags = {t for c in cases for t in c.tags}
    assert {"hinglish", "hindi_deva", "marathi", "noisy_typo", "query", "fraction"} <= tags


def _p(**kw: object) -> ParsedIntent:
    base: dict[str, object] = {"intent": "credit_sale", "confidence": 0.9, "source": "rules"}
    base.update(kw)
    return ParsedIntent.model_validate(base)


@pytest.mark.parametrize(
    ("parsed", "name", "text"),
    [
        (_p(amount_paise=12000), "Sharma ji", "Sharma ji, ek sau bees rupaye udhaar. Sahi hai?"),
        (_p(intent="payment_received", amount_paise=30000), "Gupta ji",
         "Gupta ji ne teen sau rupaye jama kiye. Sahi hai?"),
        (_p(intent="cash_sale", amount_paise=5000), None, "pachaas rupaye nakad bikri. Sahi hai?"),
        (_p(amount_paise=None), "Sharma ji", "Sharma ji ka kitne rupaye?"),
        (_p(amount_paise=6000000, flags=["large_amount"]), "Sharma ji",
         "Dhyan dijiye, bada amount. Sharma ji, saath hazaar rupaye udhaar. Sahi hai?"),
        (_p(intent="undo_last"), None, "Pichhli entry cancel karoon? Haan ya nahi?"),
        (_p(intent="unknown"), None, "Maaf kijiye, samajh nahi aaya. Dobara boliye."),
    ],
)  # fmt: skip
def test_confirm_text(parsed: ParsedIntent, name: str | None, text: str) -> None:
    assert confirm_text(parsed, name) == text


def test_confirm_text_never_contains_digits_or_symbols() -> None:
    for paise in (12000, 155050, 99, 10000000):
        t = confirm_text(_p(amount_paise=paise), "Sharma ji")
        assert not any(ch.isdigit() for ch in t)
        assert "₹" not in t


def test_after_commit_and_query_texts() -> None:
    assert committed_text("credit_sale", "Sharma ji", 32000) == (
        "Likh diya. Sharma ji ka total baaki teen sau bees rupaye."
    )
    assert committed_text("payment_received", "Gupta ji", 0) == (
        "Jama ho gaya. Gupta ji ka ab kuch baaki nahi."
    )
    assert dues_list_text(
        [("Sharma ji", 50000), ("Gupta ji", 30000), ("Verma ji", 12000), ("Raju", 100)]
    ) == (
        "Sabse zyada baaki: Sharma ji paanch sau rupaye, Gupta ji teen sau rupaye, "
        "Verma ji ek sau bees rupaye."
    )
    assert dues_list_text([]) == "Kisi ka kuch baaki nahi hai."
    assert sales_today_text(250000, 14) == "Aaj ki bikri do hazaar paanch sau rupaye, 14 entry."
