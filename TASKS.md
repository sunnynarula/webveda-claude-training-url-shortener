# Tasks

Each slice runs the loop in `docs/PLAN.md` §2. The contract is written at the
start of the slice and approved before RED. After `/clear`, say *"read
TASKS.md and continue"*.

**Where things are tracked.** This file holds the slice contracts and the loop
steps: it is what the testing agent, the verification agent and the security
reviewer read to learn what a slice promised. Everything else — bugs,
decisions, work to schedule — goes to
[GitHub Issues](https://github.com/sunnynarula/webveda-claude-training-url-shortener/issues),
so a pull request can close an issue and anyone reading the repo can see what
is open. Label each issue with the slice that settles it (`slice-1` …
`slice-9`), and with `security` or `decision` where they apply.

**Loop order note:** verdicts are recorded against a commit, so any commit
made after the gates or reviews invalidates them. The README update therefore
comes *before* the gates (see `docs/PLAN.md`, Amendments).

## Setup (`docs/PLAN.md` §7)

- [x] 1 Memory (publishing goal, production standard)
- [x] 2 Q&A 007 corrected
- [x] 3 `docs/PLAN.md` saved; learning plan aligned
- [x] 4 Licence: PolyForm Noncommercial 1.0.0, NOTICE, README licence section
- [x] 5 Spec decisions in `CLAUDE.md`; ADRs 0001–0011
- [x] 6 `security-reviewer` (Fable). The plan-review run and the reliability-reviewer were dropped by decision (Amendments).
- [x] 7–9 testing, verification and push agents updated
- [x] 10 `.claude/settings.json`: acceptEdits, ask before `git push`, verdict and frozen-files hooks
- [x] 11 `.review/` ignored; this file
- [x] 12a Docker Compose installed
- [ ] 12b Push `main` (developer approves)
- [ ] Branch protection on `main` after slice 1's first CI run: require `ci-ok`, 0 approvals, no bypass (developer approves)
- [ ] Turn on Dependabot security updates (repository Settings)

## Slice 1: skeleton, Compose, CI, harness (learning-plan step 7)

Branch `feat/slice-1-skeleton`.

**Contract.** Claude drafted it from `docs/PLAN.md` §8. The developer asked to
proceed without a separate approval stop, so it can be reviewed at any time.

*Interface*
- `create_app(settings: Settings | None = None) -> FastAPI` in
  `app/main.py`. `python -m app` serves it on `Settings.host`:`Settings.port`
  with JSON logging. The factory itself configures no logging, because
  `dictConfig` would replace the handlers of whatever process called it
  (issue #18); `uvicorn app.main:create_app --factory` therefore needs
  `--log-config` to get the same output.
- `app.config.Settings` (pydantic-settings). Tests always construct it as
  `Settings(_env_file=None, ...)` and never read a developer's `.env`.
- `GET /api/health/live` returns 200 `{"status": "ok"}`.
- Settings, read from the environment:
  - required: `DATABASE_URL`, `REDIS_URL`, `PUBLIC_BASE_URL`,
    `FRONTEND_ORIGIN`
  - optional: `LOG_LEVEL` (default `INFO`), `HOST` (default `127.0.0.1`),
    `PORT` (default `8000`)
  - `PUBLIC_BASE_URL` and `FRONTEND_ORIGIN` must be bare origins: a scheme
    and host, with an optional port, and no path, query or fragment. They
    must be `https`, except that `http` is allowed for the local hosts:
    `localhost`, `127.0.0.1` and `[::1]` (issue #12). The value stored is
    rebuilt from the parts that were checked, so a capitalised host is
    stored lower-cased and an invisible character is refused (issue #1).
- Errors follow RFC 9457 (`application/problem+json`): `type`, `title`,
  `status`, `detail`, `code` and `request_id`. The codes in this slice are:
  - `not_found`
  - `method_not_allowed`
  - `invalid_request`: a 422, with `errors: [{loc, msg, type}]`, and never
    echoing input
  - `internal_error`
- `X-Request-ID` is accepted if it matches `^[A-Za-z0-9._-]{1,64}$`;
  otherwise it's replaced with a uuid4 hex. It's always echoed in the
  response.
- Logs are one JSON object per line, uvicorn's own lines included. One access
  line per request records `event="request"`, `request_id`, `method`, `route`
  (the template, never the query string), `status` and `duration_ms`.
- `app.database.asyncpg_url_and_args(url) -> (URL, connect_args)` returns
  SQLAlchemy's `URL` object — not a string, so the password is masked wherever
  the value is printed (issue #17) — with the `postgresql+asyncpg` driver and
  no query string. Every query parameter is
  translated or refused, never passed through (issue #11, ADR 0012):
  - `sslmode` `require`, `verify-ca`, `verify-full` become an `SSLContext`
    that verifies the chain and the hostname (issue #15); `disable`, `allow`
    and `prefer` keep libpq's meaning; anything else, including an empty or
    repeated value, is refused (issue #3)
  - `channel_binding` is discarded: asyncpg cannot do it (ADR 0010)
  - `options` and `application_name` become `server_settings`,
    `connect_timeout` becomes `timeout`, `target_session_attrs` passes through
  - `sslrootcert` and any other parameter are refused by name
- Test-database guard: `testsupport.db_guard.ensure_safe_test_database_url(url)`
  raises `UnsafeTestDatabaseError` unless the database name ends in `_test` and
  the host is `localhost`, `127.0.0.1`, `::1` or `postgres` (the CI service).
  A `#` is refused outright, and only `sslmode`, `connect_timeout` and
  `application_name` may appear in the query (issues #6, #7).
- `HEAD` is answered wherever `GET` is, with the same headers and no body, and
  a trailing slash is a 404 rather than a redirect (issues #8, #10).

*Acceptance tests*
1. With valid settings the app boots, and `GET /api/health/live` returns 200
   with an `X-Request-ID` header.
2. A missing or malformed `PUBLIC_BASE_URL` or `FRONTEND_ORIGIN` is a
   settings error. Malformed means a path or query, a non-http(s) scheme, or
   `http` for a host that isn't local.
3. Every settings field appears in `backend/.env.example`.
4. For a Neon-shaped URL (`…?sslmode=require&channel_binding=require`), the
   returned URL has no query parameters, `connect_args` require TLS, and
   `create_async_engine` accepts the result without connecting.
5. `X-Request-ID`:
   - missing: one is generated
   - malformed (`bad id!`): replaced
   - 65 characters: replaced
   - valid: echoed
   - 20 concurrent requests: each gets its own ID back
6. Error shapes:
   - an unknown route gives 404 `not_found`
   - `POST /api/health/live` gives 405 `method_not_allowed`
   - on a test route, bad JSON and a wrongly typed body give 422
     `invalid_request`, without echoing the input
   - a test route that raises gives 500 `internal_error`

   Every one of these is `application/problem+json` and carries
   `X-Request-ID`. The 500 also carries `Access-Control-Allow-Origin` for
   `FRONTEND_ORIGIN`.
7. Logs: a uvicorn subprocess serving the app writes only JSON lines, startup
   lines included, plus one access line per request with the fields above. No
   line contains a query string.
8. The test-database guard refuses `…/urlshortener` (no `_test` suffix) and a
   remote host, and accepts `…@localhost/urlshortener_test`.

*Also in this slice*
- `backend/pyproject.toml`, `backend/uv.lock`, `backend/.python-version`
- `scripts/check.sh`, `red-check.py`, `review-diff.sh`, `ratchet.py`
- `.quality-baseline.json`
- `docker-compose.yml`: Postgres 18 and Valkey, pinned by digest, on
  127.0.0.1
- `.github/workflows/ci.yml`, `.github/dependabot.yml`
- the README sections Run locally and Environment variables

*Loop*
- [x] 0 Branch `feat/slice-1-skeleton`
- [x] 1 Contract and skeleton (`ed0f74f`, `911c94a`)
- [x] 2 RED — 54 tests, 52 failing, none erroring (`b7111d3`)
- [x] 3 GREEN — 88 tests pass, 100% branch coverage (`5bf33ee`)
- [x] 4 REFACTOR (`04ce27b`)
- [x] 5 README — every command in it was run (`1162450`)
- [x] 6 Gates and held-out tests — 206 held-out tests, 48 failures, 18 issues
- [ ] 7 Reviews (verification + security, in parallel)
- [ ] 8 Findings decided
- [ ] 9 Push and PR
- [ ] 10 CI green, merged

*Found along the way* — all filed as issues on 2026-09-23. The held-out
tests found seven defects in what this slice ships and seven questions for
later slices; two more came from reading source while implementing.

- **Fixed in this slice:** #1 #2 #3 #4 #5 #6 #7 #8 #10 #11 #12 #15 #17 #18, and #16. Each
  has a regression test named after it in
  `backend/tests/unit/test_regressions.py`, checked by reverting the fixes
  and confirming the right tests fail.
- **#17 fixed with the developer's agreement to change a frozen test.** The
  RED contract said the function returns a string; it now returns
  SQLAlchemy's `URL`, which masks the password when printed. Acceptance test
  4 changed with it, and says so in a comment.
- **Deferred to the slice that owns them:** #14 (slice 3), #9 #13
  (slice 6). Their held-out tests are parked with a note.
- **Process:** #16, on `red-check.py` reporting a legitimate RED run as a
  problem. Left until it happens a second time.

The triage behind all of this is ADR 0012: twelve of the eighteen were
one mistake in three places.

## Slices 2–9

The contract for each is written when the slice starts. The starting point
is `docs/PLAN.md` §8.

- [ ] Slice 2: schema and migration (step 9)
- [ ] Slice 3: `POST /api/v1/shorten` (step 10)
- [ ] Slice 4: `GET /{short_code}` (step 11)
- [ ] Slice 5: stats (step 12)
- [ ] Slice 6: rate limiting, CORS, health, headers (step 13)
- [ ] Slice 7: React form (step 14)
- [ ] Slice 8: expiry cleanup and takedown (step 15)
- [ ] Slice 9: deploy and operate (steps 17–18)
