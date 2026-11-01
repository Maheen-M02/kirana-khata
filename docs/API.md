# API

Base URL: `/api`. The frontend reaches it through the Next.js rewrite, so it's same-origin. Money is always **integer paise** plus a `*_display` string (`"₹1,20,000"`), so the browser never does arithmetic on rupees.

Errors come back as `{"error": {"code": "...", "message": "<short Hinglish line>"}}` and never include a stack trace. Validation errors use FastAPI's 422.

> **Auth:** until Phase 6, every route acts on the single dev shop (`make seed`). Phase 6 adds the phone + PIN JWT cookie. The routes already scope every query by the shop id.

## Health

| Method | Path | Notes |
|---|---|---|
| GET | `/health` | Liveness check |
| GET | `/ready` | `{status, checks: {db, gnani, evon}}`. Returns 503 if the DB is down. Never spends Gnani credits. |

## Customers

| Method | Path | Body / query | Returns |
|---|---|---|---|
| GET | `/customers` | n/a | `[CustomerOut]`: every customer with `balance_paise`, sorted by name |
| POST | `/customers` | `{display_name, phone?, aliases?[]}` | 201 `CustomerOut`. 409 if the name exists. |
| GET | `/customers/{id}` | `?limit=100` | `CustomerDetail` (CustomerOut plus `entries[]`, newest first) |
| POST | `/customers/{id}/aliases` | `{alias}` | `CustomerOut` (learns a spoken variant) |

`CustomerOut = {id, display_name, aliases[], phone, balance_paise, balance_display, last_activity}`. A negative balance is an advance.

## Ledger

| Method | Path | Body / query | Returns |
|---|---|---|---|
| GET | `/ledger/entries` | `?day=today\|all&customer_id=&limit=100` | `[EntryOut]`, newest first |
| POST | `/ledger/entries` | `{type: credit_sale\|cash_sale\|payment_received, amount_paise: int>0, customer_id?, note?, lines?[]}` | 201 `EntryOut`. Tapping "save" in the UI is the explicit confirmation. |
| POST | `/ledger/entries/{id}/reverse` | n/a | The reversal `EntryOut` (negative amount). 409 if already cancelled. |
| POST | `/ledger/undo` | n/a | `{reversal, original_id, speak}`. Reverses the newest live entry; 409 `nothing_to_undo`. |

`EntryOut = {id, type, amount_paise, amount_display, customer_id, customer_name, note, created_at, is_reversal, reverses_entry_id, reversed_by, voice_event_id, lines[]}`

## Reports

| Method | Path | Returns |
|---|---|---|
| GET | `/reports/today` | `{total_paise, cash_paise, credit_paise, payments_paise, entries, total_display, speak}` for the IST day |
| GET | `/reports/dues?limit=5` | `{customers[], total_paise, total_display, speak}`: who owes the most, highest first |

`speak` holds the ready-made Hinglish line for Timbre, e.g. `"Aaj ki bikri chaar sau sattar rupaye, 3 entry."`

## Voice (Phase 4)

| Method | Path | Body | Returns |
|---|---|---|---|
| POST | `/voice/turn` | multipart `audio` (webm/opus, m4a, wav… ≤ 2 MB) plus the `Idempotency-Key` header (8–64 chars) | `TurnOut` |
| POST | `/voice/{event_id}/confirm` | JSON `{accept?: bool, customer_id?: int, amount_paise?: int}` **or** multipart `audio` ("haan", a name, or an amount) | `TurnOut` |
| GET | `/voice/audio/{sha256}.mp3` | n/a | Cached Timbre audio (immutable) |

```
TurnOut = {event_id, status: pending|confirmed|rejected|failed,
           stage: confirm|confirm_large|disambiguate|customer|amount|done|error,
           transcript, intent, confirm_text, confirm_audio_url, needs_confirmation,
           options: [{customer_id, name}], entry_id, customer_id, balance_paise,
           latency_ms: {stt, nlu, tts, total}}
```

- **Play** `confirm_audio_url` and show `confirm_text` (the text is always present, even when TTS fails).
- **`needs_confirmation`:** show ✓/✗, or send the next "haan" clip to `/confirm`. A bare "haan" sent to `/voice/turn` also confirms the latest open question.
- **`stage = disambiguate`:** render `options` as buttons, then send `{customer_id}`.
- **`stage = amount`:** the user says or types the amount, then send `{amount_paise}` or the audio.
- **Same `Idempotency-Key` twice:** returns the same response. A second accept on an event replays the first result. The database allows at most one ledger row per voice event.
- **Dev only (not in `prod`):** a multipart `transcript` field may replace `audio`, so the UI can be tested without spending credits.
