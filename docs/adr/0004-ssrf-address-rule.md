# 0004. SSRF: the address rule and the resolver

Status: accepted, 2026-09-22 (`docs/PLAN.md` §1, `docs/qna/007`)

## Context

On Python 3.12.3, `ipaddress`'s `is_global` returns True for several
dangerous addresses:
- the multicast address `224.0.0.1`
- IPv6 disguises of `169.254.169.254`: NAT64 `64:ff9b::a9fe:a9fe`,
  IPv4-compatible `::a9fe:a9fe` and IPv4-translated `::ffff:0:a9fe:a9fe`
- the site-local address `fec0::1`

Also, `loop.getaddrinfo` runs in asyncio's default thread pool (8 threads on
the dev laptop). A timeout doesn't free a thread, so a slow attacker-run
nameserver can use up every thread, and the database driver needs that same
pool.

## Decision

- **IPv4:** reject unless the address is global and not multicast.
- **IPv6:**
  - First unwrap any IPv4 address hidden inside it: IPv4-mapped, NAT64
    (`64:ff9b::/96` and `64:ff9b:1::/48`), 6to4 and Teredo. Check the result
    with the IPv4 rule.
  - Otherwise, require an address inside `2000::/3`, global and not multicast.
- **Every** resolved address must pass. One bad answer rejects the URL.
- DNS goes through the `Resolver` seam, backed by `aiodns`, with a cap on
  concurrent lookups and a 2-second timeout. A failed or timed-out lookup
  gives 400. Numeric hosts (decimal, hex and octal IPs) always go through the
  real parser, including in tests.
- Pin the Python patch version. `ipaddress`'s tables have changed between
  patch releases.

## Consequences

- Every address named above is a test case.
- Known limits: the check can't stop DNS answers that change after a link is
  created, or a target that redirects onward. Both are listed as known
  limitations.
