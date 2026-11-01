"""Devanagari -> Hinglish-style Latin, so one keyword/number table serves Prisma's Devanagari
output ("शर्मा जी ने 2 kg चीनी ली, 120 रुपये उधार") and romanised speech alike.

Hand-rolled instead of a generic scheme (ITRANS/IAST) because we want *colloquial* spellings
("udhaar", "sharmaa", "namkeen") with Hindi schwa deletion, not scholarly ones ("udhāra").
Matching downstream is skeleton-based (see `skeleton()`), so small spelling drift is fine.
"""

from __future__ import annotations

import re
import unicodedata

_CONSONANTS: dict[str, str] = {
    "क": "k", "ख": "kh", "ग": "g", "घ": "gh", "ङ": "n",
    "च": "ch", "छ": "chh", "ज": "j", "झ": "jh", "ञ": "n",
    "ट": "t", "ठ": "th", "ड": "d", "ढ": "dh", "ण": "n",
    "त": "t", "थ": "th", "द": "d", "ध": "dh", "न": "n",
    "प": "p", "फ": "ph", "ब": "b", "भ": "bh", "म": "m",
    "य": "y", "र": "r", "ल": "l", "ळ": "l", "व": "v",
    "श": "sh", "ष": "sh", "स": "s", "ह": "h",
}  # fmt: skip
# Nukta forms (precomposed or base + U+093C).
_NUKTA: dict[str, str] = {
    "क": "k", "ख": "kh", "ग": "g", "ज": "z", "ड": "r", "ढ": "rh", "फ": "f", "य": "y",
}  # fmt: skip
_VOWELS: dict[str, str] = {
    "अ": "a", "आ": "aa", "इ": "i", "ई": "ee", "उ": "u", "ऊ": "oo", "ऋ": "ri",
    "ए": "e", "ऐ": "ai", "ओ": "o", "औ": "au", "ऑ": "o", "ऍ": "e",
}  # fmt: skip
_MATRAS: dict[str, str] = {
    "ा": "aa", "ि": "i", "ी": "ee", "ु": "u", "ू": "oo", "ृ": "ri",
    "े": "e", "ै": "ai", "ो": "o", "ौ": "au", "ॉ": "o", "ॅ": "e",
}  # fmt: skip
_VIRAMA = "्"
_NUKTA_SIGN = "़"
_ANUSVARA = {"ं": "n", "ँ": "n"}
_VISARGA = "ः"
_DIGITS = str.maketrans("०१२३४५६७८९", "0123456789")
_DEVANAGARI_WORD = re.compile(r"[ऀ-ॿ]+")


def has_devanagari(text: str) -> bool:
    return bool(_DEVANAGARI_WORD.search(text))


def _syllables(word: str) -> list[tuple[str, str | None]]:
    """Split into (consonant_or_vowel_latin, vowel) units.

    vowel: None = inherent schwa, "" = suppressed (virama), else the matra.
    Independent vowels come back as ("", vowel).
    """
    out: list[tuple[str, str | None]] = []
    chars = unicodedata.normalize("NFD", word)
    i = 0
    while i < len(chars):
        ch = chars[i]
        if ch in _CONSONANTS:
            cons = _CONSONANTS[ch]
            if i + 1 < len(chars) and chars[i + 1] == _NUKTA_SIGN:
                cons = _NUKTA.get(ch, cons)
                i += 1
            vowel: str | None = None
            if i + 1 < len(chars):
                nxt = chars[i + 1]
                if nxt in _MATRAS:
                    vowel = _MATRAS[nxt]
                    i += 1
                elif nxt == _VIRAMA:
                    vowel = ""
                    i += 1
            out.append((cons, vowel))
        elif ch in _VOWELS:
            out.append(("", _VOWELS[ch]))
        elif ch in _ANUSVARA:
            out.append(("n", ""))
        elif ch == _VISARGA:
            out.append(("h", ""))
        # danda, other marks: dropped
        i += 1
    return out


def romanise_word(word: str) -> str:
    syl = _syllables(word)
    parts: list[str] = []
    for idx, (cons, vowel) in enumerate(syl):
        if vowel is not None:
            parts.append(cons + vowel)
            continue
        # Inherent schwa: drop word-finally; drop medially in V-C(a)-C+matra contexts
        # ("namkeen", "kitnaa", "pichhlee") when the previous unit carries a vowel.
        is_last = idx == len(syl) - 1
        nxt = syl[idx + 1] if not is_last else None
        prev_has_vowel = idx > 0 and syl[idx - 1][1] not in ("",)
        next_has_matra = nxt is not None and nxt[0] != "" and nxt[1] not in (None, "")
        if is_last or (prev_has_vowel and next_has_matra and idx > 0):
            parts.append(cons)
        else:
            parts.append(cons + "a")
    return "".join(parts)


def romanise(text: str) -> str:
    """Romanise every Devanagari run in `text`; leave Latin, digits and punctuation alone."""
    text = text.translate(_DIGITS).replace("।", ".").replace("॥", ".")
    return _DEVANAGARI_WORD.sub(lambda m: romanise_word(m.group(0)), text)


_SKELETON_SUBS = (("ee", "i"), ("oo", "u"), ("aa", "a"), ("w", "v"), ("z", "j"), ("q", "k"))
_REPEATS = re.compile(r"(.)\1+")
_NON_ALNUM = re.compile(r"[^a-z0-9]")


def skeleton(word: str) -> str:
    """Spelling-tolerant key: 'udhaar'/'udhar'/'udhhar' -> 'udhar', 'theek'/'thik' -> 'thik'."""
    s = word.lower()
    for a, b in _SKELETON_SUBS:
        s = s.replace(a, b)
    s = _NON_ALNUM.sub("", s)
    return _REPEATS.sub(r"\1", s)
