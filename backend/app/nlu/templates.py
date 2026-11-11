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
NOTHING_TO_UNDO = "Cancel karne ke liye koi entry nahi hai."
_ENTRY_WORD = {"credit_sale": "udhaar", "payment_received": "jama", "cash_sale": "nakad bikri"}


def undo_confirm_text(entry_type: str, name: str | None, amount_paise: int) -> str:
    """Name the entry before cancelling it, so the wrong one is never reversed."""
    what = f"{speak_amount(abs(amount_paise))} {_ENTRY_WORD.get(entry_type, 'entry')}"
    who = f"{name}, " if name else ""
    return f"Pichhli entry: {who}{what}. Cancel karoon?"


def amount_choice_text(options: Sequence[int]) -> str:
    """More than one amount was heard: ask instead of picking one."""
    spoken = [speak_amount(p) for p in options]
    count = "Do" if len(spoken) == 2 else "Kai"
    return f"{count} rakam suni: {', '.join(spoken[:-1])} aur {spoken[-1]}. Kitne likhoon?"


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


def dues_list_text(
    dues: Sequence[tuple[str, int]], top: int = 3, total_paise: int | None = None
) -> str:
    owing = [(n, a) for n, a in dues if a > 0][:top]
    if not owing:
        return "Kisi ka kuch baaki nahi hai."
    parts = ", ".join(f"{n} {speak_amount(a)}" for n, a in owing)
    head = f"Kul baaki {speak_amount(total_paise)}. " if total_paise else ""
    return f"{head}Sabse zyada baaki: {parts}."


def sales_today_text(
    total_paise: int, entries: int, credit_paise: int = 0, payments_paise: int = 0
) -> str:
    """The spoken day summary: bikri, then how much went on udhaar and how much came back."""
    parts: list[str] = []
    if entries:
        parts.append(f"Aaj ki bikri {speak_amount(total_paise)}, {entries} entry.")
    if credit_paise > 0:
        parts.append(f"Usme udhaar {speak_amount(credit_paise)}.")
    if payments_paise > 0:
        parts.append(f"Jama aaya {speak_amount(payments_paise)}.")
    return " ".join(parts) or "Aaj abhi tak koi bikri nahi likhi."
