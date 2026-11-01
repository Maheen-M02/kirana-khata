"""Deterministic Hinglish/Hindi/Marathi intent parser. It is both the fallback when Evon is
down and the independent check on every amount Evon suggests. Pure functions, no IO.

Works on Prisma's real output shapes: `transcribe` (Devanagari + digits) and `transliterate`
(Latin + number words), via the shared romaniser + skeleton keys.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from decimal import Decimal
from fractions import Fraction

from app.nlu.numbers_hi import (
    CURRENCY_WORDS,
    NEGATION_WORDS,
    PAISE_WORDS,
    UNIT_WORDS,
    AmountResult,
    NumberSpan,
    Token,
    find_amount,
    is_number_word,
    to_paise,
    tokenize,
)
from app.nlu.resolver import display_spoken, is_honorific, scan_known_names
from app.nlu.schema import (
    LARGE_AMOUNT_PAISE,
    MAX_AMOUNT_PAISE,
    MONEY_INTENTS,
    Intent,
    Item,
    NluContext,
    ParsedIntent,
)
from app.nlu.translit import skeleton


def _keys(*words: str) -> frozenset[str]:
    return frozenset(skeleton(w) for w in words)


def _phrases(*phrases: str) -> tuple[tuple[str, ...], ...]:
    return tuple(tuple(skeleton(w) for w in p.split()) for p in phrases)


CREDIT = _keys(
    "udhaar", "udhar", "udhari", "udhaari", "udaar", "udhr", "baaki", "baki", "bakaya", "khate",
    "khata", "khaate", "credit", "likh", "likho", "likhna", "likhdo", "likhlo",
)  # fmt: skip
CREDIT_PHRASES = _phrases("baad mein", "baad me", "bad me", "kal dega", "kal denge", "baad main")
PAYMENT = _keys(
    "jama", "jamaa", "jma", "diye", "die", "diya", "dia", "diyo", "payment", "pay", "paid",
    "bheje", "bheja", "bhej", "chukaya", "chukaye", "chukta", "lautaya", "lautaye", "vapas",
    "wapas", "online", "upi", "gpay", "paytm", "phonepe", "dile", "bharle", "bharla", "bhare",
)  # fmt: skip
# "diya/diye" alone also means the *shop gave* goods ("Meena ko tel diya"): weak evidence.
WEAK_PAYMENT = _keys("diye", "die", "diya", "dia", "diyo", "dile")
PAYMENT_PHRASES = _phrases(
    "de gaye", "de gaya", "de gayi", "de gae", "de diye", "de diya", "jama kele", "mil gaye",
    "mil gaya", "mil gayi", "mile hain", "chuka diya", "chuka diye", "jama kar",
)  # fmt: skip
CASH = _keys("nakad", "nakd", "nagad", "cash", "kaish", "kesh", "nagdi", "rokda", "rokh")
SALES_WORDS = _keys(
    "bikri", "bikree", "bikari", "sale", "sales", "becha", "bika", "biki", "kamai", "kamaai",
    "dhanda", "galla", "total", "vikri", "vikree", "dhandha", "collection",
)  # fmt: skip
TODAY = _keys("aaj", "aj", "aajka", "today", "aaja")
DUES_PHRASES = _phrases(
    "kis kis", "kiska kiska", "kaun kaun", "kon kon", "udhaar list", "udhar list", "baaki list",
    "sabka hisaab", "sab ka hisaab", "sabse zyada", "sabse jyada", "sabka baaki", "list batao",
    "kiske kiske", "kunacha kunacha", "kon kon", "sagle baki",
)  # fmt: skip
QUERY_WORDS = _keys(
    "kitna", "kitni", "kitne", "kya", "batao", "bataiye", "bata", "batana", "dikhao", "dikha",
    "hisaab", "hisab", "hishob", "balance", "kiti", "sango", "sanga", "hua", "hai", "kitta",
)  # fmt: skip
BALANCE_WORDS = _keys(
    "hisaab", "hisab", "hishob", "balance", "khata", "kitna", "kiti", "baaki", "baki"
)
UNDO = _keys(
    "cancel", "kainsil", "kensil", "undo", "hata", "hatao", "mita", "mitao", "galti", "radd"
)
UNDO_PHRASES = _phrases(
    "pichhli entry", "pichli entry", "last entry", "galat ho gaya", "galat ho gayi",
    "galat likha", "wapas lo", "pichla", "pichhla", "aakhri entry", "akhri entry",
)  # fmt: skip
YES = _keys(
    "haan", "han", "ha", "haa", "hanji", "sahi", "theek", "thik", "yes", "ok", "okay",
    "bilkul", "ji", "correct", "barobar", "ho", "hoy", "chalega", "kardo", "done", "haanji",
)  # fmt: skip
NO = _keys("nahi", "nahin", "naheen", "na", "naa", "galat", "no", "mat", "nako", "nai", "nope")
CASE_MARKERS = _keys(
    "ne", "ka", "ki", "ke", "ko", "se", "kaa", "kee", "la", "ni", "cha", "chi", "che"
)
FILLERS = _keys(
    "aaj", "abhi", "haan", "accha", "acha", "are", "arre", "arey", "suno", "ok", "to",
    "toh", "aur", "phir", "fir", "ab", "please", "zara", "jara", "jo", "wo", "vo", "ye",
)  # fmt: skip
ITEM_STOP = (
    CREDIT | PAYMENT | CASH | CASE_MARKERS | CURRENCY_WORDS | NEGATION_WORDS
    | _keys("aur", "liya", "li", "liye", "le", "gaye", "gaya", "diya", "aaj", "tha", "the")
)  # fmt: skip
VERB_STOP = _keys(
    "do", "karo", "kar", "kardo", "likh", "de", "dena", "le", "lo", "hai", "tha", "thi", "mein",
    "me", "main", "par", "pe", "wala", "wale", "hua", "hui", "gaya", "gaye", "diya", "liya",
)  # fmt: skip
PURCHASE = _keys(
    "li", "liya", "liye", "lia", "lie", "kharida", "kharide", "kharidi", "ghetla", "ghetle",
    "ghetli", "nela", "nele", "le", "gaye", "gaya",
)  # fmt: skip
TWO_AMOUNT_GOODS = _keys("saaman", "saman", "samaan", "maal", "mal", "bill", "saamaan", "kharida")


def _has_phrase(keys: Sequence[str], phrases: Iterable[tuple[str, ...]]) -> bool:
    for p in phrases:
        n = len(p)
        for i in range(len(keys) - n + 1):
            if tuple(keys[i : i + n]) == p:
                return True
    return False


def _any(keys: Sequence[str], vocab: frozenset[str]) -> bool:
    return any(k in vocab for k in keys)


def _negated(keys: Sequence[str], vocab: frozenset[str]) -> bool:
    """'udhaar nahi', 'cash nahi' — a keyword immediately followed by a negation."""
    return any(
        k in vocab and i + 1 < len(keys) and keys[i + 1] in NEGATION_WORDS
        for i, k in enumerate(keys)
    )


# ------------------------------------------------------------ customer extraction
def extract_customer(tokens: Sequence[Token], known: Sequence[str] = ()) -> str | None:
    """Name phrase before the first case marker / honorific ("Sharma ji ne", "Gupta ka")."""
    keys = [t.key for t in tokens]
    texts = [t.text for t in tokens]
    hon = [is_honorific(t) for t in texts]
    for i, k in enumerate(keys):
        is_hon = hon[i]
        if not (k in CASE_MARKERS or is_hon):
            continue
        core_end = i  # name words sit before the marker / first honorific
        j = i
        while j < len(texts) and hon[j]:
            j += 1  # honorific chain: "ramesh bhai", "sharma uncle ji"
        start = core_end - 1
        while start >= 0 and core_end - start <= 3:
            kk, tt = keys[start], texts[start]
            if (
                kk in FILLERS or kk in CASE_MARKERS or kk in CREDIT or kk in PAYMENT
                or kk in CASH or kk in CURRENCY_WORDS or tt[0].isdigit() or kk in QUERY_WORDS
                or kk in TODAY or kk in UNIT_WORDS or kk in VERB_STOP or kk in PURCHASE
                or kk in NEGATION_WORDS or is_number_word(kk) or kk in SALES_WORDS
            ):  # fmt: skip
                break
            start -= 1
        core = texts[start + 1 : core_end]
        if core:
            return display_spoken(" ".join(texts[start + 1 : j]))
    # "Raju 500 ka saman..." : 1-2 plain words at the start, directly followed by a number.
    for n in (2, 1):
        if len(tokens) > n and (tokens[n].text[0].isdigit() or is_number_word(keys[n])):
            head = keys[:n]
            if all(
                k not in FILLERS and k not in VERB_STOP and k not in CREDIT and k not in PAYMENT
                and k not in CASH and not is_number_word(k) and k not in UNIT_WORDS
                and k not in QUERY_WORDS and k not in TODAY and k not in SALES_WORDS
                and k not in CURRENCY_WORDS and k != "rs"
                for k in head
            ):  # fmt: skip
                return display_spoken(" ".join(texts[:n]))
    if known:
        hit = scan_known_names(texts, known)
        if hit:
            return hit
    return None


# ------------------------------------------------------------ items
def extract_items(tokens: Sequence[Token], spans: Sequence[NumberSpan]) -> list[Item]:
    items: list[Item] = []
    for s in spans:
        if s.kind not in ("qty", "unknown") or s.value > 1000:
            continue
        i = s.end
        unit: str | None = None
        if i < len(tokens) and tokens[i].key in UNIT_WORDS:
            unit = UNIT_WORDS[tokens[i].key]
            i += 1
        name: list[str] = []
        while i < len(tokens) and len(name) < 3:
            t = tokens[i]
            if t.key in ITEM_STOP or t.text[0].isdigit() or t.key in UNIT_WORDS:
                break
            name.append(t.text)
            i += 1
        if name and (unit or s.kind == "unknown"):
            qty = Decimal(s.value.numerator) / Decimal(s.value.denominator)
            items.append(Item(name=" ".join(name), qty=qty, unit=unit))
    return items


# ------------------------------------------------------------ main entry
def _two_amounts(tokens: Sequence[Token], res: AmountResult) -> int | None:
    """'100 ka saaman liya, 50 diye' -> credit of 50 (goods minus paid)."""
    spans = [s for s in res.spans if s.kind != "qty"]
    if len(spans) < 2:
        return None
    keys = [t.key for t in tokens]
    goods = next(
        (s for s in spans if any(k in TWO_AMOUNT_GOODS for k in keys[s.end : s.end + 3])), None
    )

    def paid_after(s: NumberSpan) -> bool:
        window = keys[s.end : s.end + 3]
        return any(k in PAYMENT for k in window) or _has_phrase(window, PAYMENT_PHRASES)

    paid = next((s for s in spans if s is not goods and paid_after(s)), None)
    if goods and paid and goods.value > paid.value:
        return to_paise(Fraction(goods.value - paid.value))
    return None


def parse_rules(transcript: str, ctx: NluContext | None = None) -> ParsedIntent:
    ctx = ctx or NluContext()
    tokens = tokenize(transcript)
    keys = [t.key for t in tokens]
    base = {"transcript": transcript, "source": "rules"}

    if not tokens:
        return ParsedIntent(intent="unknown", confidence=0.0, flags=["empty"], **base)

    amount = find_amount(transcript, tokens)
    has_number = bool(amount.spans)

    # 1. Short yes / no (the confirm step).
    if len(tokens) <= 4 and not has_number:
        if keys[0] in NO or any(k in NO for k in keys):
            return ParsedIntent(intent="confirm_no", confidence=0.9, **base)
        soft = FILLERS | _keys(
            "hai", "he", "hain", "ji", "na", "bhai", "likh", "likho", "kar", "karo", "do", "de",
            "dijiye", "kardo",
        )  # fmt: skip
        if all(k in YES or k in soft for k in keys) and any(k in YES for k in keys):
            return ParsedIntent(intent="confirm_yes", confidence=0.9, **base)

    # 2. Undo.
    if (_any(keys, UNDO) or _has_phrase(keys, UNDO_PHRASES)) and not (
        amount.paise and (_any(keys, CREDIT) or _any(keys, PAYMENT))
    ):
        return ParsedIntent(intent="undo_last", confidence=0.85, **base)

    customer = extract_customer(tokens, ctx.known_customers)
    is_question = _any(keys, QUERY_WORDS) and not amount.paise

    # 3. Queries (read-only).
    if _has_phrase(keys, DUES_PHRASES):
        return ParsedIntent(intent="query_dues_list", confidence=0.85, **base)
    if _any(keys, SALES_WORDS) and (_any(keys, TODAY) or is_question) and not customer:
        return ParsedIntent(intent="query_sales_today", confidence=0.85, **base)
    if customer and is_question and _any(keys, BALANCE_WORDS):
        return ParsedIntent(intent="query_balance", customer=customer, confidence=0.85, **base)

    # 4. Money.
    flags = list(amount.flags)
    credit = (_any(keys, CREDIT) or _has_phrase(keys, CREDIT_PHRASES)) and not _negated(
        keys, CREDIT
    )
    payment = (_any(keys, PAYMENT) or _has_phrase(keys, PAYMENT_PHRASES)) and not _negated(
        keys, PAYMENT
    )
    strong_payment = payment and (
        any(k in PAYMENT and k not in WEAK_PAYMENT for k in keys)
        or _has_phrase(keys, PAYMENT_PHRASES)
    )
    cash = _any(keys, CASH) and not _negated(keys, CASH)
    paise = amount.paise
    intent: Intent
    confidence = 0.8

    two = _two_amounts(tokens, amount)
    if two is not None:
        intent, paise = "credit_sale", two
        flags = [f for f in flags if f != "multiple_amounts"] + ["two_amounts"]
    elif cash:
        intent = "cash_sale"
    elif payment and not credit:
        intent = "payment_received"
    elif credit and not payment:
        intent = "credit_sale"
    elif credit and payment and not strong_payment:
        intent = "credit_sale"  # "Meena ko tel diya, udhaar likh lo"
        confidence = 0.65
    elif credit and payment:
        # "udhaar ke 200 jama kiye" = paying off dues; the payment verb is the action.
        intent = "payment_received"
        confidence = 0.6
        flags.append("ambiguous_type")
    elif customer and (paise is not None or _any(keys, PURCHASE)):
        # "Sharma ji ne cheeni li" (no amount) -> credit, then ask "Kitne rupaye?"
        intent, confidence = "credit_sale", 0.55
        flags.append("ambiguous_type")
    elif paise is not None:
        intent, confidence = "cash_sale", 0.6
    else:
        return ParsedIntent(intent="unknown", customer=customer, confidence=0.2, **base)

    if paise is not None and paise > MAX_AMOUNT_PAISE:
        paise = None
        flags.append("amount_missing")
    if paise is not None and paise > LARGE_AMOUNT_PAISE:
        flags.append("large_amount")
    if "amount_unmarked" in flags or "multiple_amounts" in flags:
        confidence = min(confidence, 0.7)
    if intent in MONEY_INTENTS and intent != "cash_sale" and not customer:
        flags.append("customer_missing")
        confidence = min(confidence, 0.6)

    money_span = amount.money_span
    amount_text = (
        " ".join(t.text for t in tokens[money_span.start : money_span.end + 1])
        if money_span is not None
        else None
    )
    if amount_text and money_span is not None and money_span.end < len(tokens):
        nxt = tokens[money_span.end].key
        if nxt not in CURRENCY_WORDS and nxt not in PAISE_WORDS:
            amount_text = " ".join(t.text for t in tokens[money_span.start : money_span.end])
    return ParsedIntent(
        intent=intent,
        customer=customer,
        items=extract_items(tokens, amount.spans),
        amount_paise=paise,
        amount_text=amount_text,
        confidence=confidence,
        flags=sorted(set(flags)),
        **base,
    )
