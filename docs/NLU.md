# NLU (Phase 2)

The code lives in `backend/app/nlu/`. It turns a Prisma transcript into a `ParsedIntent`, with money as integer paise. **The LLM is never trusted with money.**

```
transcript ─┬─> rules.parse_rules ───────────────┐  (always; about 1 ms; deterministic)
            └─> EvonParser (JSON, 4 s budget) ───┤
                                                 v
                              HybridParser.merge: Evon decides the wording-heavy intent,
                              rules decide the AMOUNT, and disagreements become flags
                                                 v
                        ParsedIntent(intent, customer, items, amount_paise, flags, confidence)
                                                 v
                      resolver.resolve(customer) -> matched | ambiguous (ask) | new (offer)
                                                 v
                      templates.confirm_text -> "Sharma ji, ek sau bees rupaye udhaar. Sahi hai?"
```

| Module | Job |
|---|---|
| `translit.py` | Devanagari → Hinglish Latin with schwa deletion (उधार → udhaar, नमकीन → namkeen), plus a `skeleton()` key that tolerates spelling drift. |
| `numbers_hi.py` | Parses numbers into paise (digits, ₹, 1.5k, all 1–99 Hindi forms, sau/hazaar/lakh/crore, dedh/dhai/sava/saade/paune, Devanagari, Marathi basics including `donshe`, rupees and paise) and speaks paise back as Hinglish words. Exact `Fraction` maths: money never touches a float. `find_amount` picks the money phrase in a sentence and flags corrections, multiple amounts and unmarked numbers. |
| `rules.py` | The deterministic intent parser, used as both the fallback and the cross-check. It handles negation ("udhaar nahi, cash"), corrections ("teen sau… nahi, do sau"), goods minus paid ("100 ka saaman, 50 diye" = 50 credit), "likh do" (not "two"), and Marathi suffixes. |
| `resolver.py` | Matches the spoken name to a customer: honorifics stripped, rapidfuzz plus a phonetic key, per-word min-of-best scoring. It returns a match, a question ("Kaun se Sharma ji: Ramesh ya Suresh?"), or an offer to create a new customer. It also suggests aliases to learn. |
| `prompts.py`, `evon_client.py` | Evon over an OpenAI-compatible API: thinking off, temperature 0.2, JSON-only prompt with 12 few-shot examples, `<think>`/fence stripping, one retry that includes the validation error. |
| `parser.py` | `RulesParser`, `EvonParser` and `HybridParser`. `NLU_MODE` selects one via `factory.py`. |
| `schema.py` | `EvonOutput` (strict LLM contract) and `ParsedIntent` (`needs_confirmation` is true for all money and undo). |
| `templates.py` | Confirmation, commit, balance, dues and sales lines, with numbers always spoken as words. |

## How money stays safe

1. Every money intent needs a "haan" (`needs_confirmation`).
2. The rules amount wins. If Evon disagrees: `amount_mismatch`. If only Evon found an amount: `evon_amount_only`. If none was found: `amount_missing`, and the app asks "Kitne rupaye?".
3. Extra unmarked numbers, corrections, amounts over ₹50,000 and low confidence all set flags that force an explicit read-back.
4. Golden gate: **0 amounts that are wrong and not flagged**. This is enforced in CI on both sets.

## Results (rules parser, offline, `make eval-nlu`)

| Set | Cases | Intent | Customer | Amounts |
|---|---|---|---|---|
| `golden_utterances.yaml` (tuned on) | 81 | 100% | 100% | 54/54 exact |
| `golden_holdout.yaml`, **first blind run** | 30 | **90.0%** | 96.7% | 18/19 exact, **1 wrong and unflagged** (fixed) |
| `golden_holdout.yaml` after the fixes | 30 | 100% | 100% | 19/19 exact |

The **blind holdout number (90%)** is the honest estimate of how the rules generalise. After it was used for fixes, the holdout no longer counts as unseen, so new holdout cases should be added over time. Evon results come from `make test-live` once Evon is hosted (`infra/evon/`).

## Deviations from the `hinglish-ledger-nlu` skill

- **Transliteration:** a hand-rolled colloquial romaniser instead of `indic-transliteration`. Scholarly schemes give "udhāra"/"sharmā"; we need "udhaar"/"sharma" to share one keyword table with romanised speech.
- **Name scoring:** every spoken word must match a word of the stored name. Plain `token_set_ratio` scored "Suresh Sharma" 100 against the alias "Sharma ji" (subset) and would have booked the wrong Sharma.
- **STT format:** `transcribe` (digits plus Devanagari) is kept as the default after the live A/B in `VOICE.md`. Both shapes are in the golden set.
