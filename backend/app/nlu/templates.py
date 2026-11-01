"""Short, warm Hinglish lines for Timbre. Amounts are always spoken as words (speak_amount)."""

from __future__ import annotations

from collections.abc import Sequence

from app.nlu.numbers_hi import speak_amount
from app.nlu.schema import ParsedIntent

UNKNOWN = "Maaf kijiye, samajh nahi aaya. Dobara boliye."
SAY_YES_OR_NO = "Haan ya nahi boliye."
CANCELLED = "Theek hai, cancel kar diya."
UNDO_CONFIRM = "Pichhli entry cancel karoon? Haan ya nahi?"
UNDO_DONE = "Pichhli entry cancel ho gayi."


def _who(name: str | None) -> str:
    return name or "Customer"


def confirm_text(p: ParsedIntent, name: str | None = None) -> str:
    """The read-back before anything is written. `name` = resolved display name."""
    if p.intent == "undo_last":
        return UNDO_CONFIRM
    if not p.is_money:
        return UNKNOWN
    who = name or p.customer
    if p.amount_paise is None:
        return f"{who} ka kitne rupaye?" if who and p.intent != "cash_sale" else "Kitne rupaye?"
    amt = speak_amount(p.amount_paise)
    caution = "Dhyan dijiye, bada amount. " if "large_amount" in p.flags else ""
    if p.intent == "credit_sale":
        return f"{caution}{_who(who)}, {amt} udhaar. Sahi hai?"
    if p.intent == "payment_received":
        return f"{caution}{_who(who)} ne {amt} jama kiye. Sahi hai?"
    return f"{caution}{amt} nakad bikri. Sahi hai?"


def balance_phrase(paise: int) -> str:
    if paise > 0:
        return f"total baaki {speak_amount(paise)}"
    if paise < 0:
        return f"{speak_amount(-paise)} advance jama hai"
    return "ab kuch baaki nahi"


def committed_text(intent: str, name: str | None, balance_paise: int | None) -> str:
    if intent == "cash_sale" or balance_paise is None:
        return "Likh diya."
    head = "Likh diya." if intent == "credit_sale" else "Jama ho gaya."
    return f"{head} {_who(name)} ka {balance_phrase(balance_paise)}."


def balance_text(name: str, balance_paise: int) -> str:
    return f"{name} ka {balance_phrase(balance_paise)}."


def dues_list_text(dues: Sequence[tuple[str, int]], top: int = 3) -> str:
    owing = [(n, a) for n, a in dues if a > 0][:top]
    if not owing:
        return "Kisi ka kuch baaki nahi hai."
    parts = ", ".join(f"{n} {speak_amount(a)}" for n, a in owing)
    return f"Sabse zyada baaki: {parts}."


def sales_today_text(total_paise: int, entries: int) -> str:
    if entries == 0:
        return "Aaj abhi tak koi bikri nahi likhi."
    return f"Aaj ki bikri {speak_amount(total_paise)}, {entries} entry."
