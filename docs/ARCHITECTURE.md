# Architecture

## Components

| Layer | Tech | Notes |
|---|---|---|
| Client | Next.js 14 (App Router) PWA, Tailwind, shadcn/ui | Server components by default; only the recorder and player are client components. `/api/*` is rewritten to the backend, so the auth cookie stays same-origin. |
| API | FastAPI on Python 3.12, Pydantic v2 | App factory in `app/main.py`. Each request gets an `x-request-id` that is bound into structlog. |
| Voice | Gnani Prisma v3.0 (REST `/stt/v3`) and Timbre v2.5 (`/api/v1/tts/sse`, `/inference`) | All calls go through one process-wide semaphore (`GNANI_MAX_CONCURRENCY=1`), because the account allows 1 active request across STT and TTS. |
| NLU | Evon behind an OpenAI-compatible adapter, plus a deterministic rules parser | `NLU_MODE=rules\|hybrid\|evon` |
| Data | SQLAlchemy 2 (sync) with Alembic. SQLite in dev, Postgres (psycopg 3) in prod. | `postgres://` URLs are normalised to `postgresql+psycopg://`. Alembic uses `render_as_batch` so migrations also work on SQLite. |
| Ops | Docker (python:3.12-slim with ffmpeg); GitHub Actions CI | The container runs `alembic upgrade head` on boot. |

## Voice turn (target ≤ 3.5 s p50 from mic release to first audio)

1. Upload (webm/opus) → ffmpeg converts to 16 kHz mono WAV and trims silence. Clips under 0.4 s or over 28 s are rejected before any credits are spent.
2. Prisma STT with `format` always set explicitly (v3's default changes with the language) and the language hints `hi-IN,en-IN`.
3. NLU: Evon returns JSON (thinking disabled, 4 s timeout), validated with Pydantic. The rules parser is both the fallback and a cross-check on the amount.
4. Customer resolution with rapidfuzz plus a phonetic key. Ambiguous matches trigger a question back.
5. The confirmation text has numbers written as Hinglish words and is spoken by Timbre through the single-flight queue. Phrases are cached by sha256.
6. A `voice_event` is saved with the transcript, JSON, confidence, latency per stage and status.

## Decisions log

| Date | Decision | Why |
|---|---|---|
| 2026-11-01 | Sync SQLAlchemy instead of async | Simpler Alembic setup, and one code path for SQLite and Postgres. DB calls are tiny next to the STT and TTS round trips. |
| 2026-11-01 | One Gnani semaphore shared by STT and TTS | The live docs say the 1-active-request limit applies per account ([DOC_DIFFS #1](DOC_DIFFS.md)). |
| 2026-11-01 | ~~`timbre-v2.5` + `Poorvi`~~, replaced by **`timbre-v3.0` + `Shivani` + `hi-en`** | Chosen by the owner after a live A/B. It also had the faster first chunk (308 vs 368 ms). |
| 2026-11-01 | Start with `NLU_MODE=rules`; Evon hosting is undecided | Unblocks Phases 2–4. Evon gets swapped in through the adapter once it's hosted (GPU vLLM is preferred for latency). |
| 2026-11-01 | Evon dev URL is `:8080` | The kit's default `:8000` clashed with the backend. 8080 is llama-server's default. |
| 2026-11-01 | Deploy targets: Render (backend), Vercel (frontend), Neon (Postgres) | Free tiers, Docker support, and HTTPS by default. |
| 2026-11-01 | STT `format=transcribe` stays the default | Live A/B on the same clip: `transcribe` gave `120`/`2 kg` as digits plus Devanagari words (637 ms); `transliterate` gave Latin with numbers as words (592 ms). Digits remove the riskiest failure (misheard number words). Rules handle both. |
| 2026-11-01 | Custom Devanagari romaniser, not `indic-transliteration` | Colloquial spellings ("udhaar") so one keyword and number table serves both scripts. |
| 2026-11-01 | Ledger strictly insert-only: reversal rows carry `reverses_entry_id`; `reversed_by` is derived | The spec's `reversed_by` column would require updating the original. Triggers can forbid every UPDATE only if none is ever needed. |
| 2026-11-01 | Ledger tests on SQLite and Postgres (CI service) | Triggers, CHECKs and `SUM(bigint)` types differ between engines; prod is Postgres. |
| 2026-11-01 | Evon served by vLLM on Modal (A100-80GB on the $30/month free credits), script prepared but not deployed | The HF card confirms the vLLM flags. `nemotron_h` makes GGUF support uncertain. See `infra/evon/README.md`. |

## Evon hosting

Planned: vLLM on Modal (one H100, scale to zero, warm before filming). The script and steps are in [`infra/evon/`](../infra/evon/README.md). Until it's deployed, `NLU_MODE=rules`.
