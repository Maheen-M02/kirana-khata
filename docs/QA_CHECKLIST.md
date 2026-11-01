# QA checklist (`qa-voice-testing` skill): status at the end of Phase 6

Legend: ✅ pass (automated test) · 🟡 partial · ❌ not done. Test paths are relative to `backend/tests/` unless they start with `frontend/`.

## Edge cases

| Check | Status | Evidence |
|---|---|---|
| Mic permission denied → clear Hinglish help | ✅ | `frontend/components/voice-console.test.tsx` "mic permission denied" |
| Double tap / double submit → no duplicate | ✅ | `ledger/test_voice_loop.py::test_double_tap_and_double_haan_book_once`, plus the DB unique index `uq_ledger_entry_voice_event` |
| Network drop mid-upload → queued in IndexedDB and retried | ❌ | Not built. The UI shows "Internet nahi hai…" and keeps the open question (`voice-machine.test.ts` offline case). Listed as an extra in MASTER_PROMPT. |
| Empty STT transcript → "Awaaz saaf nahi aayi…" | ✅ | `test_voice_loop.py::test_empty_transcript` |
| Gnani 429/5xx → retried, then friendly; never half-written | ✅ | `unit/voice/test_transport.py` (retries, backoff, no 4xx retry), `test_voice_loop.py::test_gnani_rate_limit_is_friendly_and_writes_nothing` |
| Evon down or timing out → rules fallback | ✅ | `unit/nlu/test_parser.py::test_evon_down_uses_rules`, `::test_evon_timeout_uses_rules` |
| Ambiguous customer → question | ✅ | `test_voice_loop.py::test_two_sharmas_ask_then_tap`, `::test_disambiguate_by_voice` |
| New customer → creation confirmation | ✅ | `test_voice_loop.py::test_new_customer_created_on_haan` |
| Amount missing → "Kitne rupaye?" | ✅ | `test_voice_loop.py::test_missing_amount_is_asked` |
| Amount over ₹50,000 → extra confirmation | ✅ | `test_voice_loop.py::test_large_amount_needs_two_haans` |
| Undo → reversal, balance restored | ✅ | `test_voice_loop.py::test_undo_by_voice`, `ledger/test_service.py`, `ledger/test_properties.py` |
| Concurrent requests: TTS single-flight holds, no deadlock | ✅ | `unit/voice/test_transport.py::test_concurrent_stt_and_tts_are_serialised`, `test_credit_guard_and_gate.py::test_single_flight_releases_on_error` |
| Clips over 28 s or under 0.4 s rejected before credits are spent | ✅ | `unit/voice/test_audio.py`, `test_voice_loop.py::test_accidental_tap_rejected_before_stt` (STT never called) |
| Auth: wrong PIN limited (5 per 15 min), JWT expiry, shop isolation | ✅ | `ledger/test_auth_hardening.py` (lockout, forged/expired tokens, cross-shop 404s) |
| Unicode: Devanagari names stored and displayed | ✅ | `test_auth_hardening.py::test_devanagari_names_round_trip` |
| Time zone: "aaj" means Asia/Kolkata | ✅ | `ledger/test_service.py::test_sales_today_uses_ist_day`, `test_credit_guard_and_gate.py::test_guard_resets_at_ist_midnight_not_utc` |
| PWA installs on Android; app shell works offline | 🟡 | Installability checked locally (manifest, icons, SW, offline page; see `FRONTEND.md`). Needs an Android device over HTTPS after the deploy. |

## Production hardening

| Item | Status | Evidence |
|---|---|---|
| CORS restricted to the frontend origin | ✅ | `app/main.py` (`FRONTEND_ORIGIN`) |
| Request size limit 2 MB | ✅ | `test_auth_hardening.py::test_body_limit_rejects_before_reading`, `test_voice_loop.py::test_upload_limits_and_prod_guard` |
| Rate limits per shop | ✅ | 30 voice turns/min per shop; login lockout. `test_voice_turns_are_rate_limited_per_shop`. A small in-process limiter instead of slowapi, since there's one backend instance. |
| Structured JSON logs with request_id; PII limited | ✅ | `core/logging.py`, request-id middleware. Logs record intent, latency and kind, never the key, raw audio or PINs. |
| Audio retained 7 days, then deleted | ✅ | `core/retention.py` (runs at startup and every 6 h), `test_audio_retention_deletes_only_old_files` |
| `/health` and `/ready` | ✅ | `integration/test_health.py` (ready never spends credits) |
| Migrations on deploy; demo seed | ✅ | Dockerfile CMD runs `alembic upgrade head`; `make seed` / `make set-pin`; CI runs `alembic check` |
| Optional Sentry DSN | ❌ | Not added (optional; no DSN). |
| Uncaught errors → friendly JSON, no stack trace | ✅ | `core/errors.py` catch-all handler (implemented; no dedicated test yet) |
| **Tests never spend credits** (CLAUDE.md) | ✅ | Root `pytest_configure` masks keys unless `-m live`; the transport tripwire raises when `KK_BLOCK_PAID_CALLS=1`. `unit/voice/test_no_paid_calls.py` |
| Weak `JWT_SECRET` refused in prod | ✅ | `test_weak_jwt_secret_refused_in_prod` |

## Pre-demo release gate (runs 24 h before filming, Phases 7–8)

Not run yet. It needs the deployed app, real phone recordings, a hosted Evon and the remaining credits checked on the Gnani dashboard.
