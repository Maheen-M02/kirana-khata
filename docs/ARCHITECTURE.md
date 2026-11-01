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
| 2026-11-01 | `timbre-v2.5` with voice `Poorvi` and `hi-en` | Poorvi is the only v2.5 voice whose preferred language is Hinglish. `timbre-v3.0` + `Shivani` is the A/B alternative for Phase 1. |
| 2026-11-01 | Start with `NLU_MODE=rules`; Evon hosting is undecided | Unblocks Phases 2–4. Evon gets swapped in through the adapter once it's hosted (GPU vLLM is preferred for latency). |
| 2026-11-01 | Evon dev URL is `:8080` | The kit's default `:8000` clashed with the backend. 8080 is llama-server's default. |
| 2026-11-01 | Deploy targets: Render (backend), Vercel (frontend), Neon (Postgres) | Free tiers, Docker support, and HTTPS by default. |

## Evon hosting

Undecided. Recorded options are in `.claude/skills/evon-llm/SKILL.md`. This section gets updated when one is chosen.
