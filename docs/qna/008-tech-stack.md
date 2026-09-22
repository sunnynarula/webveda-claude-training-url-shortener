# 008. The tech stack

**Asked:** 2026-09-22 · **Updated:** 2026-09-22

> What is the tech stack of this application?

## Short answer

The backend is fully async Python on FastAPI, with PostgreSQL (through
SQLAlchemy and asyncpg) as the database, Redis for the redirect cache and the
rate-limit counters, and Alembic for migrations. The frontend is React, built
with Vite. It's tested with pytest and vitest, linted and type-checked with
ruff, mypy and eslint, and run locally with Docker Compose. Nothing is built
yet, so this is the stack the spec prescribes. Exact versions get pinned when
the code arrives.

## Answer

### The core (`CLAUDE.md` §2)

| Layer | Choice | Its job here | First needed at |
|---|---|---|---|
| Backend | Python 3.11+, FastAPI, fully async | The API: `/shorten`, the redirect, stats, health | Step 7 (scaffold) |
| Database | PostgreSQL, through SQLAlchemy's async engine and the `asyncpg` driver | Stores the `urls` table | Step 7 (container), step 9 (schema) |
| Cache and rate-limit store | Redis | Maps a short code to its URL for fast redirects, and holds rate-limit counters shared by every worker | Step 7 (container), steps 11 and 13 (code) |
| Migrations | Alembic | Creates and changes the schema through versioned scripts | Step 9 |
| Frontend | React, built with Vite | The form that calls `/shorten` | Step 14 |

### Supporting pieces named elsewhere in the spec

| Piece | Choice | Where the spec says so |
|---|---|---|
| Request and response models | Pydantic | §14 |
| Settings from environment variables | pydantic-settings | §4 (`config.py`) |
| Web server | uvicorn, with gunicorn when running several workers | §10 (named when explaining the rate limiter) |
| Rate limiting | slowapi "or equivalent", backed by Redis | §10 |
| CORS | FastAPI's `CORSMiddleware` | §10 |
| Logging | structlog, or the standard `logging` module with a JSON formatter | §9 |
| Counting clicks after the redirect is sent | FastAPI `BackgroundTasks` | §6 |
| Scheduling the cleanup job | cron or a systemd timer | §11 |
| Postgres and Redis on your machine | Docker Compose (`docker-compose.yml`) | §4 |

### Tests and code quality

| Where | Tests | Lint and types |
|---|---|---|
| Backend | pytest | ruff and mypy, configured in `pyproject.toml` |
| Frontend | vitest with React Testing Library | eslint and prettier |

These are the tools the testing-agent runs. `CLAUDE.md` §14 requires ruff,
mypy, eslint and prettier to report no errors.

### Why these choices (the reasons the course gives)

- **Fully async**, so one server can handle many redirects at once. §2 bans
  blocking database calls in async routes. For the same reason, the SSRF check
  needs an async DNS lookup (see 007).
- **Redis instead of in-memory counters**, because in-memory counters "are
  per-process and silently stop working the moment you run more than one
  uvicorn/gunicorn worker" (§10).
- **Alembic**, so schema changes are "tracked the same way code changes are"
  (Module 12).
- **SQLAlchemy instead of hand-built SQL strings** (§14). The click count is
  one atomic `UPDATE`, never a read followed by a write (§6).

### Beyond your machine

- **CI:** GitHub Actions running lint, type checks and tests, with `main`
  protected so the checks must pass (§13, plan step 16).
- **Hosting:** the spec doesn't choose one. The course deploys with the Vercel
  CLI plus a managed Postgres and Redis (Module 14, chapter 2; plan step 17).
  The plan names Neon as one Postgres option.

### What's installed on this machine (checked 2026-09-22)

| Tool | Needed | Installed |
|---|---|---|
| Python | 3.11+ | 3.12.3 ✓ |
| Node | 20+ | 20.19.6 ✓ (npm 10.8.2) |
| Docker | Yes | 29.1.3 ✓, and this user can reach the Docker daemon |
| Docker Compose | Yes, for `docker compose` | **Missing.** Neither the Compose plugin nor the older standalone `docker-compose` is installed. Ubuntu's `docker-compose-v2` package (2.40.3) is available. Step 7 needs it. |
| gh | Yes (the push-agent uses it) | 2.45.0 ✓ |

### Claude Code tooling for this stack (from the plan)

- **`pyright-lsp` and `typescript-lsp` plugins** (step 7) let Claude check
  types while it edits Python and the frontend.
- **`context7` plugin** (step 9) fetches current SQLAlchemy 2 async and
  Alembic documentation, instead of relying on what the model remembers.

### Not decided yet

There's no `requirements.txt` or `package.json` yet, so no versions are pinned
beyond Python 3.11+ and Node 20+. The spec also leaves a few choices open:
structlog or standard logging, slowapi "or equivalent", and cron or a systemd
timer.

## Sources

- `CLAUDE.md` §2 (the stack table), §4, §6, §9, §10, §11, §13 and §14.
- `.claude/agents/testing-agent.md` (pytest, vitest/RTL, `ruff check .`,
  `mypy app`, `npm run lint`).
- `ASSIGNMENT.md` §1 (prerequisites: Python 3.11+, Node 20+, Docker, `gh`).
- Course repo: `modules/module-12-url-shortener-project.md` line 18 (Alembic);
  `modules/module-14-cicd-and-reliability.md` chapter 2 (Vercel).
- `docs/LEARNING-PLAN.md` steps 7, 9, 16 and 17.
- Commands run on 2026-09-22: `python3 --version`, `node --version`,
  `npm --version`, `docker --version`, `docker compose version` ("unknown
  command"), `docker-compose --version` ("command not found"), the contents of
  `/usr/libexec/docker/cli-plugins` (only `docker-buildx` and `docker-trust`),
  `apt-cache policy docker-compose-v2` (not installed; candidate 2.40.3),
  `docker ps` (works), `gh --version`.

## Related

- [002. What "a slice" means](002-what-is-a-slice.md) (which slice brings in
  each piece)
- [007. What the SSRF check is](007-what-is-the-ssrf-check.md) (why the DNS
  lookup must be async)
