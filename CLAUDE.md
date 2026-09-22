# URL Shortener — Project Guide

Source of truth for Claude Code on this repo. Read before making changes. **(assumed)** marks a decision made without explicit input — flag if wrong, or make your own call and document it here.

The approved build plan is `docs/PLAN.md`. Decisions made while planning are marked **(assumed, ADR NNNN)**, and each one is explained in `docs/adr/`.

## 1. What this is

A full-stack URL shortener: submit a long URL, get back a short code that redirects to it, with click analytics, built to survive more than one concurrent user — not a toy CRUD app.

## 2. Tech stack

| Layer | Choice |
|---|---|
| Backend | Python 3.11+, FastAPI, fully **async** (no sync DB calls in async routes) |
| Database | PostgreSQL, via SQLAlchemy async engine + `asyncpg` |
| Cache / rate-limit store | Redis protocol — cache-aside for redirects, shared counter store for rate limiting. **Valkey** locally and in CI, since Redis 7.4+ is not open source **(assumed, ADR 0009)** |
| Frontend | React (Vite) |
| Migrations | Alembic |
| Python dependencies | `uv`, with `pyproject.toml` + `uv.lock` **(assumed, ADR 0011)** |

## 3. Architecture

```
React frontend ──HTTP──▶ FastAPI backend ──▶ Redis (cache, rate limit)
                               │
                               ▼
                          PostgreSQL

Dev workflow (per slice, docs/PLAN.md §2):
  contract → RED (Testing Agent) → GREEN → REFACTOR → gates (Testing Agent)
  → Verification Agent + Security Reviewer → Push Agent
```

`.claude/agents/` defines the four agents referenced above — see §8. Code is layered routers → services → repositories, cache and click recorder, and tests replace the clock, code generator, DNS resolver and click recorder through FastAPI dependencies **(assumed, ADR 0001)**.

## 4. Repo structure

```
url-shortener/
├── CLAUDE.md
├── TASKS.md                       # per-slice contracts and progress
├── .claude/
│   ├── agents/                    # testing-agent, verification-agent, push-agent, security-reviewer
│   ├── hooks/                     # verdict recorder, frozen-files guard
│   └── settings.json              # acceptEdits, ask before git push, hooks
├── docs/                          # PLAN.md, adr/, qna/, LEARNING-PLAN.md
├── scripts/                       # check.sh, red-check.py, review-diff.sh, ratchet.py
├── backend/
│   ├── app/
│   │   ├── main.py                # app factory (create_app), middleware order
│   │   ├── config.py              # env var loading (pydantic-settings)
│   │   ├── database.py            # async engine/session, connection-URL handling
│   │   ├── cache.py               # Redis-protocol client
│   │   ├── errors.py              # RFC 9457 problem responses
│   │   ├── middleware.py          # request ID, access log, catch-all 500
│   │   ├── models.py
│   │   ├── schemas.py
│   │   ├── crud.py
│   │   ├── security.py            # URL safety / SSRF checks, reserved aliases
│   │   ├── logging_config.py      # JSON logging, uvicorn included
│   │   └── routers/
│   │       ├── health.py          # /api/health/live, /api/health
│   │       ├── shorten.py         # /api/v1/shorten
│   │       ├── redirect.py        # /{short_code}
│   │       └── stats.py           # /api/v1/urls/{short_code}
│   ├── scripts/cleanup_expired.py # cron/systemd-timer job
│   ├── tests/                     # acceptance tests (frozen after RED); tests/unit/ is the implementer's
│   ├── alembic/
│   ├── pyproject.toml             # dependencies, ruff, mypy, pytest config
│   ├── uv.lock
│   └── .env.example
├── frontend/
│   ├── src/{App.jsx, components/, pages/Home.jsx, api/client.js}
│   ├── package.json
│   └── .env.example
└── docker-compose.yml             # local Postgres 18 + Valkey for dev
```

## 5. Core features (MVP)

- Shorten a URL (optional custom alias, optional expiry)
- Redirect a short code to its original URL — cached, atomic click tracking
- View stats for a short code
- Rate-limited, abuse-resistant shorten endpoint
- Reject invalid/unsafe URLs, duplicate custom aliases, reserved words

**Out of scope for MVP (assumed):** auth/user accounts, link editing, QR codes, per-click history (see §12).

## 6. API contract (`/api/v1` prefix)

| Method | Path | Description |
|---|---|---|
| `POST` | `/api/v1/shorten` | Create (or dedupe-return) a short URL |
| `GET` | `/{short_code}` | 302 redirect — unversioned, this is the public-facing URL |
| `GET` | `/api/v1/urls/{short_code}` | Metadata + click stats |
| `GET` | `/api/health` | Liveness + dependency check |

**POST /api/v1/shorten**
```json
// request
{ "url": "https://example.com/very/long/path", "custom_alias": "promo26", "expires_in_days": 30 }
// response 201 (new) or 200 (deduped existing non-alias URL — see idempotency rule below)
{ "short_code": "promo26", "short_url": "https://sho.rt/promo26", "original_url": "...", "expires_at": "2026-10-07T00:00:00Z" }
```

Validation, in order:
1. Scheme must be `http`/`https` only — reject `javascript:`, `data:`, `file:`, etc.
2. Length ≤ 2048 chars.
3. Resolve hostname; reject loopback, link-local, and RFC1918 private ranges, and bare IP literals pointing at the metadata endpoint (`169.254.169.254`) — this is an SSRF/phishing guard, implement in `security.py`, never trust client-supplied hostnames blindly.
4. `custom_alias`, if given, must not be in the reserved-word set: `api, health, admin, static, docs, redoc, openapi, v1, www, assets, favicon.ico`.

Errors: `400` invalid/unsafe URL · `409` alias taken or reserved · `429` rate limited.

Decisions made while planning:
- Every error body is RFC 9457 `application/problem+json`, carrying a machine-readable `code` and the `request_id`. Malformed request bodies get `422`. When several errors apply, report 429 > 413 > 422 > 400 > 409. Request bodies are capped at 16 KB (`413`). **(assumed, ADR 0002)**
- The request model is strict and forbids unknown fields. Aliases match `^[A-Za-z0-9_-]{3,10}$` in full. Reserved words are matched ignoring case, and the list also covers every top-level route. **(assumed)**
- URLs are canonicalised once: printable ASCII, the host converted to punycode with UTS-46, no userinfo, and a valid port. The canonical form is what gets checked, stored, deduplicated and redirected to. **(assumed, ADR 0003)**
- Step 3 uses the full address rule in ADR 0004: after unwrapping, every resolved address must be global and not multicast, and IPv6 must be inside `2000::/3`. Lookups use a bounded async resolver. **(assumed, ADR 0004)**
- Deduplication applies only when neither an alias nor an expiry is given. It matches on `url_hash` among rows with no expiry, using `INSERT … ON CONFLICT`. `expires_in_days` must be a whole number from 1 to 365. **(assumed, ADR 0005)**

**Idempotency rule (explicit, don't leave this undefined):** if `custom_alias` is omitted and a non-expired row already exists for the exact same `original_url` with `is_custom_alias = false`, return that existing short code with `200` instead of creating a duplicate row. Requests with a `custom_alias` always attempt a fresh insert and `409` on conflict — aliases are never deduped against.

**GET /{short_code}**
- Cache-aside: check Redis (`url:{short_code}` → original URL) first. On hit, redirect immediately.
- On miss: query Postgres, write-through to Redis with a TTL **(assumed 1h)**, then redirect.
- Click tracking happens **after** the redirect response is sent, via FastAPI `BackgroundTasks` running a single atomic statement: `UPDATE urls SET click_count = click_count + 1, last_accessed_at = now() WHERE short_code = :code`. Never read-then-write the counter in application code — that's a lost-update race under concurrent hits.
- `404` unknown code · `410` expired (and evict from Redis on expiry).
- The redirect status is exactly `302` (Starlette's default is 307), sent with `Cache-Control: no-store`. It answers GET and HEAD, and HEAD isn't counted as a click. The code's format is checked before any lookup. Disabled codes return `410`. **(assumed)**
- Cache entries are `url:v1:{code}` → `{url, expires_at, disabled}`. Every hit re-checks expiry and disabled status, and TTL = min(1 h, time until expiry). **(assumed, ADR 0006)**
- Timeouts: about 200 ms for Redis with no retries, plus bounded database timeouts. If Redis fails, redirects fall back to Postgres; `/shorten` fails closed with `503`. **(assumed, ADR 0007)**

**GET /api/v1/urls/{short_code}** returns `200` for expired or disabled codes too, with `is_expired` and `is_disabled` flags. It never includes the internal `id`. **(assumed)**

**Health:** `/api/health/live` checks no dependencies and is for platform probes. `/api/health` checks Postgres and Redis (§9). **(assumed)**

## 7. Database schema

Target schema, as revised while planning **(assumed, ADR 0005)**. The migration in slice 2 is the authority:

```sql
CREATE TABLE urls (
  id               BIGSERIAL PRIMARY KEY,
  short_code       VARCHAR(10) UNIQUE NOT NULL,   -- UNIQUE already creates the index
  original_url     TEXT CHECK (octet_length(original_url) <= 2048),  -- canonical ASCII; NULL once retired
  url_hash         BYTEA,                          -- SHA-256 of original_url, computed in the app
  is_custom_alias  BOOLEAN NOT NULL DEFAULT FALSE,
  created_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
  expires_at       TIMESTAMPTZ,
  disabled_at      TIMESTAMPTZ,                    -- abuse takedown
  retired_at       TIMESTAMPTZ,                    -- expired and cleaned up; the code is kept
  click_count      BIGINT NOT NULL DEFAULT 0,
  last_accessed_at TIMESTAMPTZ
);
-- dedupe: one row per URL among non-alias rows with no expiry; inserts use ON CONFLICT
CREATE UNIQUE INDEX uq_urls_url_hash_dedupe ON urls (url_hash)
  WHERE NOT is_custom_alias AND expires_at IS NULL;
-- cleanup scans
CREATE INDEX ix_urls_expires_at ON urls (expires_at) WHERE expires_at IS NOT NULL;
```

Short codes: 7-char base62 via `secrets`, insert-and-retry on unique-constraint collision. **Trade-off, stated explicitly:** this makes codes opaque/non-enumerable, the right call for a public shortener — the cost is an occasional wasted round-trip on collision (rare at 62^7 keyspace) versus a sequential ID's guaranteed-unique but enumerable codes.

**Codes are never reused.** Rows are *retired* (URL dropped, code kept) or *disabled*, never deleted. Otherwise a stranger could claim a freed code as an alias and take over links people have already shared. **(assumed, ADR 0005)**

## 8. Agent workflow (`.claude/agents/`)

| Agent | File | Job |
|---|---|---|
| Testing Agent | `testing-agent.md` | Writes/runs pytest + vitest, runs lint/type-check |
| Verification Agent | `verification-agent.md` | Read-only review against this spec + a reliability/security checklist |
| Push Agent | `push-agent.md` | Pushes a reviewed branch and opens a PR |
| Security Reviewer | `security-reviewer.md` | Read-only security review of each slice, on Fable (`model: fable`, tools `Read, Grep, Glob`) **(assumed)** |

Run them in that order for every change: implement → Testing Agent → Verification Agent → Push Agent. Don't invoke Push Agent unless the other two have both passed — that discipline is on you and Claude Code here, since this starter doesn't wire up automated enforcement (see §13 for what that would take).

**Enforcement added while planning (assumed):**
- Each slice follows the loop in `docs/PLAN.md` §2.
- A `SubagentStop` hook records the Testing Agent's, Verification Agent's and Security Reviewer's final verdicts against the current commit in `.review/verdicts/`. The Push Agent only pushes when all three say PASS for `HEAD`.
- A `PreToolUse` hook asks before anyone except the Testing Agent edits the acceptance tests, the gate scripts, CI, or the hooks themselves.
- Claude Code asks before every `git push`.

## 9. Observability

- Structured (JSON) logging via `structlog` or stdlib `logging` with a JSON formatter.
- Request-ID middleware: read `X-Request-ID` header or generate a `uuid4`, attach to every log line for that request. An incoming ID is accepted only if it matches `^[A-Za-z0-9._-]{1,64}$`, and is replaced otherwise. It's echoed in the response. **(assumed)**
- Uvicorn's own loggers log JSON too. One access-log line per request records the route template, status and `duration_ms`, and never `original_url`. **(assumed)**
- `/api/health`: returns `200` only if `SELECT 1` succeeds against Postgres **and** `PING` succeeds against Redis; `503` otherwise. A health check that doesn't check its dependencies isn't a health check.

## 10. Security & config

- CORS: `CORSMiddleware` with `allow_origins=[FRONTEND_ORIGIN]` from env — never `*`.
- Rate limiting: `slowapi` (or equivalent) backed by `REDIS_URL`, not in-memory — in-memory counters are per-process and silently stop working the moment you run more than one uvicorn/gunicorn worker.
  - The "equivalent" is our own async limiter, because slowapi calls Redis synchronously, which would break §2.
  - It runs as ASGI middleware, so malformed requests count too.
  - INCR and EXPIRE run atomically.
  - IPv6 clients are keyed per /64.
  - Where the client IP comes from is an explicit setting.

  **(assumed, ADR 0008)**
- Secrets: `.env` for local dev only (gitignored, never committed — only `.env.example` is).
- Reserved-alias denylist enforced at creation time (§6).

## 11. Ops

- `backend/scripts/cleanup_expired.py`: *retires* rows whose `expires_at` has passed. It drops the URL, keeps the code, sets `retired_at`, and evicts the entry from the cache. Run daily via cron or a systemd timer, or through a protected `/api/internal/cleanup` endpoint on hosts without cron. **(assumed, ADR 0005:** replaces the original hard delete, because freed codes could be hijacked.**)**
- A **disable** command handles abuse takedowns. It sets `disabled_at` and evicts the cache entry, so the next request returns `410`. **(assumed)**

## 12. Known limitations (stated explicitly, not silent)

- **Click analytics are aggregate-only** (`click_count`, `last_accessed_at`). No per-click event log (timestamp/referrer/user-agent) in v1 — deliberately deferred, not forgotten.
- **Dedupe lookup** (`idx_urls_original_url_dedupe`) is a plain B-tree on `TEXT`. Fine at this scale; at real scale, hash the URL into a separate indexed column instead of indexing the raw text. *Resolved while planning: the dedupe index is on `url_hash` (ADR 0005).*
- **Stats are public** for any code, since there's no auth. Deduplicated links share one set of stats, and link-preview bots inflate `click_count`.
- **The SSRF check runs when a link is created.** It can't stop a domain whose DNS changes later, or a target that redirects onward (`docs/qna/007`).
- **Database connections are encrypted but not authenticated.** The asyncpg driver can't do channel binding, and with `sslmode=require` it doesn't check the server's certificate, so a network attacker who can intercept the connection could pose as the database. Found while implementing slice 1; a candidate fix and the evidence are in ADR 0010. **Must be settled before the first real deployment (slice 9).**
- **No multi-region / read replica story.** Single Postgres + single Redis instance — fine for this assignment, would need connection pooling and read replicas for real production traffic.

## 13. Stretch goals

If the core app is working and passing its own tests, these are the next things a production system would need — good extensions to attempt. *Pulled forward while planning: CI and branch protection arrive with slice 1, and the verdict and frozen-files hooks exist before slice 1. The three agent-specific hooks below remain step 13's job.*
- A GitHub Actions workflow that runs lint, type-check, and tests on every push/PR, with branch protection on `main` requiring it to pass. This turns §8's agent workflow from "discipline" into a gate that can't be skipped.
- `PreToolUse` hooks on the agents in `.claude/agents/` (see Claude Code's subagent docs) so Testing Agent can only edit test files, Verification Agent can't run mutating Bash commands, and Push Agent reruns tests before it's allowed to `git push`.

## 14. Conventions

- Type hints everywhere; Pydantic for all request/response models; no raw SQL string building (SQLAlchemy Core/ORM only).
- `ruff` + `mypy` clean, `eslint`/`prettier` clean.
- Commits: conventional commits (`feat:`, `fix:`, `test:`, `chore:`).
- Make one concern per commit, with the lesson in the body. Merge PRs with a merge commit, never squash, so the history keeps the test-first sequence. **(assumed)**
- Never commit `.env` files — only `.env.example`.
