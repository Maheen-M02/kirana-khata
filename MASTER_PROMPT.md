# MASTER PROMPT: Kirana Khata (paste this into Claude Code)

> Put this kit's `CLAUDE.md` and `.claude/skills/` folder in the root of an empty repo first, then paste everything below the line into Claude Code.

---

You are the lead engineer building **Kirana Khata**, a production-grade, voice-first bookkeeping app for Indian kirana (small grocery) shop owners. It is an entry for the Gnani AI "Great Indian AI Internship Challenge". **Hard deadline: 10 Nov 2026.** The finished product must be deployed, demo-ready and robust enough to film in a real, noisy shop.

Read `CLAUDE.md` and every skill in `.claude/skills/` before writing any code. Follow them strictly.

## 1. Product

A shopkeeper presses and holds one large mic button and speaks naturally in Hinglish, Hindi or Marathi, for example:

- "Sharma ji ne do kilo cheeni aur ek Parle-G liya, ek sau bees rupaye udhaar"
- "Gupta ji ne 300 rupaye jama kiye"
- "Aaj kitni bikri hui?" · "Kis kis ka paisa baaki hai?" · "Sharma ji ka hisaab batao"
- "Pichhli entry cancel karo"

The app then:

1. **Transcribes** the speech with **Gnani Prisma** (STT).
2. **Understands** it with **Gnani Evon** (LLM), producing a strict JSON intent with customer, items, amount and type. A deterministic Hinglish rule parser acts as fallback and validator.
3. **Confirms** it aloud with **Gnani Timbre** (TTS), for example "Sharma ji, ek sau bees rupaye udhaar. Sahi hai?" The shopkeeper says "haan" or "nahi", or taps ✓ / ✗.
4. **Commits** the entry to the ledger and speaks the new balance.
5. **Answers queries** by voice: today's sales, outstanding dues, one customer's balance and history.
6. Shows a simple visual ledger: today's entries, a customer list with balances, and a customer detail page.

Additional features (build only after the core is done):

- A spoken end-of-day summary
- A shareable WhatsApp payment-reminder text (`wa.me` deep link; no WhatsApp API)
- Offline queueing of recordings, synced when back online
- Marathi and Hindi UI toggle

## 2. Non-negotiable constraints

- All three Gnani models must sit in the main loop: Prisma (STT), Timbre (TTS) and Evon (LLM). Evon must sit behind an OpenAI-compatible adapter (see the `evon-llm` skill) so it can run on vLLM, SGLang or Ollama.
- **Never trust the LLM with money.** The model output is validated with Pydantic, amounts are integers in paise, totals are recomputed in code, and nothing is written to the ledger without explicit confirmation.
- Every voice event is stored with its audio reference, transcript, parsed JSON, confidence, latency per stage and status. This doubles as the debug trail and the demo metrics.
- Secrets go only in env vars. Never commit `.env` and never log API keys.
- Mobile-first PWA, one-thumb operation, 48px+ touch targets, readable at arm's length.

## 3. Stack (use this unless a skill says otherwise)

- **Backend:** Python 3.12, FastAPI, SQLAlchemy 2 plus Alembic, Pydantic v2, httpx (async), ffmpeg for audio conversion, structlog, pytest.
- **DB:** SQLite in dev and Postgres in prod (Neon or Supabase free tier). Everything must stay compatible with both.
- **Frontend:** Next.js 14 (App Router) plus TypeScript, Tailwind and shadcn/ui, MediaRecorder for audio, a PWA manifest and a service worker.
- **Auth:** Single shop owner. Phone number plus a 4-digit PIN gives a JWT in an httpOnly cookie. Keep it simple but real.
- **Deploy:** Backend on Render, Railway or Fly (Docker). Frontend on Vercel. Evon on the GPU option chosen in the `evon-llm` skill.
- **CI:** GitHub Actions runs lint (ruff, eslint), type checks (mypy, tsc) and tests on every push.

## 4. Repo layout

```
kirana-khata/
  backend/
    app/
      main.py  config.py  deps.py
      api/        (routes: auth, voice, ledger, customers, reports, health)
      voice/      (gnani_stt.py, gnani_tts.py, audio.py, tts_queue.py)
      nlu/        (evon_client.py, prompts.py, schema.py, rules.py, numbers_hi.py, resolver.py)
      ledger/     (models.py, service.py, queries.py)
      core/       (logging.py, errors.py, security.py)
    alembic/  tests/  (unit, integration, golden_utterances.yaml, audio_fixtures/)
    Dockerfile  pyproject.toml
  frontend/
    app/  components/  lib/  public/  (manifest, icons, sw)
  infra/      (docker-compose.yml, evon/ serving scripts)
  docs/       (ARCHITECTURE.md, API.md, DEMO_SCRIPT.md)
  .github/workflows/ci.yml
  README.md  .env.example
```

## 5. Data model (minimum)

- `shop` (id, name, owner_phone, pin_hash, default_language)
- `customer` (id, shop_id, display_name, aliases[] for Sharma ji / Sharmaji / Sharma uncle, phone?, created_at)
- `voice_event` (id, shop_id, audio_path, duration_ms, transcript, stt_model, detected_lang, nlu_json, nlu_source evon|rules, confidence, status pending|confirmed|rejected|failed, latency_stt_ms, latency_nlu_ms, latency_tts_ms, error, created_at)
- `ledger_entry` (id, shop_id, customer_id?, voice_event_id?, type credit_sale|cash_sale|payment_received|adjustment, amount_paise INT, note, created_at, reversed_by?). This table is **append-only**. Corrections are reversal entries and nothing is ever deleted.
- `ledger_line` (id, entry_id, item_name, qty, unit, amount_paise?)

A customer's balance is the sum of credit_sale minus payment_received, plus or minus adjustments, computed in SQL.

## 6. Voice pipeline (contract)

`POST /api/voice/turn` (multipart audio) returns `{event_id, transcript, intent, confirm_text, confirm_audio_url, needs_confirmation}`.
`POST /api/voice/{event_id}/confirm` with `{accept: bool}` or a "haan"/"nahi" audio clip commits or discards the entry and returns spoken feedback.

Steps:

1. Convert the uploaded audio to 16 kHz mono WAV with ffmpeg, trim leading and trailing silence, and reject anything under 0.4 s or over 28 s.
2. Prisma STT (REST v3) via the `gnani-voice-api` skill, with retry, timeout and error mapping.
3. NLU: send the transcript to Evon with a JSON-only prompt (thinking disabled), validate the result, and fall back to `rules.py`. Then resolve the customer with fuzzy matching against names and aliases. If it is ambiguous, ask: "Kaun se Sharma ji? Ramesh ya Suresh?"
4. Build the confirmation text, converting numbers to Hindi or Hinglish words (Timbre wants spoken-form numbers).
5. Timbre TTS goes through a **single-flight queue** because the API allows only 1 active request per key. Cache repeated phrases and stream with SSE where possible.
6. Persist the voice event with per-stage latency.

Target latency from release of the mic to the start of the confirmation audio: **≤ 3.5 s p50**. Measure it and show it on a hidden `/debug` page.

## 7. Execution plan: work in phases and stop after each one

At the end of **each** phase:

- run the tests and linters;
- update `docs/` and the README;
- commit with a clear message;
- print a short status report covering what works, what doesn't, what comes next, and any decision you need from me.

Then **wait for my "go"**.

| Phase | Deliverable | Acceptance criteria |
|---|---|---|
| 0. Setup | Scaffold, CI, docker-compose, `.env.example`, health endpoints | `make dev` runs both apps; CI is green |
| 1. Gnani voice | STT and TTS clients plus a CLI smoke test script | A real wav goes to a transcript, and text comes back as playable audio; errors are mapped; tests pass using recorded fixtures |
| 2. NLU | Evon adapter, schema, prompts, rules fallback, Hindi number parser, customer resolver | ≥ 90% intent accuracy on `golden_utterances.yaml` (≥ 60 cases); 100% of amounts correct or flagged for confirmation |
| 3. Ledger | Models, migrations, service, queries, REST API | Property tests show balances always reconcile; reversals work; the ledger is append-only |
| 4. Voice loop API | `/voice/turn` and `/confirm` end to end | An integration test runs audio fixture → committed entry → spoken balance |
| 5. Frontend | PWA with mic button, live states (listening, thinking, speaking), confirm UI, ledger screens | Works on Android Chrome over HTTPS; Lighthouse PWA and accessibility ≥ 90 |
| 6. Hardening | Auth, rate limits, input limits, structured logs, Sentry (optional), timeouts and retries, a graceful "samajh nahi aaya, dobara boliye" | Every QA checklist in the `qa-voice-testing` skill passes |
| 7. Deploy | Prod deploy, seed demo shop, `/debug` metrics page | Public HTTPS URL; a cold-start voice turn works from a phone |
| 8. Demo kit | `docs/DEMO_SCRIPT.md`, README with architecture diagram and GIF | Follows the `demo-launch` skill |

Day plan: Phases 0–1 by 2 Nov, Phases 2–3 by 4 Nov, Phases 4–5 by 6 Nov, Phases 6–7 by 7 Nov, Phase 8 and filming on 8 Nov, posting on 9 Nov. **10 Nov is buffer only.**

## 8. Engineering rules

- Use type hints everywhere, make mypy strict on `app/`, and keep functions small.
- External calls (Gnani, Evon) live behind interfaces with fakes for tests. Tests must never hit paid APIs, except an opt-in `pytest -m live` marker.
- Keep a **credit budget**: a `GNANI_CREDIT_GUARD` env var that refuses calls past N per day in dev, and log every billable call.
- Use idempotency keys on `/voice/turn` so a double tap doesn't double-book.
- Write user-facing strings in Hinglish, kept short and warm. Never show a raw error to the shopkeeper.
- If any doc or assumption is unclear (for example the Gnani API shape), **fetch the live docs** at https://docs.gnani.ai/llms.txt before coding. Don't guess.
- Don't add features outside this prompt without asking. Scope is the enemy; polish wins the demo.

Start with **Phase 0** now. First restate the plan in 10 lines or fewer and list any blocking questions, such as which API key to use and where Evon is hosted. Then begin.
