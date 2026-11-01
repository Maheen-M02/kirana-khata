"""Spoken numbers <-> integer paise for Hinglish / Hindi (Latin or Devanagari) / Marathi basics.

parse:  "dedh sau" -> 15000, "₹1,200" -> 120000, "एक सौ बीस" -> 12000, "dus rupaye pachaas paise"
        -> 1050, "1.5k" -> 150000. Exact arithmetic with Fraction: money never touches a float.
speak:  12000 -> "ek sau bees rupaye", 155050 -> "ek hazaar paanch sau pachaas rupaye aur pachaas
        paise" (Timbre wants spoken-form numbers).
find_amount: picks the money phrase out of a whole utterance and flags anything uncertain.
"""

from __future__ import annotations

import re
from collections.abc import Sequence
from dataclasses import dataclass, field
from decimal import Decimal
from fractions import Fraction

from app.nlu.translit import romanise, skeleton

# ---------------------------------------------------------------- word tables
# value -> spellings; the FIRST spelling is the canonical one used by speak().
_HINDI_1_99: dict[int, tuple[str, ...]] = {
    1: ("ek", "ik"), 2: ("do",), 3: ("teen", "tin"), 4: ("chaar", "char"),
    5: ("paanch", "panch", "paach"), 6: ("chhah", "chhe", "chhai", "che", "cheh", "chah"),
    7: ("saat",), 8: ("aath",), 9: ("nau", "no"), 10: ("das", "dus", "dass"),
    11: ("gyaarah", "gyarah", "gyara", "gyarha"), 12: ("baarah", "barah", "bara"),
    13: ("terah", "tera"), 14: ("chaudah", "chauda", "chodah", "choda"),
    15: ("pandrah", "pandra", "pandhra"), 16: ("solah", "sola"), 17: ("satrah", "satra"),
    18: ("athaarah", "atharah", "athara", "athra"), 19: ("unnees", "unis", "unnis"),
    20: ("bees", "bis"), 21: ("ikkees", "ikkis"), 22: ("baaees", "bais", "baais", "baees"),
    23: ("teyees", "teis", "tees2", "teyis"), 24: ("chaubees", "chaubis", "chobis"),
    25: ("pachchees", "pachees", "pachis", "pachchis"), 26: ("chhabbees", "chhabis", "chabbis"),
    27: ("sattaaees", "sattais", "satais", "sattaees"), 28: ("atthaaees", "atthais", "athais", "atthaees"),
    29: ("untees", "untis", "unatis"), 30: ("tees", "tis"),
    31: ("iktees", "ikattees", "iktis", "ikatis"), 32: ("battees", "battis", "batis"),
    33: ("taintees", "taintis", "tentis"), 34: ("chauntees", "chauntis", "chontis"),
    35: ("paintees", "paintis", "pentis"), 36: ("chhattees", "chhattis", "chattis"),
    37: ("saintees", "saintis", "sentis"), 38: ("adtees", "artees", "adtis", "artis", "arhtees"),
    39: ("untaalees", "untalis", "untaalis"), 40: ("chaalees", "chalis", "chaalis"),
    41: ("iktaalees", "iktalis", "iktaalis"), 42: ("bayaalees", "bayalis", "bayaalis"),
    43: ("taintaalees", "taintalis", "tentalis"), 44: ("chauvaalees", "chauvalis", "chavalis", "chauaalees"),
    45: ("paintaalees", "paintalis", "pentalis"), 46: ("chhiyaalees", "chhiyalis", "chiyalis"),
    47: ("saintaalees", "saintalis", "sentalis"), 48: ("adtaalees", "artaalees", "artalis", "adtalis", "arhtaalees"),
    49: ("unchaas", "unchas", "unanchas"), 50: ("pachaas", "pachas", "pachchaas"),
    51: ("ikyaavan", "ikyavan", "ikyawan"), 52: ("baavan", "bavan", "bawan"),
    53: ("tirpan", "tirepan"), 54: ("chauvan", "chauwan", "chovan"),
    55: ("pachpan",), 56: ("chhappan", "chappan"), 57: ("sattaavan", "sattavan", "satawan"),
    58: ("atthaavan", "atthavan", "athawan"), 59: ("unsath", "unsaath", "unsatth"),
    60: ("saath", "sath"), 61: ("iksath", "iksaath", "iksatth"), 62: ("baasath", "basath", "baasatth"),
    63: ("tirsath", "tirsaath", "tiresath"), 64: ("chausath", "chausaath", "chaunsath", "chonsath"),
    65: ("painsath", "pensath", "painsaath"), 66: ("chhiyaasath", "chhiyasath", "chiyasath"),
    67: ("sadsath", "sarsath", "sadsaath", "sarhsath"), 68: ("adsath", "arsath", "adsaath", "arhsath"),
    69: ("unhattar", "unhatar"), 70: ("sattar", "satar"),
    71: ("ikhattar", "ikahattar", "ikhatar"), 72: ("bahattar", "bahatar"),
    73: ("tihattar", "tihatar"), 74: ("chauhattar", "chauhatar", "chohattar"),
    75: ("pachhattar", "pachattar", "pachhatar"), 76: ("chhihattar", "chihattar", "chhihatar"),
    77: ("satattar", "sathattar", "satahattar"), 78: ("athattar", "athhattar", "athahattar"),
    79: ("unaasi", "unasi", "unyaasi", "unyasi", "unyaasee"), 80: ("assi", "asi", "assee"),
    81: ("ikyaasi", "ikyasi", "ikyaasee"), 82: ("bayaasi", "bayasi", "bayaasee"),
    83: ("tiraasi", "tirasi", "tiraasee"), 84: ("chauraasi", "chaurasi", "chauraasee"),
    85: ("pachaasi", "pachasi", "pachaasee"), 86: ("chhiyaasi", "chhiyasi", "chhiyaasee"),
    87: ("sattaasi", "sattasi", "sattaasee"), 88: ("atthaasi", "atthasi", "athasi", "atthaasee"),
    89: ("navaasi", "navasi", "nawasi", "navaasee"), 90: ("nabbe", "nabe", "nabbey"),
    91: ("ikyaanve", "ikyanve", "ikyaanbe", "ikyanbe"), 92: ("baanve", "banve", "baanbe", "banbe"),
    93: ("tiraanve", "tiranve", "tiraanbe", "tiranbe"), 94: ("chauraanve", "chauranve", "chauraanbe"),
    95: ("pachaanve", "pachanve", "panchaanve", "panchaanbe", "pachaanbe"),
    96: ("chhiyaanve", "chhiyanve", "chhiyaanbe", "chiyanve"),
    97: ("sattaanve", "sattanve", "sattaanbe"), 98: ("atthaanve", "atthanve", "atthaanbe", "athanve"),
    99: ("ninyaanve", "ninyanve", "ninyaanbe", "ninanve"),
}  # fmt: skip
_MARATHI: dict[int, tuple[str, ...]] = {
    2: ("don",), 6: ("saha",), 10: ("daha",), 11: ("akra",),
    19: ("ekonis", "ekonees"), 20: ("vees", "vis"), 40: ("chaalis",), 50: ("pannas", "pannaas"),
    80: ("aishi", "ainshi"), 90: ("navvad", "navad"),
}  # fmt: skip
_ENGLISH: dict[int, tuple[str, ...]] = {
    1: ("one",), 2: ("two",), 3: ("three",), 4: ("four",), 5: ("five",), 6: ("six",),
    7: ("seven",), 8: ("eight",), 9: ("nine",), 10: ("ten",), 11: ("eleven",), 12: ("twelve",),
    13: ("thirteen",), 14: ("fourteen",), 15: ("fifteen",), 16: ("sixteen",),
    17: ("seventeen",), 18: ("eighteen",), 19: ("nineteen",), 20: ("twenty",), 30: ("thirty",),
    40: ("forty",), 50: ("fifty",), 60: ("sixty",), 70: ("seventy",), 80: ("eighty",),
    90: ("ninety",),
}  # fmt: skip
_SCALES: dict[int, tuple[str, ...]] = {
    100: ("sau", "so", "shambhar", "hundred"),
    1_000: ("hazaar", "hazar", "hajaar", "hajar", "hajjar", "thousand"),
    1_00_000: ("laakh", "lakh", "lac", "lakhs"),
    1_00_00_000: ("karod", "crore", "karor", "carore"),
}  # fmt: skip
# Fraction words. ("mul", x): x * next scale ("dedh sau" = 150). ("add", x): applied to the
# next unit ("sava do sau" = 225, "saade teen hazaar" = 3500, "paune do sau" = 175).
_FRACTIONS: dict[str, tuple[str, Fraction]] = {}
for _w in ("dedh", "derh", "dedhh", "dhed"):
    _FRACTIONS[_w] = ("mul", Fraction(3, 2))
for _w in ("dhai", "dhaai", "dhaee", "dhaaee", "adhai", "arhai", "dhaii"):
    _FRACTIONS[_w] = ("mul", Fraction(5, 2))
for _w in ("aadha", "adha", "aadhaa", "aadhe", "adhe"):
    _FRACTIONS[_w] = ("mul", Fraction(1, 2))
for _w in ("sava", "savaa", "sawa", "sawaa"):
    _FRACTIONS[_w] = ("add", Fraction(1, 4))
for _w in ("saade", "saadhe", "sade", "sadhe", "saarhe", "sarhe"):
    _FRACTIONS[_w] = ("add", Fraction(1, 2))
for _w in ("paune", "pone", "paone", "paunay"):
    _FRACTIONS[_w] = ("add", Fraction(-1, 4))

CURRENCY_WORDS = frozenset(
    skeleton(w)
    for w in (
        "rs", "rupaye", "rupaiye", "rupay", "rupaya", "rupee", "rupees", "rupiya", "rupiye",
        "rupye", "rupe", "rupae", "rupaa", "rup", "inr", "rupya",
    )
)  # fmt: skip
PAISE_WORDS = frozenset(skeleton(w) for w in ("paise", "paisa", "pese", "paisee", "paiseh"))
UNIT_WORDS: dict[str, str] = {
    skeleton(w): canon
    for canon, words in {
        "kilo": ("kilo", "kg", "kgs", "kilogram", "keelo"),
        "gram": ("gram", "grams", "gm", "gms", "graam", "gr"),
        "litre": ("litre", "liter", "ltr", "leetar", "litar", "lit"),
        "packet": ("packet", "packets", "pkt", "paket", "paiket", "pack", "pakit"),
        "dabba": ("dabba", "dabbe", "dibba", "dabbaa", "box"),
        "darjan": ("darjan", "dozen", "darjen"),
        "piece": ("piece", "pieces", "pc", "pcs", "nag", "peece"),
        "bottle": ("bottle", "botal", "bottal"),
        "bori": ("bori", "bora", "sack"),
        "thaili": ("thaili", "thaila"),
    }.items()
    for w in words
}
_AMBIGUOUS = frozenset({"do", "no", "so", "saath", "sath", "ik", "che", "tis2"})
# Verb stems after which "do" means "give/do", not "two" ("likh do", "cancel kar do").
_DO_VERBS = frozenset(
    skeleton(w)
    for w in (
        "likh", "de", "kar", "bata", "dikha", "jod", "daal", "dal", "rakh", "hata", "mita",
        "chhod", "bhej", "le", "lagaa", "laga", "samjha", "sun", "bol", "dekh", "cancel",
    )
)  # fmt: skip
NEGATION_WORDS = frozenset(
    skeleton(w) for w in ("nahi", "nahin", "naheen", "galat", "no", "sorry", "matlab")
)


def _build_word_index() -> dict[str, int]:
    index: dict[str, int] = {}
    for table in (_HINDI_1_99, _MARATHI, _ENGLISH):
        for value, words in table.items():
            for w in words:
                key = skeleton(w.rstrip("2"))
                if not key or w.endswith("2"):
                    continue
                if key in index and index[key] != value:
                    raise ValueError(f"number word collision: {w!r} -> {index[key]} vs {value}")
                index[key] = value
    return index


UNIT_INDEX: dict[str, int] = _build_word_index()
SCALE_INDEX: dict[str, int] = {skeleton(w): v for v, ws in _SCALES.items() for w in ws}
FRACTION_INDEX: dict[str, tuple[str, Fraction]] = {skeleton(w): v for w, v in _FRACTIONS.items()}
_MARATHI_HUNDREDS = re.compile(r"^(?P<unit>[a-z]+?)(?:she|shey|shay)$")  # donshe = 200

# ---------------------------------------------------------------- tokenising
_NUM_RE = re.compile(r"^(?:\d{1,3}(?:,\d{2,3})+|\d+)(?:\.\d+)?$")
_NUM_K_RE = re.compile(r"^(\d+(?:\.\d+)?)k$")
_SPLIT_RE = re.compile(r"^(\d+(?:[.,]\d+)*)([a-z]+)$")


@dataclass(frozen=True)
class Token:
    text: str  # romanised, lowercase
    key: str  # skeleton


def tokenize(text: str) -> list[Token]:
    """Romanise Devanagari, lowercase, split money symbols and digit/letter joins."""
    t = romanise(text).lower()
    t = t.replace("₹", " rs ").replace("/-", " rs ").replace("rs.", "rs ")
    t = re.sub(r"(?<=\d),(?=\d)", "§", t)  # protect 1,200
    t = re.sub(r"(?<=\d)\.(?=\d)", "¤", t)  # protect 12.50
    t = re.sub(r"[^\w§¤\-]+", " ", t)
    tokens: list[Token] = []
    for raw in t.split():
        raw = raw.replace("§", ",").replace("¤", ".").strip("-")
        if not raw:
            continue
        m = _SPLIT_RE.match(raw)
        parts = [m.group(1), m.group(2)] if m and m.group(2) != "k" else [raw]
        for p in parts:
            tokens.append(Token(p, skeleton(p) if not p[0].isdigit() else p))
    return tokens


# ---------------------------------------------------------------- number spans
@dataclass
class NumberSpan:
    value: Fraction  # in the unit it was spoken (rupees unless `is_paise`)
    start: int  # token index
    end: int  # exclusive
    kind: str = "unknown"  # money | qty | unknown
    is_paise: bool = False
    marked: bool = False  # had an explicit currency word / symbol


def _digit_value(tok: str) -> Fraction | None:
    if _NUM_RE.match(tok):
        return Fraction(tok.replace(",", ""))
    m = _NUM_K_RE.match(tok)
    if m:
        return Fraction(m.group(1)) * 1000
    return None


def _word_value(key: str) -> tuple[str, Fraction | tuple[str, Fraction]] | None:
    if key in UNIT_INDEX:
        return ("unit", Fraction(UNIT_INDEX[key]))
    if key in SCALE_INDEX:
        return ("scale", Fraction(SCALE_INDEX[key]))
    if key in FRACTION_INDEX:
        return ("frac", FRACTION_INDEX[key])
    m = _MARATHI_HUNDREDS.match(key)
    if m and m.group("unit") in UNIT_INDEX:
        return ("unit_x100", Fraction(UNIT_INDEX[m.group("unit")] * 100))
    return None


class _Acc:
    """Accumulates one number phrase: total (thousands and up) + current (< 1000 part)."""

    def __init__(self) -> None:
        self.total = Fraction(0)
        self.current = Fraction(0)
        self.units_open = False  # a unit was added since the last scale
        self.pending: tuple[str, Fraction] | None = None
        self.count = 0
        self.last_scale = 10**12

    def value(self) -> Fraction:
        extra = self.pending[1] if self.pending and self.pending[0] == "mul" else Fraction(0)
        return self.total + self.current + extra


def is_number_word(key: str) -> bool:
    return _word_value(key) is not None


def _is_numeric(tokens: Sequence[Token], i: int) -> bool:
    return _digit_value(tokens[i].text) is not None or _word_value(tokens[i].key) is not None


def find_number_spans(tokens: Sequence[Token]) -> list[NumberSpan]:
    spans: list[NumberSpan] = []
    i = 0
    n = len(tokens)
    while i < n:
        if not _is_numeric(tokens, i):
            i += 1
            continue
        acc = _Acc()
        start = i
        j = i
        while j < n:
            tok = tokens[j]
            dv = _digit_value(tok.text)
            wv = None if dv is not None else _word_value(tok.key)
            if dv is None and wv is None:
                break
            kind, val = ("unit", dv) if dv is not None else wv  # type: ignore[misc]
            if kind in ("unit", "unit_x100"):
                assert isinstance(val, Fraction)
                if acc.units_open and kind == "unit" and dv is None:
                    break  # "do teen" = two numbers, not 5
                if acc.units_open and dv is not None:
                    break
                if acc.pending and acc.pending[0] == "add":
                    val = val + acc.pending[1]
                    acc.pending = None
                elif acc.pending and acc.pending[0] == "mul":
                    break
                acc.current += val
                acc.units_open = kind == "unit"
            elif kind == "scale":
                assert isinstance(val, Fraction)
                if val >= acc.last_scale and acc.count:
                    break  # "sau sau" / "hazaar hazaar": a new phrase
                if acc.pending:
                    mode, f = acc.pending
                    base = f if mode == "mul" else Fraction(1) + f
                    acc.pending = None
                    acc.current += base
                if val == 100:
                    acc.current = (acc.current or Fraction(1)) * 100
                else:
                    acc.total += (acc.current or Fraction(1)) * val
                    acc.current = Fraction(0)
                acc.units_open = False
                acc.last_scale = int(val)
            else:  # fraction word
                assert isinstance(val, tuple)
                if acc.units_open or acc.pending:
                    break
                acc.pending = val
            acc.count += 1
            j += 1
        if j == start:
            j = start + 1
        value = acc.value()
        if acc.pending and acc.pending[0] == "add" and acc.count == 1:
            value = Fraction(0)  # a bare "saade" means nothing
        span = NumberSpan(value=value, start=start, end=j)
        if value > 0 and not _is_false_number(tokens, span):
            spans.append(span)
        i = j
    _classify(tokens, spans)
    return spans


def _is_false_number(tokens: Sequence[Token], span: NumberSpan) -> bool:
    """'likh do', 'ke saath', 'ek baar' style words that look like numbers but are not."""
    if span.end - span.start != 1:
        return False
    word = tokens[span.start].text
    if word not in _AMBIGUOUS and word != "ek":
        return False
    nxt = tokens[span.end].key if span.end < len(tokens) else None
    prev = tokens[span.start - 1].key if span.start > 0 else None
    strong_next = nxt is not None and (
        nxt in CURRENCY_WORDS or nxt in UNIT_WORDS or nxt in PAISE_WORDS
    )
    if word in ("do",):
        if prev in _DO_VERBS or nxt is None:
            return True
        return nxt in ("na", "ji", "please", "pls", "zara", "jara")
    if word in ("saath", "sath", "so", "no", "che"):
        return not strong_next
    return False  # "ek" stays a number (qty) — amount selection deprioritises it


_WEAK_MONEY_NEXT = frozenset(skeleton(w) for w in ("ka", "ki", "ke", "wala", "vala"))


def _classify(tokens: Sequence[Token], spans: list[NumberSpan]) -> None:
    for s in spans:
        nxt = tokens[s.end].key if s.end < len(tokens) else None
        prev = tokens[s.start - 1].key if s.start > 0 else None
        if nxt in PAISE_WORDS:
            s.kind, s.is_paise, s.marked = "money", True, True
        elif nxt in CURRENCY_WORDS or prev == "rs":
            s.kind, s.marked = "money", True
        elif nxt in UNIT_WORDS:
            s.kind = "qty"
        elif nxt in _WEAK_MONEY_NEXT:
            s.kind = "money"


# ---------------------------------------------------------------- public API
def to_paise(rupees: Fraction | Decimal) -> int:
    """Rupees -> integer paise, rounding half-up (only odd inputs like 1.255 ever round).
    Decimal input (Evon's JSON) converts exactly via Fraction: no float on the money path."""
    p = Fraction(rupees) * 100
    if p < 0:
        raise ValueError("negative amount")
    return int((p.numerator * 2 + p.denominator) // (2 * p.denominator))


def parse_amount(text: str | None) -> int | None:
    """A *money phrase* ("ek sau bees rupaye", "₹1,200", "dus rupaye pachaas paise") -> paise.
    Returns None unless the text holds exactly one amount."""
    if not text:
        return None
    res = find_amount(text)
    if res.paise is None or "multiple_amounts" in res.flags:
        return None
    return res.paise


@dataclass
class AmountResult:
    paise: int | None
    flags: list[str] = field(default_factory=list)
    spans: list[NumberSpan] = field(default_factory=list)
    money_span: NumberSpan | None = None


def _merge_rupee_paise(spans: list[NumberSpan], tokens: Sequence[Token]) -> list[NumberSpan]:
    """'das rupaye (aur) pachaas paise' -> one span of 10.50 rupees."""
    out: list[NumberSpan] = []
    for s in spans:
        if s.is_paise and out and out[-1].kind == "money" and not out[-1].is_paise:
            gap = [t.key for t in tokens[out[-1].end : s.start]]
            if all(g in CURRENCY_WORDS or g == "aur" for g in gap) and len(gap) <= 2:
                prev = out[-1]
                out[-1] = NumberSpan(prev.value + s.value / 100, prev.start, s.end, "money",
                                     False, True)  # fmt: skip
                continue
        out.append(s)
    return out


def find_amount(text: str, tokens: Sequence[Token] | None = None) -> AmountResult:
    toks = list(tokens) if tokens is not None else tokenize(text)
    spans = _merge_rupee_paise(find_number_spans(toks), toks)
    flags: list[str] = []
    # Mid-sentence correction: "teen sau... nahi, do sau" -> later amount wins.
    kept: list[NumberSpan] = []
    for idx, s in enumerate(spans):
        later = spans[idx + 1 :]
        window = [t.key for t in toks[s.end : s.end + 3]]
        if later and any(w in NEGATION_WORDS for w in window) and s.kind != "qty":
            nxt = later[0]
            between = [t.key for t in toks[s.end : nxt.start]]
            if len(between) <= 4:
                flags.append("corrected")
                if nxt.kind == "unknown" and s.kind == "money":
                    nxt.kind = "money"
                continue
        kept.append(s)
    money = [s for s in kept if s.kind == "money"]
    candidates = money or [s for s in kept if s.kind == "unknown"]
    if not money and candidates:
        # Unmarked numbers: prefer multi-word / larger phrases; a lone "ek" is usually "one item".
        candidates = [
            c for c in candidates if not (c.value == 1 and c.end - c.start == 1)
        ] or candidates
        flags.append("amount_unmarked")
    if not candidates:
        return AmountResult(None, [*flags, "amount_missing"], kept, None)
    if len(candidates) > 1:
        flags.append("multiple_amounts")
    elif money:
        # Safety: an extra unmarked number ("500 ka saman ..., 200 de gaya") could be the real
        # amount. Never pick silently: flag so the amount is read back explicitly.
        others = [
            s for s in kept if s.kind == "unknown" and not (s.value == 1 and s.end - s.start == 1)
        ]
        if others:
            flags.append("multiple_amounts")
    chosen = candidates[-1]
    rupees = chosen.value / 100 if chosen.is_paise else chosen.value
    return AmountResult(to_paise(rupees), flags, kept, chosen)


# ---------------------------------------------------------------- speak
_CANON: dict[int, str] = {v: ws[0] for v, ws in _HINDI_1_99.items()}


def _below_100(n: int) -> str:
    return _CANON[n]


def _below_1000(n: int) -> list[str]:
    words: list[str] = []
    h, r = divmod(n, 100)
    if h:
        words += [_below_100(h), "sau"]
    if r:
        words.append(_below_100(r))
    return words


def number_words(n: int) -> str:
    """Integer -> Hinglish words (Indian grouping): 1550 -> 'ek hazaar paanch sau pachaas'."""
    if n < 0:
        raise ValueError("negative")
    if n == 0:
        return "shunya"
    words: list[str] = []
    for scale, name in ((1_00_00_000, "crore"), (1_00_000, "lakh"), (1_000, "hazaar")):
        q, n = divmod(n, scale)
        if q:
            words += (
                [*(_below_1000(q) if q >= 100 else [_below_100(q)]), name]
                if q < 1000
                else [number_words(q), name]
            )
    words += _below_1000(n)
    return " ".join(words)


def speak_amount(paise: int) -> str:
    """12000 -> 'ek sau bees rupaye'; 100 -> 'ek rupaya'; 1050 -> 'das rupaye aur pachaas paise'."""
    if paise < 0:
        raise ValueError("negative amount")
    rupees, p = divmod(paise, 100)
    if rupees == 0 and p == 0:
        return "shunya rupaye"
    parts: list[str] = []
    if rupees:
        parts.append(f"{number_words(rupees)} {'rupaya' if rupees == 1 else 'rupaye'}")
    if p:
        parts.append(f"{number_words(p)} paise")
    return " aur ".join(parts)
