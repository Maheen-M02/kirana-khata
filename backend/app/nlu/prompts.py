"""Evon prompt: JSON-only extraction with few-shot examples (Hinglish, Devanagari, Marathi,
STT typos, queries). Kept short: every token costs latency on the 3.5 s budget."""

from __future__ import annotations

import json
from collections.abc import Sequence

SYSTEM = """You are the parser for a kirana shop ledger in India.
Input: ONE transcript of the shopkeeper speaking (Hinglish, Hindi in Devanagari, or Marathi). It may contain speech-recognition errors.
Output ONLY one JSON object, no prose, no markdown:
{"intent": one of ["credit_sale","cash_sale","payment_received","query_balance","query_sales_today","query_dues_list","undo_last","confirm_yes","confirm_no","unknown"],
 "customer": string|null, "items": [{"name": string, "qty": number|null, "unit": string|null}],
 "amount_rupees": number|null, "amount_text": string|null, "confidence": number 0..1}
Rules:
- "udhaar/udhar/baaki/khate mein/baad mein dega" (उधार, बाकी, खाते) -> credit_sale.
- "jama/diye/de gaye/payment/online bheje" (जमा, दिए) -> payment_received.
- "nakad/cash" (नकद, कैश), or a sale with no customer -> cash_sale.
- "X ka hisaab / X ka kitna baaki" -> query_balance. "aaj kitni bikri" -> query_sales_today. "kis kis ka baaki" -> query_dues_list.
- "pichhli entry cancel / galat ho gaya" -> undo_last. Short "haan/sahi/theek" -> confirm_yes; "nahi/galat" -> confirm_no.
- customer = the person's name as spoken, with honorific (e.g. "Sharma ji"). null if none.
- amount_rupees = the money amount only (not quantities like "2 kilo"). Never invent an amount: if none is spoken, use null and confidence < 0.6.
- If the speaker corrects themselves ("teen sau... nahi, do sau"), use the corrected amount.
- "100 ka saaman, 50 diye" means credit_sale of 50 (goods minus paid).
- amount_text = copy the exact spoken amount phrase from the transcript.
Known customers: {known}"""

FEW_SHOT: tuple[tuple[str, dict[str, object]], ...] = (
    ("Sharma ji ne do kilo cheeni aur ek Parle-G liya, ek sau bees rupaye udhaar",
     {"intent": "credit_sale", "customer": "Sharma ji",
      "items": [{"name": "cheeni", "qty": 2, "unit": "kilo"}, {"name": "parle-g", "qty": 1, "unit": None}],
      "amount_rupees": 120, "amount_text": "ek sau bees rupaye", "confidence": 0.95}),
    ("शर्मा जी ने 2 kg चीनी ली, 120 रुपये उधार।",
     {"intent": "credit_sale", "customer": "Sharma ji", "items": [{"name": "cheeni", "qty": 2, "unit": "kilo"}],
      "amount_rupees": 120, "amount_text": "120 रुपये", "confidence": 0.95}),
    ("Gupta ji ne 300 rupaye jama kiye",
     {"intent": "payment_received", "customer": "Gupta ji", "items": [], "amount_rupees": 300,
      "amount_text": "300 rupaye", "confidence": 0.95}),
    ("gupta ji ne sau bis diye",
     {"intent": "payment_received", "customer": "Gupta ji", "items": [], "amount_rupees": 120,
      "amount_text": "sau bis", "confidence": 0.8}),
    ("पचास रुपये का दूध नकद",
     {"intent": "cash_sale", "customer": None, "items": [{"name": "doodh", "qty": None, "unit": None}],
      "amount_rupees": 50, "amount_text": "पचास रुपये", "confidence": 0.9}),
    ("पाटील काकांनी दोनशे रुपये उधार घेतले",
     {"intent": "credit_sale", "customer": "Patil kaka", "items": [], "amount_rupees": 200,
      "amount_text": "दोनशे रुपये", "confidence": 0.85}),
    ("Ramesh bhai ka kitna baaki hai?",
     {"intent": "query_balance", "customer": "Ramesh bhai", "items": [], "amount_rupees": None,
      "amount_text": None, "confidence": 0.95}),
    ("aaj kitni bikri hui", {"intent": "query_sales_today", "customer": None, "items": [],
                             "amount_rupees": None, "amount_text": None, "confidence": 0.95}),
    ("kis kis ka paisa baaki hai", {"intent": "query_dues_list", "customer": None, "items": [],
                                    "amount_rupees": None, "amount_text": None, "confidence": 0.95}),
    ("pichhli entry cancel karo", {"intent": "undo_last", "customer": None, "items": [],
                                   "amount_rupees": None, "amount_text": None, "confidence": 0.95}),
    ("Verma ji teen sau nahi do sau udhaar",
     {"intent": "credit_sale", "customer": "Verma ji", "items": [], "amount_rupees": 200,
      "amount_text": "do sau", "confidence": 0.8}),
    ("haan sahi hai", {"intent": "confirm_yes", "customer": None, "items": [],
                       "amount_rupees": None, "amount_text": None, "confidence": 0.95}),
)  # fmt: skip


def build_messages(
    transcript: str, known_customers: Sequence[str] = (), error: str | None = None
) -> list[dict[str, str]]:
    known = ", ".join(list(dict.fromkeys(known_customers))[:50]) or "(none yet)"
    messages = [{"role": "system", "content": SYSTEM.replace("{known}", known)}]
    for text, out in FEW_SHOT:
        messages.append({"role": "user", "content": text})
        messages.append({"role": "assistant", "content": json.dumps(out, ensure_ascii=False)})
    messages.append({"role": "user", "content": transcript})
    if error:
        messages.append(
            {
                "role": "user",
                "content": f"Your last reply was invalid ({error[:300]}). "
                "Reply again with ONLY the JSON object for the transcript above.",
            }
        )
    return messages
