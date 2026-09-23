# 0012. An external string is re-emitted from its parse, and its parameters are an allowlist

Status: accepted, 2026-09-23 (triage of the slice 1 held-out review, issues #1–#18)

## Context

The held-out tests for slice 1 produced fourteen findings. Two more came from
reading library source while implementing, and this triage added two, making
eighteen issues in all. **Eight of them are one mistake made in three places**,
and they are the eight named in the table below — the count and the table were
written from the same list this time, the first version of this paragraph having
claimed twelve against a table of eight:

| Where | What it does | Issues |
|---|---|---|
| `app/config.py::bare_origin` | checks the *parsed* pieces of an origin, then returns the *original* string | #1 #2 #4 |
| `testsupport/db_guard.py` | decides with `urlsplit` whether a string is safe, then hands the string to libpq, which parses it differently | #6 #7 |
| `app/database.py::asyncpg_url_and_args` | reads a URL through SQLAlchemy's parser, and passes every parameter it did not recognise to asyncpg, which rejects them | #3 #11 #17 |

The shape is always the same. A string is parsed into a structured view; a
decision is taken on that view; then the original string, or a partly
processed one, is handed to a **different consumer with a different parser**.
Wherever the two parsers disagree, the decision was taken about a string that
nobody will ever act on:

- `urlsplit` deletes tabs and newlines anywhere in a URL, and trims leading
  whitespace. libpq does neither.
- `urlsplit` treats `#` as starting a fragment. libpq has no fragments: `#`
  is an ordinary character and a `?` after it still begins the parameter list.
  Confirmed by handing `…/urlshortener_test#?dbname=postgres` to `psql`,
  which connected to `postgres`.
- SQLAlchemy's `parse_qsl` drops a parameter whose value is empty. libpq
  keeps it.
- SQLAlchemy's asyncpg dialect passes unknown query parameters to
  `asyncpg.connect`, which has no `**kwargs` and raises.

**This project had already decided the answer, for one input.** ADR 0003 says
of a submitted URL: *"rebuild the URL from its parts … The canonical string is
what's resolved, stored, deduplicated and redirected to."* That rule was
applied to the one input a user posts, and to none of the strings an operator
configures. The defect class is not new knowledge; it is a decision that was
never generalised.

## Decision

Four rules, for any string that arrives from outside the process — a setting,
an environment variable, a connection URL, a request field:

1. **Re-emit, never echo.** What we hand on is rebuilt from the pieces we
   validated, not the text we were given. If validation and storage can
   disagree, they eventually will.
2. **Parameters are an allowlist.** Where we interpret the parameters of a
   URL or a string, we name the ones we understand and refuse the rest,
   saying which. A denylist is only ever as good as our imagination, and it
   fails silently — #7 is a denylist that misses `?HOST=`, #11 is the absence
   of a list at all.
3. **A security-relevant setting fails closed.** A control that means
   "require X" is never satisfied by absence, emptiness or ambiguity. `?sslmode=`
   with no value is a refusal, not a default (#3).
4. **Where another program parses the same string, ask the authority instead
   of being clever.** Our parse of a connection URL is a guess about what the
   server will do. Where the answer matters and the server can be asked, ask
   it: the test-database guard should confirm with `select current_database()`
   once fixtures connect (slice 2), and keep the string checks as the cheap
   first gate.

## Consequences

- `bare_origin` returns a rebuilt origin — scheme and host lower-cased, port
  preserved — so a capitalised host can no longer be accepted at startup and
  then fail to match at runtime, and an invisible character cannot survive
  validation.
- `asyncpg_url_and_args` accepts a named set of query parameters and refuses
  the rest, which is the same change that fixes #3, #7 and #11 at once.
- Some exotic-but-legal inputs are refused. That is the trade this project
  already made in ADR 0003, and it is the right way round for settings, which
  are written once by an operator who can be told exactly what was wrong.
- Rule 4 costs a round-trip in the test fixtures and is the only check that
  cannot be defeated by a parser we did not think about.

## Related

- ADR 0002 (one error model) — rule 1 is also why a 422 must not reflect a
  field name it was given (#14).
- ADR 0003 (canonical URLs) — the same rule, decided earlier for user URLs.
- ADR 0010 (deploy target) — the Neon connection URL is where rules 2 and 3
  are load-bearing (#11, #15, #20).
- The review round that followed found four more instances of the same rules:
  a URL with no `sslmode` at all (#20, rule 3), a host list the guard's parser
  could not see past (#22, rule 4), a scheme rewritten rather than checked
  (#24, rule 2) and an invisible character outside ASCII (#25, rule 1). The
  rules held; the first pass applying them did not reach far enough.
