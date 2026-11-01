---
name: hinglish-ledger-nlu
description: Use when parsing Hinglish/Hindi/Marathi shop utterances into ledger intents, converting spoken numbers both ways, resolving customer names, or editing the golden utterance test set.
---

# Hinglish ledger NLU

## Intents and their effects

| Intent | Typical phrases | Effect |
|---|---|---|
| credit_sale | "udhaar", "khate mein likho", "baad mein dega", "baaki" | +balance for the customer |
| cash_sale | "nakad", "cash mein", or no customer named | sales total only |
| payment_received | "jama kiye", "de gaye", "paise diye", "online bheje" | −balance |
| query_balance | "X ka hisaab", "X ka kitna baaki" | read only |
| query_sales_today | "aaj kitni bikri", "aaj ka total" | read only |
| query_dues_list | "kis kis ka baaki", "udhaar list" | read only (top 5 spoken) |
| undo_last | "pichhli entry cancel", "galat ho gaya" | reversal after confirmation |
| confirm_yes / confirm_no | "haan / ha / sahi / theek / yes" · "nahi / na / galat / no" | confirm step |

## Numbers (`numbers_hi.py`): build this first, test it heavily

**Parse (words to integer paise).** It must handle:

- Digits and mixed forms: "120", "1,200", "₹120", "120 rs", "1.5k"
- Hindi words with **all 1–100 unique forms**: ek, do, teen … gyarah, barah … ikkees, baais … ninyanve, sau
- Scales: sau, hazaar/hajar, lakh/laakh. Examples: "dedh sau" = 150, "dhai hazaar" = 2500, "sava sau" = 125, "saade teen sau" = 350, "paune do sau" = 175
- Fractions: aadha, dedh (1.5), dhai (2.5), sava (+¼), saade (+½), paune (−¼)
- Devanagari: "एक सौ बीस"
- Marathi basics: ek, don, teen, chaar, paach … shambhar (100), hajar
- Common STT spellings: bees/bis, pachaas/pachas, hazar/hajaar/hajar

**Speak (integer to words for TTS).** Hinglish romanised words: 120 → "ek sau bees", 1550 → "ek hazaar paanch sau pachaas", plus "rupaye" and, if there are paise, "aur X paise".

Golden tests: at least 80 cases in each direction, including round-trips.

## Units and items

kilo/kg, gram, litre, packet/packet, dabba, darjan (dozen), piece/nag. Store items free-text, normalised to lowercase. Don't build an item catalogue; it's out of scope.

## Customer resolution (`resolver.py`)

1. Normalise by lowercasing, stripping honorifics (ji, bhai, uncle, aunty, didi, saab, seth), transliterating Devanagari to Latin (use `indic-transliteration`), and collapsing doubled letters (sharmaa → sharma).
2. Match against display_name plus aliases using `rapidfuzz` token_set_ratio. Also compare a phonetic key (a simple Hindi-aware Soundex/Metaphone variant).
3. A score of ≥ 90 with one candidate auto-picks. Two or more candidates scoring ≥ 80 trigger a question: "Kaun se Sharma ji: Ramesh ya Suresh?" A score under 80 for a credit or payment intent triggers "Naya customer 'Sharma ji' bana doon?"
4. When the shopkeeper confirms a name, save the spoken variant as a new alias so the system learns.

## Confirmation text templates (short and natural)

- credit_sale: "{name}, {amount} udhaar. Sahi hai?" Then after commit: "Likh diya. {name} ka total baaki {balance}."
- payment_received: "{name} ne {amount} jama kiye. Sahi hai?"
- cash_sale: "{amount} nakad bikri. Sahi hai?"
- query_dues_list: "Sabse zyada baaki: {n1} {a1}, {n2} {a2}, {n3} {a3}."
- unknown: "Maaf kijiye, samajh nahi aaya. Dobara boliye."

## Golden set (`tests/golden_utterances.yaml`)

Have at least 60 cases. Each case has fields: `transcript`, `expected.intent`, `expected.customer`, `expected.amount_paise`, `tags` (hinglish, hindi_deva, marathi, noisy_typo, query, fraction). The CI report shows accuracy per tag. Include adversarial cases: two amounts in one sentence ("100 ka saaman, 50 diye" means credit 50, or ask), negation ("udhaar nahi, cash"), and corrections mid-sentence ("teen sau… nahi, do sau").
