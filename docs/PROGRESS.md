# Progress

Deadline **10 Nov 2026**. The day plan (MASTER_PROMPT §7): Phases 0–1 by 2 Nov · 2–3 by 4 Nov · 4–5 by 6 Nov · 6–7 by 7 Nov · 8 and filming on 8 Nov · posting on 9 Nov.

| Phase | Status | Date |
|---|---|---|
| 0. Setup | ✅ done (repo created; push is waiting on the gh `workflow` scope) | 2026-11-01 |
| 1. Gnani voice | 🟡 code and offline tests done; live acceptance waiting for approval to spend credits | 2026-11-01 |
| 2. NLU | ⏳ next | |
| 3. Ledger | — | |
| 4. Voice loop API | — | |
| 5. Frontend | — | |
| 6. Hardening | — | |
| 7. Deploy | — | |
| 8. Demo kit | — | |

## Phase 0: Setup (2026-11-01)

**Done**
- Toolchain: uv 0.13.6, Python 3.12.16 (managed by uv), GNU make 4.4.1, Node 24, pnpm 9, ffmpeg 9 and Docker 29.
- Backend: FastAPI app factory, typed settings (secrets are `SecretStr`), structlog JSON logs with request IDs, a friendly error handler, `/api/health` and `/api/ready`, an Alembic skeleton, and a Dockerfile (python:3.12-slim with ffmpeg, non-root user).
- Frontend: Next.js 14.2.33, TypeScript, Tailwind and shadcn (button, card, badge); an `/api` proxy to the backend; a placeholder home page with a server-side health badge; a PWA manifest and icon.
- `Makefile` (`install`, `dev`, `test`, `lint`, `fmt`, `migrate`, `smoke-voice` stub, `docker-up`), `infra/docker-compose.yml` (backend and Postgres 16), and `.github/workflows/ci.yml` (backend, frontend and docker jobs).
- `docs/DOC_DIFFS.md`: live Gnani docs compared with the skill (15 items).

**Metrics**
- pytest: 14 passed. vitest: 4 passed. ruff, mypy `--strict` (12 files), eslint and tsc are clean.
- `make dev`: backend on :8000 and frontend on :3000 both return 200, and the frontend shows "Server chalu hai" via the backend.
- `pnpm build` passes. The Docker image boots, migrates, and serves `/api/health` and `/api/ready`.

**Open issues**
- Repo is https://github.com/Maheen-M02/kirana-khata (public). The push was rejected: the gh token lacks the `workflow` scope.
- The Gnani key is now in `.env`. It had been pasted into `.env.example`; I moved it out before any push, and git history is clean. A CI secret scan now guards against this.
- Evon hosting is undecided (running `NLU_MODE=rules` for now).
- Run `make` from Git Bash on Windows: PowerShell may resolve `bash` to WSL.
- The winget PATH entries for uv and make only appear in shells opened after the install.

## Phase 1: Gnani voice (2026-11-01)

**Done**
- `app/voice/`: audio prep (ffmpeg), the `GnaniTransport` (auth, retries, error mapping, logging), the `SingleFlight` gate shared by STT and TTS, the `FileCreditGuard` (daily, IST), `GnaniSTT` (REST v3), `GnaniTTS` (REST and SSE, sha256 disk cache), `FakeSTT`/`FakeTTS`, and a factory. See [VOICE.md](VOICE.md).
- `scripts/smoke_voice.py`, plus `make smoke-voice`, `make tts-say` and `make test-live` (all opt-in; they spend credits).
- Fixtures in `tests/fixtures/gnani/` taken from the documented response and error bodies. Recorded ones get added with `--record`.
- Found and fixed a truncation bug in the skill's ffmpeg command (DOC_DIFFS #16): a clip with a mid-sentence pause was cut from 2.8 s to 0.52 s.

**Metrics**
- pytest: 81 passed (67 new voice tests; the ffmpeg tests use real encodes of webm/opus and m4a/aac). The `live` test is deselected by default.
- ffmpeg prep: about 120 ms for a 2.8 s clip.
- Offline CLI run against an unresolvable host: 3 attempts with backoff, mapped to `upstream`, friendly line shown, and the key never appears in output.

**Not done (acceptance)**
- "A real wav goes to a transcript, and text comes back as playable audio" needs a live run (about 6 credits). Waiting for approval.
- No recorded fixtures yet. They come from that same live run (`--record`).

**Open issues**
- The credit guard counts a call before sending it, so calls that fail on the network are counted too (conservative).
- The credit counter lives in a JSON file; it moves to the DB in Phase 3.
