# Progress

Deadline **10 Nov 2026**. The day plan (MASTER_PROMPT §7): Phases 0–1 by 2 Nov · 2–3 by 4 Nov · 4–5 by 6 Nov · 6–7 by 7 Nov · 8 and filming on 8 Nov · posting on 9 Nov.

| Phase | Status | Date |
|---|---|---|
| 0. Setup | ✅ done locally (CI isn't confirmed: no GitHub remote yet) | 2026-11-01 |
| 1. Gnani voice | ⏳ next | |
| 2. NLU | — | |
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
- No GitHub remote, so CI hasn't run yet. Waiting on approval to create the repo.
- No `GNANI_API_KEY` (no `.env`). Phase 1's live acceptance and the recorded fixtures depend on it.
- Evon hosting is undecided (running `NLU_MODE=rules` for now).
- Run `make` from Git Bash on Windows: PowerShell may resolve `bash` to WSL.
- The winget PATH entries for uv and make only appear in shells opened after the install.
