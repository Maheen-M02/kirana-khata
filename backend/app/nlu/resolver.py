"""Spoken customer name -> customer. "Sharma ji" / "शर्मा जी" / "sharmaa uncle" all normalise to
"sharma"; rapidfuzz plus a Hindi-aware phonetic key handles STT spelling drift.

Rules (hinglish-ledger-nlu skill): one candidate >= 90 picks; two or more >= 80 asks
"Kaun se Sharma ji: Ramesh ya Suresh?"; best < 80 on credit/payment offers to create a new one.
"""

from __future__ import annotations

import re
from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import Literal

from rapidfuzz import fuzz

from app.nlu.translit import romanise, skeleton

HONORIFICS = frozenset(
    {
        "ji", "jee", "bhai", "bhaiya", "bhaiyya", "bhaisaab", "uncle", "aunty", "auntie",
        "anty", "didi", "di", "saab", "sahab", "saheb", "seth", "sethji", "bhabhi", "chacha",
        "chachi", "mama", "mami", "dada", "dadi", "kaka", "kaki", "tai", "bhau", "mavshi",
        "rao", "madam", "sir", "mr", "mrs", "shri", "shrimati", "smt", "babu", "bhaijaan",
    }
)  # fmt: skip
HONORIFIC_KEYS = frozenset(skeleton(h) for h in HONORIFICS)
# Marathi case suffixes glued to names/honorifics (on skeleton keys): काकांनी -> kakani,
# काकांचा -> kakancha, ताईंनी -> taini.
_MARATHI_SUFFIX = re.compile(r"(?:ncha|nchi|nche|nni|ni|cha|chi|che|na|la|kade)$")
_REPEATS = re.compile(r"(.)\1+")

AUTO_PICK = 90.0
ASK = 80.0


def marathi_base(key: str) -> str:
    """'kakancha' -> 'kaka', 'kakani' -> 'kaka', 'taini' -> 'tai' (skeleton keys)."""
    base = _MARATHI_SUFFIX.sub("", key) if len(key) > 4 else key
    return base[:-1] if base.endswith("n") and len(base) > 3 else base


def is_honorific(word: str) -> bool:
    k = skeleton(romanise(word))
    return k in HONORIFIC_KEYS or marathi_base(k) in HONORIFIC_KEYS


def normalise_name(name: str) -> str:
    s = romanise(name).lower()
    s = re.sub(r"[^a-z\s]", " ", s)
    words = []
    for w in s.split():
        if is_honorific(w):
            continue
        k = skeleton(w)
        if k.endswith("ji") and len(k) > 4:  # "sharmaji"
            k = k[:-2]
        words.append(k)
    return " ".join(words)


def strip_marathi_suffix(word: str) -> str:
    return marathi_base(skeleton(word)) if len(word) > 5 else word


_PHONETIC_SUBS = (
    ("sh", "s"), ("ph", "f"), ("w", "v"), ("z", "j"), ("q", "k"), ("ck", "k"), ("x", "ks"),
    ("bh", "b"), ("dh", "d"), ("th", "t"), ("kh", "k"), ("gh", "g"), ("chh", "c"), ("ch", "c"),
    ("jh", "j"), ("ee", "i"), ("oo", "u"), ("y", "i"),
)  # fmt: skip


def phonetic_key(name: str) -> str:
    """Rough Hindi-aware key: aspiration, sh/s, v/w and vowel length don't matter.
    'shrma', 'sharmaa', 'sarma' -> 'srm' style skeletons compared with fuzz.ratio."""
    out = []
    for w in normalise_name(name).split():
        for a, b in _PHONETIC_SUBS:
            w = w.replace(a, b)
        w = _REPEATS.sub(r"\1", w)
        head, tail = w[:1], re.sub(r"[aeiou]", "", w[1:])
        out.append(head + tail)
    return " ".join(out)


def _fuzzy(a: str, b: str) -> float:
    """Every spoken word must match *some* word of the stored name; score = the weakest match.
    "sharma" vs "ramesh sharma" -> 100 (less specific: two Sharmas -> ask), "suresh sharma" vs
    "ramesh sharma" -> ~66 (a wrong word is information), "gupata" vs "anil gupta" -> ~91."""
    b_words = b.split()
    return float(min(max(fuzz.ratio(w, bw) for bw in b_words) for w in a.split()))


def score(spoken: str, candidate: str) -> float:
    a, b = normalise_name(spoken), normalise_name(candidate)
    if not a or not b:
        return 0.0
    pa, pb = phonetic_key(spoken), phonetic_key(candidate)
    phon = _fuzzy(pa, pb) * 0.95 if pa and pb else 0.0
    return max(_fuzzy(a, b), phon)


@dataclass(frozen=True)
class CustomerRef:
    id: int
    display_name: str
    aliases: tuple[str, ...] = ()

    @property
    def names(self) -> tuple[str, ...]:
        return (self.display_name, *self.aliases)


@dataclass(frozen=True)
class Candidate:
    customer: CustomerRef
    score: float


@dataclass
class Resolution:
    kind: Literal["matched", "ambiguous", "new", "none"]
    spoken: str
    customer: CustomerRef | None = None
    candidates: list[Candidate] = field(default_factory=list)

    @property
    def question(self) -> str | None:
        if self.kind == "ambiguous":
            return disambiguation_question(self.spoken, [c.customer for c in self.candidates])
        if self.kind == "new":
            return f"Naya customer '{display_spoken(self.spoken)}' bana doon?"
        return None


def resolve(spoken: str | None, customers: Sequence[CustomerRef]) -> Resolution:
    if not spoken or not normalise_name(spoken):
        return Resolution("none", spoken or "")
    scored = sorted(
        (Candidate(c, max(score(spoken, n) for n in c.names)) for c in customers),
        key=lambda c: c.score,
        reverse=True,
    )
    strong = [c for c in scored if c.score >= ASK]
    if not strong:
        return Resolution("new", spoken, candidates=scored[:3])
    if len(strong) == 1 and strong[0].score >= AUTO_PICK:
        return Resolution("matched", spoken, strong[0].customer, strong)
    return Resolution("ambiguous", spoken, candidates=strong[:3])


def display_spoken(spoken: str) -> str:
    """'sharmaa jee' -> 'Sharma ji' for prompts."""
    words = romanise(spoken).split()
    out = []
    for w in words:
        lw = w.lower()
        if lw in ("jee", "ji"):
            out.append("ji")
        else:
            out.append(_REPEATS.sub(r"\1", lw).capitalize())
    return " ".join(out)


def disambiguation_question(spoken: str, options: Sequence[CustomerRef]) -> str:
    """'Kaun se Sharma ji: Ramesh ya Suresh?' (first names when the surname is the clash)."""
    spoken_norm = set(normalise_name(spoken).split())
    labels = []
    for c in options:
        parts = [p for p in c.display_name.split() if p.lower() not in spoken_norm]
        labels.append(" ".join(parts) or c.display_name)
    head = display_spoken(spoken) or "customer"
    if len(labels) == 1:
        return f"{head} matlab {options[0].display_name}?"
    return f"Kaun se {head}: {', '.join(labels[:-1])} ya {labels[-1]}?"


def new_alias(spoken: str, customer: CustomerRef) -> str | None:
    """Spoken variant worth remembering after the shopkeeper confirms (system learns)."""
    norm = normalise_name(spoken)
    if not norm or any(normalise_name(n) == norm for n in customer.names):
        return None
    return display_spoken(spoken)


def scan_known_names(tokens: Sequence[str], known: Sequence[str]) -> str | None:
    """Find a known customer name anywhere in the utterance (for Marathi / odd word order)."""
    best: tuple[float, str] | None = None
    norm_known = [(k, normalise_name(k)) for k in known if normalise_name(k)]
    words = [strip_marathi_suffix(t) for t in tokens]
    for size in (2, 1):
        for i in range(len(words) - size + 1):
            gram = " ".join(words[i : i + size])
            if not normalise_name(gram):
                continue
            for original, nk in norm_known:
                s = fuzz.ratio(normalise_name(gram), nk)
                if s >= 88 and (best is None or s > best[0]):
                    best = (s, original)
    return best[1] if best else None
