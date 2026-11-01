---
name: qa-voice-testing
description: Use when writing tests, running QA, hardening for production, or doing the pre-demo release check for the Kirana Khata voice app.
---

# QA and hardening for the voice ledger

## Test pyramid

1. **Unit** (fast, most numerous): numbers_hi, rules parser, resolver, confirmation templates, ledger service. Use `hypothesis` property tests so that sum(entries) equals balance, a reversal nets to zero, and paise are never floats.
2. **Golden NLU eval:** run `pytest tests/test_golden.py` against FakeEvon (canned responses) and the rules parser. Add `-m live` to run against real Evon and print accuracy per tag. The gate is ≥ 90% intent accuracy and 0 wrong amounts committed without confirmation.
3. **Integration:** FastAPI TestClient with an audio fixture through FakeSTT, the NLU, FakeTTS, the confirm endpoint and the DB, then assert the balance.
4. **Live smoke** (manual, spends credits): `make smoke-voice` with 10 real recordings.
5. **Frontend:** vitest for the recorder state machine, and one Playwright e2e that grants mic access with a fake media stream (`--use-fake-device-for-media-stream --use-file-for-fake-audio-capture=fixture.wav`).

## Audio fixtures to record yourself (`tests/audio_fixtures/`)

Record 20 or more clips on a phone, covering:

- quiet room
- shop with background chatter
- traffic or road noise
- a fan running
- a TV playing
- a soft-spoken older voice
- fast speech
- Marathi
- a Devanagari-style Hindi speaker
- a 0.3 s accidental tap
- 29 s of rambling
- silence only

Store each clip's expected transcript and intent in `fixtures.yaml`.

## Edge-case checklist (each item needs a test or a manual tick)

- [ ] Mic permission denied: a clear Hinglish explanation plus how to enable it
- [ ] Double tap or double submit: the idempotency key prevents a duplicate entry
- [ ] Network drops mid-upload: the clip is queued in IndexedDB and retried, and the UI shows "Bheja ja raha hai…"
- [ ] STT returns an empty transcript: "Awaaz saaf nahi aayi, dobara boliye"
- [ ] Gnani 429 or 5xx: retried, then a friendly message, and the entry is never half-written
- [ ] Evon down or timing out: the rules fallback is used and the demo still works
- [ ] Ambiguous customer leads to a disambiguation question
- [ ] New customer leads to a creation confirmation
- [ ] Amount missing ("Sharma ji ne cheeni li"): asks "Kitne rupaye?"
- [ ] Very large amount (> ₹50,000): extra confirmation
- [ ] Undo after a commit creates a reversal entry, and the balance is restored
- [ ] Concurrent requests: the TTS single-flight queue holds and nothing deadlocks
- [ ] Clips over 28 s and under 0.4 s are rejected before any credits are spent
- [ ] Auth: wrong PIN is rate-limited (5 per 15 min), JWT expiry is handled, and one shop can't see another's data
- [ ] Unicode: Devanagari names are stored and displayed correctly
- [ ] Time zone: "aaj" uses Asia/Kolkata, not UTC
- [ ] PWA: installs on Android, and the app shell works offline

## Production hardening

- CORS restricted to the frontend origin, a request size limit of 2 MB, and rate limits per shop (slowapi)
- Structured JSON logs with request_id, and PII limited to customer names
- Audio retained for 7 days, then deleted by a cron or startup task
- `/health` (liveness) and `/ready` (DB, Gnani and Evon reachability)
- Alembic migrations run on deploy; seed script for the demo shop
- Optional Sentry DSN; uncaught errors return a friendly JSON error and never a stack trace

## Pre-demo release gate (run 24 h before filming)

1. Run `make lint test` and confirm CI is green.
2. Run the golden live eval, then record the numbers in the README.
3. Run 20 live voice turns on a phone over mobile data and record p50/p95 latency from `/debug`.
4. Warm up Evon so there's no cold start, and pre-warm the TTS cache.
5. Check credits remaining in the Gnani dashboard (≥ 1,000 left).
6. Have a fallback ready: the rules-only mode flag works if the GPU dies.

Report results as a table: check | pass/fail | evidence.
