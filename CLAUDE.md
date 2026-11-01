# CLAUDE.md: Kirana Khata

This is a voice-first bookkeeping PWA for kirana shops, entered in the Gnani AI internship challenge. The deadline is **10 Nov 2026**. The full spec is in `MASTER_PROMPT.md`.

## Always

- Read the relevant skill in `.claude/skills/` before touching that area:
  - Gnani STT/TTS → `gnani-voice-api`
  - Evon LLM → `evon-llm`
  - Intent parsing, Hindi numbers, customer matching → `hinglish-ledger-nlu`
  - Tests and QA → `qa-voice-testing`
  - Demo, README and posting → `demo-launch`
- Money is an integer number of **paise**. Never use floats. The ledger is append-only; corrections are reversal entries.
- Nothing is written to the ledger without explicit user confirmation.
- Tests use fakes for Gnani and Evon. Real calls happen only under `pytest -m live`.
- Work in phases. Stop and report at the end of each one.

## Commands

- `make dev` runs the backend (:8000) and frontend (:3000).
- `make test` runs pytest plus vitest.
- `make lint` runs ruff, mypy, eslint and tsc.
- `make smoke-voice FILE=sample.wav` runs a live STT → NLU → TTS round trip and spends credits.

## Env vars (see .env.example)

`GNANI_API_KEY`, `GNANI_BASE_URL=https://api.vachana.ai`, `GNANI_STT_MODEL=prisma-v3.0`, `GNANI_TTS_MODEL=timbre-v2.5`, `GNANI_TTS_VOICE`, `EVON_BASE_URL`, `EVON_MODEL`, `EVON_API_KEY`, `DATABASE_URL`, `JWT_SECRET`, `GNANI_CREDIT_GUARD`.

## Style

- Backend: ruff, mypy strict, small pure functions in `nlu/` and `ledger/`, async IO at the edges.
- Frontend: server components by default, client components only for the recorder and player. Use Tailwind and shadcn.
- User-facing copy is short, warm Hinglish, with no jargon and no raw errors.
- Commit messages follow Conventional Commits.
