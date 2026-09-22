# Plan: build the URL shortener to production standard, in test-first, security-reviewed slices

## In plain terms (start here)

This is the plan for building the app in the course's 8 slices, plus a 9th for deploying and running it. Three expert reviews shaped it (DevOps, full-stack, architect/TDD), and I checked each fact they relied on before using it.

**How every slice is built:**
- You approve a contract, meaning what the slice must do.
- An agent writes failing tests from that contract. Claude writes code until they pass, then tidies it up with the tests still passing. Claude can't change or weaken those tests: a hook blocks it.
- A Fable security reviewer and a spec reviewer then check the slice. Their verdicts are recorded automatically against the exact commit they reviewed.
- One check script, run locally and in CI, must pass before GitHub allows a merge.

**Five production fixes the reviews made:**
1. **Expired or disabled codes are retired, never freed.** Otherwise a stranger could re-register one and take over every link people have already shared.
2. **Abusive links can be disabled.** Every public shortener gets used for phishing, and without this one bad link can get the whole domain blocklisted.
3. **The URL that passes the safety check is exactly the one stored and redirected to.**
4. **Short timeouts everywhere.** Library defaults would let a stalled Redis freeze each redirect for seconds or more.
5. **A new slice 9 covers deploying and running the app:** migrations, backups, a takedown runbook and monitoring.

**Commercial use:**
- Nothing in the stack blocks it. Every library is MIT, BSD, Apache or the PostgreSQL licence.
- Redis becomes Valkey, because Redis is no longer open-source.
- Your own code moves to PolyForm Noncommercial (section 6). Approving this plan confirms that.

**Decided later, at deploy time (step 17):** whether your hosted copy runs on free tiers as a demo, or on a paid setup at roughly $40–60 a month.

Everything below is build detail.

---

## Context

This is step 3 of `docs/LEARNING-PLAN.md`: plan the build and save the approved plan as `docs/PLAN.md`. The user's requirements:
- TDD, so no slice regresses.
- A security review of every slice by a Fable subagent.
- Review standards that must be met.
- A smoother process.
- Production standard, and commercially viable.

The user's publishing goal: the repo stays public. People are invited to use it, companies pay for commercial use, and the author gets credit.

**Inputs:**
- Q&A 001–009.
- An initial critique.
- Three expert reviews (DevOps, full-stack, architect/TDD; together about 580k tokens).
- A licensing audit I did myself.

**Everything factual in this plan was checked against source code, docs or local runs**, except where it's marked JUDGEMENT.

**Conceptual neighbours:** `CLAUDE.md` §8 already has testing → verification → push, and §13 names CI and hooks as the way to make it a gate. This plan extends §8 and brings §13 forward. It adds no parallel mechanism.

## 1. Architecture decisions (each gets a short ADR in `docs/adr/`)

- **Layers:** routers → `LinkService` → `LinkRepository`, `LinkCache` and `ClickRecorder`.
  - Each part the tests need to replace is a FastAPI dependency they can override: `Clock`, `CodeGenerator`, `Resolver` (DNS) and `ClickRecorder`.
  - Business rules use the injected clock, passed into queries as a parameter, never SQL `now()`.
- **One error shape:** RFC 9457 problem+json plus `code` and `request_id`.
  - Handlers cover 404, 405, 413, 422 (which must not echo the user's input back), 429, 500 and 503.
  - An innermost catch-all middleware makes sure 500s still carry the CORS and `X-Request-ID` headers.
  - When several errors apply, the response reports them in this order: 429 > 413 > 422 > 400 > 409.
- **Canonical URLs:**
  - Parse the URL once, using printable-ASCII, RFC 3986 rules.
  - Reject userinfo, `\` characters, bad ports, and hosts that fail IDNA (the internationalised domain name rules).
  - Convert the host to punycode with the `idna` package (UTS-46, the standard browsers use), then check the length.
  - Store, dedupe and redirect those exact bytes.
  - Plain `getaddrinfo` uses the older IDNA 2003 rules, and `faß.de` shows the two resolve different hosts.
- **Data model** (changes spec §7):
  - `url_hash BYTEA` (SHA-256, computed in the app), with a `UNIQUE (url_hash) WHERE NOT is_custom_alias AND expires_at IS NULL` partial index. Inserts use `ON CONFLICT DO NOTHING RETURNING`. This removes the dedupe race and the raw-text index; a 2,048-character non-ASCII URL could otherwise exceed Postgres's B-tree row limit.
  - New `disabled_at` and `retired_at` columns. Retired rows keep their `short_code` and drop the URL, so **no code is ever reused.**
  - Drop the redundant `idx_urls_short_code`.
  - A partial index on `expires_at`, for cleanup.
  - Constraints follow a naming convention, so violations map to error codes.
- **Cache:**
  - Key `url:v1:{code}` holds `{url, expires_at, disabled}`.
  - Every cache hit checks expiry and disabled status.
  - TTL = min(1 h, time until expiry), set with `SET … PXAT`, and nothing is cached if that's ≤ 0.
  - The store runs with `maxmemory` and `volatile-lru`, and persistence off. Cached data is disposable.
- **Timeouts:**
  - Redis: about 200 ms, no retries, and a bounded pool. The redis-py 8.1.0 defaults are 5 s timeouts plus 10 retries; I checked `_defaults.py`.
  - asyncpg `command_timeout`, SQLAlchemy `pool_timeout` and `pool_pre_ping`, and `pool_recycle` under 5 minutes.
  - `statement_timeout` is set on the app's database role, not per session.
  - Database lookups use short `async with` session blocks. A session held open by a `yield` dependency would still be held while the background click task runs.
- **DNS:** use `aiodns` behind `Resolver`, with a concurrency cap and a 2-second timeout that returns 400. `loop.getaddrinfo` would borrow the default thread pool, which has 8 threads on this laptop, and a timeout doesn't free the thread.
- **Deploy target: Vercel.** The DevOps review checked Vercel's runtime, which only finishes a request once the app has returned, so `BackgroundTasks` complete. `ClickRecorder` stays swappable anyway, and slice 9 checks this on the live deployment.
  - The frontend and API share one origin in production. Development uses Vite's proxy.
  - CORS stays strict for development and for other deployments.

## 2. The per-slice loop

Each slice runs in a fresh session (`/rename slice-N`) in acceptEdits mode, and its contract lives in `TASKS.md`.

| # | Step | Who | Commit (on `feat/slice-N-…`) |
|---|---|---|---|
| 0 | `git checkout main && git pull && git checkout -b feat/slice-N-<name>` | you or Claude | — |
| 1 | **Contract and skeleton:** write the interface and acceptance list in `TASKS.md` (**you approve**), and add the empty modules, extension points and stubs | main Claude, then you | `docs(slice-N): contract`, `chore(slice-N): skeleton` |
| 2 | **RED:** HTTP contract tests, repository tests and property tests, asserting on the error `code`. `scripts/red-check.py` reads pytest's JUnit report and confirms each new test *fails* rather than *errors*. | testing-agent | `test(slice-N): …` (these files are now **frozen**) |
| 3 | **GREEN:** implement. Claude may add its own tests under `tests/unit/`. `/goal` is optional. | main Claude (you write the SSRF check) | `feat(slice-N): …` |
| 4 | **REFACTOR:** tidy up, with tests green before and after | main Claude | `refactor(slice-N): …` |
| 5 | **Gates and held-out tests:** `scripts/check.sh`. The testing-agent then writes extra tests from the contract that the implementer never saw. | testing-agent | `test(slice-N): held-out …` |
| 6 | **README:** fill in the section the skeleton comment names, and add or update ADRs | main Claude | `docs(slice-N): …` |
| 7 | **Reviews, in parallel:** `scripts/review-diff.sh` writes `.review/slice-N.diff` and records HEAD's SHA. The verification-agent checks the spec, the README, and that frozen files are untouched. The security-reviewer runs on Fable. | read-only agents | — |
| 8 | **You decide on the findings.** Each accepted fix starts as a failing test. At most 2 rounds; after that, anything unresolved needs a waiver file (the finding, your reasoning, a tracking issue). | you | `test:` then `fix:` |
| 9 | **Push and PR:** the push-agent requires testing, verification and security verdicts recorded **for the current HEAD** (section 3), and Claude Code asks you before the push | push-agent | — |
| 10 | **CI `ci-ok` goes green, then you merge** with a merge commit | you | — |

**Anti-gaming:**
- A `PreToolUse` hook stops main Claude from editing the frozen test files, `conftest.py`, `scripts/check.sh` or `.github/workflows/*`. The hook input identifies which agent is acting (`agent_type`), so the testing-agent is exempt.
- `check.sh` compares the counts of suppression markers against `.quality-baseline.json` and fails if any count goes up. The markers are `noqa`, `type: ignore`, `pragma: no cover`, skip/xfail, coverage `omit` and ruff per-file-ignores.
- pytest runs with `--strict-markers` and `xfail_strict`.

**Branches:** once `main` is protected, every commit goes through a slice branch or a small docs PR.

## 3. The security reviewer (Fable) and recorded verdicts

`.claude/agents/security-reviewer.md`:

```yaml
name: security-reviewer
description: Read-only security review of one slice's diff (and of docs/PLAN.md at step 5). Use after testing passes, in parallel with verification-agent, before push-agent.
tools: Read, Grep, Glob     # no Bash/Edit/Write: read-only by construction
model: fable
effort: high               # confirm Fable accepts it at step 5
maxTurns: 30
omitClaudeMd: true         # skips the 41k-token global CLAUDE.md; it reads the project files itself
```

**What it's told to do:**
- Read `CLAUDE.md`, the ADRs, the slice's `TASKS.md` entry, `docs/qna/007` and the diff file. Follow callers with Grep.
- **Check against:**
  - the OWASP API Security Top 10 (2023): API4, API7, API8, API9 and API1/3
  - the spec
  - the architecture decisions in section 1 (timeouts, canonical URLs, error shape)
- **Report** each finding with its severity, `file:line`, a concrete attacking input, and a suggested fix.
- **Verdict:** FAIL on any CRITICAL or HIGH finding. MEDIUM findings go to you; LOW findings are logged only.

**Recorded verdicts (hooks):**
- A `SubagentStop` hook runs when any subagent finishes. The docs confirm its input includes `agent_type` and `last_assistant_message`.
- When the finishing agent is `testing-agent`, `verification-agent` or `security-reviewer`, the hook writes the agent's final message to `.review/verdicts/<agent_type>@<HEAD-sha>.txt`.
- The push-agent checks for three PASS files matching HEAD, or a waiver file. The model can't fake these files, so the push-agent no longer has to take anyone's word.

**Parity with the verification-agent:** both give a verdict for one slice and both are read-only. The security-reviewer is stricter about tools. The verification-agent keeps the course's security checklist as a cheap second net.

**Cost:**
- *Measured:* each of this plan's max-effort reviews used 156k–254k tokens.
- *Estimated:* a slice review on Fable is on the same order, so about 1.5–5M tokens across the build. It depends on how many re-reviews happen.
- *Measured:* `omitClaudeMd` saves about 41k tokens on every agent turn.

**Before deploy:** run the `claude-security` plugin's *Scan codebase*, a Fable-backed agent team.

## 4. Standards: what must pass

**`scripts/check.sh`** is used by the testing-agent, CI and the step 13 pre-push hook. It runs:
- `uv sync --locked`
- `ruff check` with rule sets E, F, I, B, **S**, **ASYNC**, **DTZ**, UP and **TID251**
  - TID251 bans `socket.getaddrinfo`, `socket.gethostbyname`, the synchronous `redis.Redis` and `sqlalchemy.create_engine`, which catches the blocking calls the ASYNC rules miss.
  - S101 (plain `assert`) is ignored in tests.
- `ruff format --check`
- `mypy --strict app`
- `alembic upgrade head`
- `pytest --strict-markers` with branch coverage of at least 90%, excluding `alembic/`, `TYPE_CHECKING` blocks and `__main__`
- the suppression ratchet (section 2)
- Schemathesis in-process against the app's OpenAPI schema (`from_asgi`), required from slice 3, with the DNS resolver stubbed and test-mode rate limits
- a licence gate: `pip-licenses` allowing only permissive licences

**Frontend (slice 7 on):**
- `npm ci`, `eslint`, `prettier --check` and `vitest --coverage`
- a snapshot of the OpenAPI schema, with TypeScript types generated from it by `openapi-typescript`
- `license-checker-rseidelsohn --onlyAllow`
- a Playwright smoke test and axe accessibility checks

**CI (`ci.yml`, slice 1):**
- Triggers: `pull_request`, plus pushes to `main`.
- Actions pinned to commit SHAs, with GitHub's pinning policy turned on.
- `persist-credentials: false` and `timeout-minutes: 15`.
- Service containers `postgres:18-alpine` and `valkey/valkey:8-alpine`, with health checks, pinned to the same digests as Compose.
- A single `ci-ok` job is the one required check.
- Branch protection is turned on after the first run. It requires `ci-ok`, needs 0 approvals (you can't approve your own PR) and allows no bypass.

**Nightly and non-blocking** (a newly published CVE with no fix mustn't block every merge):
- `pip-audit` and `npm audit`
- `mutmut` on `security.py` and the services
- a CycloneDX software bill of materials (SBOM) for each release

Dependabot security updates get turned on, with a `dependabot.yml` cooldown.

**Judgement checks:** the verification-agent and the security-reviewer on every slice. The built-in `/code-review` on slices 3, 4 and 6. You on every PR.

**Already on:** GitHub secret scanning and push protection. The repo stays public, so they stay free and gitleaks isn't needed.

## 5. Test harness (slice 1)

- **Guarding real data:**
  - Tests read `TEST_DATABASE_URL`, never `.env`.
  - The fixtures refuse to run unless the database name ends in `_test` and the host is local or the CI service container.
  - TRUNCATE after each test; FLUSHDB on logical database 15.
- **Async setup:**
  - One session-wide event loop.
  - `LifespanManager` around httpx's `ASGITransport`.
  - The schema always comes from migrations.
- **Replaceable dependencies:**
  - `Clock`, `CodeGenerator` and `Resolver` are overridden in tests.
  - The resolver stub still sends numeric hosts to the real parser, so the decimal, hex and octal address tests exercise real code.
- **Things an HTTP test can't see:**
  - `ASGITransport` waits for background tasks too, so "the click is recorded after the response" is proved with a gated fake `ClickRecorder`.
  - "A cache hit doesn't touch the database" is proved with a repository spy.
- **Failure fixtures:**
  - a stopped Redis
  - a *silent* Redis (a socket that accepts connections but never replies)
  - a database pool of size 1
- **Logging:**
  - A smoke test starts uvicorn as a separate process, which proves its logs are JSON too.
  - Access logs record the route template, status, `duration_ms` and cache/fallback flags. They never record `original_url`.

## 6. Commercial use and licensing (audited 2026-09-22)

| Item | Licence or terms | Effect | Action |
|---|---|---|---|
| Runtime libraries: FastAPI, Starlette, Pydantic, pydantic-settings, SQLAlchemy, asyncpg, Alembic, uvicorn, structlog, redis-py, idna, aiodns, React, Vite | MIT, BSD-3 or Apache-2.0 | None | Keep their notices. The CI licence gate blocks copyleft newcomers. |
| PostgreSQL | PostgreSQL Licence (permissive) | None | Keep |
| **Redis 7.4 and later** | RSALv2 or SSPLv1, with AGPLv3 added from 8.0. Only 7.2 and earlier are BSD, and `redis:7` means 7.4. | Not open source. It would be a burden on your commercial licensees. | **Use Valkey** (BSD-3, same protocol, same `redis.asyncio` client) locally and in CI. The production store is whatever managed service you pick. |
| Development tools (ruff, mypy, pytest, httpx, pip-audit, Schemathesis, mutmut, vitest, Playwright, eslint, prettier, and more) | Permissive. Hypothesis and axe-core are MPL-2.0. | None: they don't ship in the product | Keep |
| Skills copied into the repo | superpowers, mattpocock and supabase are MIT; neon is Apache-2.0; vercel-labs is MIT according to its README; **Trail of Bits is CC-BY-SA-4.0** | Copied files keep their own licences | Install Trail of Bits as a **plugin marketplace**, never copied into the repo. Keep the MIT and Apache notices. |
| Anthropic terms | "we assign to you all of our right, title, and interest—if any—in Outputs". Building competing AI services is banned. | None | — |
| Course files | MIT (TrainWithShubham) | Commercial use is allowed as long as the notice stays | Already covered by `NOTICE` and `LICENSE-COURSE` |
| **Your code** | PolyForm Strict: other people can't modify or share it | Conflicts with "invite people to use it" | **Switch to PolyForm Noncommercial 1.0.0.** Non-commercial users may use, change and share it; commercial users need a paid licence from you; your `Required Notice:` line travels with every copy. (Not legal advice: have a lawyer draft the commercial licence you'll sell.) |
| Outside contributions | — | You can't sell a commercial licence for code you don't own | Add a CLA before the first outside PR (CLA Assistant) |
| Credit when the app appears on social media | Licence notices travel with the code, not with screenshots of a running site | — | A "Built by …" footer (tested in slice 7), plus a README section on how to credit you and how to buy a commercial licence |
| Hosting (step 17) | Vercel Hobby is "non-commercial, personal use only". Neon's free tier suspends compute after 100 CU-hours a month. Upstash's free tier caps commands. Google Safe Browsing is non-commercial; for commercial use it's Web Risk. | A free demo is fine. A paid instance is not. | **Decide at step 17:** a demo on free tiers, or production at about $40–60 a month (Vercel Pro, Neon Launch, Upstash pay-as-you-go). The vendors' figures are as of review and get re-checked then. |

## 7. Harness setup before slice 1 (each item is its own commit unless marked otherwise)

1. **Save memory (not a commit):**
   - the publishing goal: public repo, credit, paid commercial licences
   - "build to production standard". Plan mode blocks this write, so it happens first after approval.
2. **Correct Q&A 007.** The full rule, verified on Python 3.12.3:
   - IPv4 addresses must be global and not multicast.
   - IPv6 addresses are unwrapped first: IPv4-mapped, NAT64 (`64:ff9b::/96` and `64:ff9b:1::/48`), 6to4 and Teredo.
   - Any other IPv6 address must be inside `2000::/3`, global and not multicast.
   - `is_global` alone passes `224.0.0.1`, `64:ff9b::a9fe:a9fe`, `::a9fe:a9fe`, `::ffff:0:a9fe:a9fe` and `fec0::1`.
   - Also cover the canonical host, `aiodns`, and pinning the Python patch version.
3. **Save this plan** as `docs/PLAN.md`, and apply section 11 to `docs/LEARNING-PLAN.md`.
4. **Licence:**
   - Put PolyForm Noncommercial 1.0.0 in `LICENSE`, with a `Required Notice:` line.
   - Update `NOTICE`.
   - Add a CLA note to the README.
5. **Record spec decisions** (section 9) as "(assumed)" lines in `CLAUDE.md`, plus §8's new order. Create `docs/adr/0001`–`000N`.
6. **Step 5 of the learning plan:** create `security-reviewer.md` and `reliability-reviewer.md`, and have both review this plan. Record the real Fable token use.
7. **`testing-agent.md`:**
   - RED, held-out and gates modes.
   - Never weaken a test.
   - Add `omitClaudeMd`, and have it read `CLAUDE.md`, `TASKS.md` and the ADRs itself.
8. **`verification-agent.md`:**
   - Scope reviews to one slice.
   - Add checks for the README, frozen files and ADRs.
   - Add a 5-line code-quality list.
   - Add `omitClaudeMd`.
9. **`push-agent.md`:**
   - Require verdict files for HEAD, or a waiver file.
   - Refuse to run on `main`.
   - Commit only leftovers; run `gh pr view` before `gh pr create`.
   - Add `omitClaudeMd`.
10. **`.claude/settings.json`:**
    - `defaultMode: acceptEdits`
    - `permissions.ask: ["Bash(git push *)"]`
    - the `SubagentStop` verdict hook
    - the `PreToolUse` frozen-files hook
11. **`.gitignore`:** add `.review/`. **`TASKS.md`:** placeholders for each slice's contract.
12. **You:** install Compose (`sudo apt install docker-compose-v2`), then approve pushing `main`. That's the last direct push; after it, `main` gets protected.

`/ship-slice` (learning-plan step 9) scripts steps 0–10 of the loop. You run slice 1 by hand first.

## 8. The slices (acceptance tests are written first; E = error `code` asserted)

**Slice 1: skeleton, Compose, CI, harness (step 7)**
- **Tests:**
  - The app boots.
  - Settings reject a missing or malformed `PUBLIC_BASE_URL` or `FRONTEND_ORIGIN`.
  - Every setting appears in `.env.example`.
  - A Neon-shaped URL containing `sslmode` and `channel_binding` parses and connects with explicit TLS. asyncpg rejects those two query parameters; the DevOps review found this in asyncpg's source.
  - `X-Request-ID` handling: a missing, malformed or oversized ID is replaced; the ID is echoed; concurrent requests keep their own.
  - An unknown route, a 405, bad JSON, a 422 and a forced 500 all return the same error shape (E), with `X-Request-ID`.
  - `/api/health/live` returns 200.
  - The JSON-log smoke test.
  - The test-database guard refuses a non-`_test` database.
- **Also:** `pyproject.toml`, `uv.lock`, `.python-version` (3.12), `check.sh`, `red-check.py`, `review-diff.sh`, the quality baseline, and `docker-compose.yml`:
  - Alpine images, pinned by digest
  - ports bound to `127.0.0.1`
  - the Postgres 18 volume at `/var/lib/postgresql`
  - Valkey with `maxmemory` and `volatile-lru`
- **Also:** `ci.yml`, then branch protection, and ADRs for the layers, error shape, clock and deploy target.
- **Security focus:** secrets live only in env; nothing listens beyond localhost.
- **README:** Run locally, Environment variables.

**Slice 2: schema and migration (step 9)**
- **Tests:**
  - upgrade → downgrade → upgrade round-trips, and `alembic check` is clean.
  - `url_hash` has its partial unique index.
  - The database rejects a URL longer than its CHECK allows (and `alembic check` can't see CHECKs).
  - A duplicate code is rejected, including by a retired row.
  - Constraint names follow the naming convention.
- **Also:**
  - Migrations are expand/contract and set a `lock_timeout`.
  - The app's database role can only read and write rows, with `statement_timeout` set.
  - A separate owner role runs the migrations.
- **Security focus:** least privilege.
- **README:** Migrations.

**Slice 3: `POST /api/v1/shorten` (step 10)**
- **Tests:**
  - 201 for a new link.
  - 200 when deduplicated. This applies only when neither an alias nor an expiry is given, and matches only rows with no expiry.
  - Two concurrent identical requests give one 201, one 200 and one row.
  - 201 for an alias.
  - 409 E for an alias that's taken (exact match), or reserved (ignoring letter case). Every top-level route is on the reserved list.
  - 422 E for an unknown field, a wrong type, an 11-character alias, or `"abc\n"`.
  - 413 E for a body over 16 KB.
  - 400 E for:
    - a bad scheme, a URL that's too long, control characters or `\`
    - userinfo, or a bad port
    - an IDNA failure
    - the full SSRF list: loopback, private, link-local, multicast, the metadata address in decimal, hex and octal forms, `127.1`, `0`, `[::1]`, IPv4-mapped, NAT64, 6to4, Teredo, IPv4-compatible, `fec0::1`, a hostname resolving to a mix of public and private addresses, and a DNS timeout
  - The DNS stub is asked for `xn--fa-hia.de` when given `faß.de`.
  - The response's `original_url` equals the eventual `Location`.
  - Collision retry.
  - A retired code can't be claimed as an alias.
- **Also:**
  - Hypothesis property tests for the validator and the code generator.
  - Schemathesis becomes required.
  - You write the SSRF check yourself.
  - Explore: `/code-review`.
- **Security focus:** API7 (SSRF) and API4 (resource consumption).
- **README:** Architecture, Known limitations.

**Slice 4: `GET /{short_code}` (step 11)**
- **Tests:**
  - Exactly **302** (Starlette defaults to 307), with `Cache-Control: no-store`.
  - HEAD is accepted and not counted as a click.
  - A malformed code gets 404 E before Redis or the database is touched (`GET /%00` never reaches Postgres).
  - A cache miss reads the database, then fills the cache.
  - A cache hit makes no lookup query (checked with the repository spy).
  - `PTTL` is no longer than the time to expiry.
  - Expired or disabled codes get 410 E with `no-store`, and are evicted.
  - N concurrent hits count N, even with a pool of size 1: 20 cache-miss redirects finish in under 2 s.
  - The response goes out before the click is recorded (gated fake).
  - With Redis *stopped*, and with Redis *silent*, the redirect still gives 302 within the latency bound.
  - With Postgres down, a cache hit still gives 302, and the failed click is logged.
  - `/api/*` and `/docs` aren't swallowed by the catch-all route.
- **Also:**
  - A short cache for unknown codes, so probing random codes doesn't hit the database every time.
  - Lenient rate limits on reads.
  - Choose a `Referrer-Policy`.
  - Explore: `/code-review`.
- **README:** Architecture, Known limitations (link-preview bots inflate `click_count`).

**Slice 5: stats (step 12)**
- **Tests:**
  - 200 with the defined fields, including `is_expired` and `is_disabled`.
  - Unknown or malformed code gets 404 E.
  - Reading stats doesn't count as a click.
  - No internal `id` in the response.
  - A lenient rate limit.
- **README:** Known limitations: stats are public, and deduplicated links share their stats.

**Slice 6: rate limiting, CORS, health, headers (step 13)**
- **Tests:**
  - The limiter is ASGI middleware, so malformed requests count toward the limit (checked on the 11th). The 429 E carries `Retry-After`.
  - The two-instance shared-limit test.
  - Counter keys always have a TTL: INCR and EXPIRE run atomically (Lua or MULTI).
  - IPv6 clients are limited per /64.
  - The client IP source is an explicit setting.
  - CORS headers appear on errors and preflights; preflights aren't rate-limited; `Retry-After` and `X-Request-ID` are exposed; a foreign origin gets nothing.
  - `/api/health` returns 503 for each dependency, within a timeout, with no details, and caches its result for a few seconds.
  - `nosniff`, `no-store` on JSON, `frame-ancestors 'none'`.
  - `/docs` is off in production.
- **Also:**
  - The hooks stretch goal.
  - The pre-push `check.sh` hook.
  - Explore: `/code-review`, and Schemathesis with the limiter on.
- **Security focus:** API4, API8.
- **README:** Environment variables.

**Slice 7: React form (step 14)**
- **Tests (vitest + RTL):**
  - 400, 409, 413, 422, 429 and network errors are each shown to the user.
  - No double submit.
  - Empty optional fields are left out of the request.
  - The destination's host is shown in punycode, so lookalike domains are visible.
  - Copy works, with a fallback when clipboard access is refused.
  - The build fails without `VITE_API_BASE_URL`.
  - A **"Built by …" credit** is in the footer.
- **Playwright smoke test:** against Compose and `vite preview`, create a link, copy it, and check the 302.
- **Also:** axe accessibility checks, the frontend CI job, and `typescript-lsp`.
- **Security focus:** no `dangerouslySetInnerHTML`; only http(s) links are rendered; a CSP.
- **README:** Run locally (frontend).

**Slice 8: expiry cleanup and takedown (step 15)**
- **Tests:**
  - Cleanup *retires* expired rows: the URL is removed, `retired_at` is set, and the code is kept. Rows with no expiry or a future expiry are untouched. The cache is evicted. It works in batches with `FOR UPDATE SKIP LOCKED` within a time budget. A second run changes nothing. A database error exits non-zero.
  - `/api/internal/cleanup` requires `Authorization: Bearer $CRON_SECRET`; without it, 401.
  - The **disable** command sets `disabled_at` and evicts the cache, so a code whose cache is warm gets 410 on the very next request.
  - Logs show counts, not URLs.
- **README:** Run locally (jobs), an abuse contact, and Known limitations.

**Slice 9: deploy and operate (steps 17–18, added by the DevOps review)**
- **Hosting:** Vercel, with the frontend and API on one origin. Preview deploys use a Neon database branch, never production credentials.
- **Deploying:** a single-concurrency CI job runs `alembic upgrade` over the *direct* database URL, then `vercel deploy --prod`. The app uses the *pooled* URL.
- **Rollback:** roll forward only. Instant Rollback reverts code, not the schema.
- **Backups:** a nightly `pg_dump -Fc` by a read-only role to storage outside Neon, kept 30 days, with a monthly restore drill. Recovery targets (RPO/RTO) go in the README.
- **Monitoring:** every scheduled job pings a missed-run monitor. GitHub disables scheduled workflows in public repos after 60 days without activity.
- **Location:** databases in us-east-1, because Vercel runs functions in `iad1` by default.
- **Post-deploy acceptance tests:**
  - A browser-style `GET /{code}` gets a 302, not the frontend page.
  - Stats count that click, which proves `BackgroundTasks` finished.
  - The client IP is detected correctly.
  - HSTS and CSP are present.
  - `/docs` is off.
- **Step 18's SLO:** built from forwarded logs (Vercel Pro) plus an external probe, with alerts on how fast the error budget is being used. Also the takedown runbook.
- **Then:** the `claude-security` scan, with no open CRITICAL or HIGH findings.

## 9. Spec decisions (recorded as "(assumed)" in `CLAUDE.md`)

| Decision | Choice |
|---|---|
| Alias format | `^[A-Za-z0-9_-]{3,10}$`, checked with `fullmatch`. Uniqueness is case-sensitive; the reserved-word check ignores case. |
| Request model | Pydantic `strict=True, extra="forbid"`. Pydantic's `HttpUrl` isn't used. |
| URL | Canonical ASCII (section 1). What gets stored, deduplicated and redirected is the canonical form. |
| Expiry | Whole number of days, 1–365. Expired means `expires_at <= clock()` everywhere. |
| Dedupe | No alias and no expiry requested; matched on `url_hash`; `ON CONFLICT`. A 200 vs 201 reveals whether the URL existed before (documented). |
| Codes | Never reused. Rows are *retired* or *disabled*, never deleted. (Changes §11.) |
| Redirect | 302, `no-store`, GET and HEAD, the code format checked first |
| Stats for an expired or disabled code | 200 with flags |
| Rate limits | `POST /shorten` at 10 a minute (assumed); reads are lenient; IPv6 keyed per /64; the IP source is a setting |
| If Redis is down | Redirects fall back to Postgres; `/shorten` returns 503 (fails closed) |
| `short_url` | Built from `PUBLIC_BASE_URL` |
| Dependencies | `uv` + `uv.lock` instead of `requirements.txt` (changes §4). Valkey instead of Redis (changes §2). |
| Health | `/api/health/live` for platform checks; `/api/health` checks the dependencies |

## 10. Explore list (all verified to exist)

| Kind | Name | Use |
|---|---|---|
| Built-in | `/code-review`, `/security-review`, `/simplify` | `/code-review` on slices 3, 4 and 6; step 10 compares them on a planted SSRF bug |
| Plugin | `claude-security` | Fable-backed scan before deploy |
| Plugin | `pr-review-toolkit` | Read its `pr-test-analyzer` and `silent-failure-hunter`; don't install |
| Plugin | `security-guidance` | It reviews at every turn end and every commit, RED commits included. Read it, and install only if the cost is worth it. |
| skills.sh | `obra/superpowers`: `test-driven-development`, `verification-before-completion` | TDD discipline, slice 1 or 2 |
| Plugin marketplace | `trailofbits/skills`: `differential-review`, `insecure-defaults`, `property-based-testing`, `spec-to-code-compliance`, `supply-chain-risk-auditor`, `mutation-testing` | Compare `differential-review` with the Fable reviewer once; `property-based-testing` at slice 3 |
| Tools | Schemathesis, Hypothesis, mutmut, Playwright, axe-core, openapi-typescript, aiodns, idna, pip-licenses, license-checker-rseidelsohn, uv | As in sections 4 and 8 |
| Standards | OWASP API Security Top 10 (2023); RFC 9457; Google's engineering practices ("small CLs") | The reviewer's checklist; the error shape; PR size |
| Optional | Google Web Risk (commercial use) | Screen URLs for malware and phishing when they're created, after launch |

## 11. Changes to `docs/LEARNING-PLAN.md`

- Step 5: the Fable security-reviewer also reviews every slice.
- New step 6b: harness setup (section 7).
- Step 7:
  - slice 1 as written in section 8
  - defer `pyright-lsp` (mypy already checks types, and it's another process on a low-spec laptop)
  - `typescript-lsp` moves to step 14
- Step 9: `/ship-slice` follows the loop in section 2.
- Step 10: `security-guidance` is marked "read first, optional".
- Step 13: the hooks now include the verdict and frozen-files hooks, added at step 6b.
- Step 15: includes takedown.
- Step 16: becomes "extend CI" (the Claude GitHub App review, the blocked-merge demo).
- Steps 17–18: become slice 9.

## 12. Files touched

- **New:**
  - `docs/PLAN.md`, `docs/adr/*`, `TASKS.md`
  - `.claude/agents/{security,reliability}-reviewer.md`, `.claude/settings.json`
  - `scripts/{check.sh,red-check.py,review-diff.sh}`, `.quality-baseline.json`
  - `.github/workflows/{ci,nightly,deploy}.yml`, `.github/dependabot.yml`
  - `backend/pyproject.toml`, `uv.lock`, `.python-version`, `docker-compose.yml`, `vercel.json`
- **Changed:**
  - `.claude/agents/{testing,verification,push}-agent.md`
  - `CLAUDE.md` (§2, §4, §7, §8, §11, and the "(assumed)" lines)
  - `LICENSE`, `NOTICE`
  - `docs/LEARNING-PLAN.md`, `docs/qna/007-…`
  - `.gitignore`, `README.md`

## 13. Verification

- **Harness:**
  - The push-agent refuses without three verdict files for HEAD, and refuses to run on `main`.
  - Editing a frozen test as main Claude is blocked.
  - The security-reviewer has no tool that can write.
  - A `git push` asks you first.
  - The step 5 run records Fable's real token use.
- **TDD:**
  - Each slice's history reads contract → skeleton → `test:` → `feat:` → `refactor:`.
  - `red-check.py` shows the RED tests failing rather than erroring.
  - The held-out tests pass.
  - The suppression ratchet doesn't rise.
- **Tests can fail:** mutmut's survivors in `security.py` are reviewed before deploy. A one-time sabotage of the counter and the SSRF check turns the suite red.
- **No regressions:** step 16's demo PR breaks a slice 2 test, and `ci-ok` blocks the merge.
- **Security:**
  - The planted `169.254.169.254` bug gets a FAIL from the reviewer.
  - `claude-security` reports no open CRITICAL or HIGH findings.
  - The licence gate stays green.
- **Production:** slice 9's post-deploy tests pass, and a backup restore drill succeeds.

## Review points not adopted (and why)

- **Giving the reviewers Bash with a git-only hook** (the initial critique). Rejected: restricting shell commands safely to git is hard, because `git -c`, `--ext-diff` and textconv drivers can run other programs. A diff file plus Grep and Read is enough.
- **Using `expires_at = now()` for takedown** (DevOps). Replaced by `disabled_at`, which is a separate state that stats can report and cleanup can retire.
- **A deploy smoke test in slice 1** (architect). Replaced by slice 1's Neon-URL test, the deploy ADR and the `ClickRecorder` extension point. The first real deploy is slice 9, which avoids an early public, half-built service.
- **gitleaks and GitHub Pro** (DevOps). Not needed, because the repo stays public.
- **Removing the verification-agent's security checklist** (the initial critique). Kept, as a cheap second net.

## Preference review

- **Applied:**
  - plain terms first
  - nothing gets fixed without your say
  - LOW findings are logged, and review rounds are capped at 2
  - one concern per commit, with merge commits
  - costs given as ranges with measured anchors
  - every tool, licence and fact verified before it's listed
  - reviewer claims checked before they were adopted
  - Docker cost measured
  - the production standard and the commercial goal honoured
- **Challenged:** the plan is much longer than the first draft. That's deliberate, because the production standard and max-effort review were asked for. The plain-terms section is still the part to read first.
