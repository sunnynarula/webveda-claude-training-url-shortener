# 0003. Canonical URLs: the URL checked is the URL stored and redirected to

Status: accepted, 2026-09-22 (`docs/PLAN.md` §1)

## Context

- **International hostnames.** Python's `getaddrinfo` converts them with IDNA
  2003, while browsers use UTS-46. Tested on this machine, `faß.de` became
  `fass.de` in Python but `xn--fa-hia.de` in the `idna` package (UTS-46).
  So the SSRF check could vet one host while visitors go to another.
- **Byte length.** Storing the URL "exactly as sent" allows 2,048 non-ASCII
  characters, which is up to 8 KB. A B-tree index row that size fails in
  Postgres, and the user sees a 500.
- **Redirect encoding.** Starlette's `RedirectResponse` re-quotes the URL, so
  an unusual stored URL may not be the one that gets redirected to.

## Decision

- Parse the submitted URL once. Accept only `http` or `https`, printable ASCII
  and RFC 3986 syntax.
- Reject userinfo (`user@host`), `\` characters, invalid ports, and hosts that
  fail IDNA.
- Convert the host to punycode with the `idna` package (UTS-46), then rebuild
  the URL from its parts.
- Check the length on that canonical form. The canonical string is what's
  resolved, stored, deduplicated and redirected to. Pydantic's `HttpUrl` isn't
  used, because it rewrites URLs (e.g. adds `/`).

## Consequences

- The response's `original_url` equals the redirect's `Location` header.
- Visually confusable hostnames show up in punycode, so they're visible.
- A few exotic URLs that browsers would accept are rejected, and that's
  documented.
