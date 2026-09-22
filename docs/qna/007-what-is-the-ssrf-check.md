# 007. What the SSRF check is

**Asked:** 2026-09-22 · **Updated:** 2026-09-22

**Changed:** the first version recommended `is_global` as "one broad rule". Tests
run while reviewing the build plan showed that's incomplete: `is_global` lets
multicast and several IPv6 disguises of private addresses through. This version
gives the full rule, and adds two problems the first version missed: hosts in
international characters, and slow DNS.

> What is the ssrf thing/check?

## Short answer

SSRF (server-side request forgery) is an attack in which someone tricks a
server into sending a request to a place the attacker can't reach directly.
That's usually the server's own internal network, or the cloud metadata
address `169.254.169.254`, which can hand out credentials. The check in
`CLAUDE.md` §6 refuses to shorten any URL whose host resolves to a loopback,
private or link-local address, so the shortener can't be used as a stepping
stone into anyone's internal network.

## Answer

### The attack

A server that fetches URLs for you makes the request from *inside* its own
network. Some addresses only mean something there: `localhost`, internal
services on `10.x` or `192.168.x`, and the instance metadata service at
`169.254.169.254`. AWS, GCP and Azure all use that address, and it can return
the machine's cloud credentials. Hand such a server `http://169.254.169.254/...`
and it fetches something you were never meant to reach.

PortSwigger's definition: *"a web security vulnerability that allows an
attacker to cause the server-side application to make requests to an
unintended location."*

### Why a URL shortener needs the check

As specified, this app never fetches the URLs it stores. `/shorten` saves the
URL, and `/{short_code}` replies with a 302 redirect that the *visitor's*
client follows. So why guard against SSRF? There are three reasons.

1. **Other servers follow your links.** Link-preview bots, chat apps that show
   link previews, webhook senders and crawlers are all servers that follow
   redirects. A shortener is an open redirect by design, and PortSwigger lists
   open redirection as a standard way to *"bypass filter-based defenses"*.
   Here is how that works. The victim service checks `sho.rt/abc`, sees a
   public address and allows it. Then it follows the 302 and lands on
   `169.254.169.254` inside *its own* network. OWASP tells such services to
   stop following redirects *"in order to prevent the bypass of the input
   validation"*. Your check is the other half of that defence: never hand out
   a redirect to an internal address in the first place.
2. **Features you might add later.** Link previews, "is this link still
   alive?" checks and safe-browsing lookups all need the backend to fetch a
   stored URL. Once it does, an unchecked URL becomes direct SSRF against
   your own server. Checking when the link is created keeps the stored data
   safe for those features.
3. **Phishing.** The spec calls it an "SSRF/phishing guard". A public
   shortener has no legitimate reason to send visitors to private addresses,
   such as a home router's admin page on `192.168.x.x`. A separate rule, step
   1 of the same validation, blocks `javascript:`, `data:` and `file:` links.

Module 12 describes the risk as a service that *"will happily 'visit' any URL
it's given"*. Strictly speaking, the app as specified doesn't visit URLs, and
reasons 1 and 2 are why the check matters anyway. That makes it a good test
of Claude's explanation in step 4 of the learning plan, where it explains
this back to you.

### What the check has to do

The check is step 3 of the validation in `CLAUDE.md` §6, and it goes in
`security.py`:

1. Take the host out of the URL.
2. Resolve the host to IP addresses, all of them.
3. Reject the URL if **any** of those addresses is loopback, link-local or
   private.

### Why it's harder than it looks

Tested with Python 3.12.3 on this machine. For numeric hosts,
`socket.getaddrinfo` parses the text itself and makes no network request.

| Host in the URL | What the system treats it as |
|---|---|
| `2852039166` | `169.254.169.254` |
| `0xA9FEA9FE` | `169.254.169.254` |
| `0251.0376.0251.0376` | `169.254.169.254` |
| `127.1` | `127.0.0.1` |
| `0` | `0.0.0.0` |

What that means for the code:

- **Compare addresses, never strings.** A text check for `169.254.169.254`
  misses the three encoded forms above. Resolve the host first, then check the
  address you get back. OWASP lists "Hex, Octal, Dword, URL and Mixed
  encoding" as tricks to test against.
- **Any hostname can point inward.** An attacker's own domain can resolve to
  `10.0.0.5`. That's why the spec says to resolve the host rather than trust
  the name.
- **`is_global` alone is not enough.** On Python 3.12.3, `is_global` is
  **True** for all of these, although each one is unsafe:

  | Address | What it really is |
  |---|---|
  | `224.0.0.1` | multicast |
  | `64:ff9b::a9fe:a9fe` | `169.254.169.254` wrapped in a NAT64 address |
  | `::a9fe:a9fe` | `169.254.169.254` in the old IPv4-compatible IPv6 form |
  | `::ffff:0:a9fe:a9fe` | `169.254.169.254` in the IPv4-translated form |
  | `fec0::1` | a deprecated site-local address |

- **The full rule** (the approved build plan uses this):
  1. For IPv4, the address must be global **and** not multicast.
  2. For IPv6, first unwrap any IPv4 address hidden inside it: IPv4-mapped
     (`ipv4_mapped`), NAT64 (`64:ff9b::/96` and `64:ff9b:1::/48`), 6to4
     (`sixtofour`) and Teredo (`teredo`). Check the unwrapped address with
     rule 1.
  3. Any other IPv6 address must be inside `2000::/3`, the global unicast
     range, **and** global and not multicast. Being inside `2000::/3` rules
     out all three IPv6 forms in the table.
  4. Every address the host resolves to must pass. One private answer is
     enough to reject the URL.

  Keep every address above, and the ones earlier in this section, as tests.
- **International hostnames.** Python's `getaddrinfo` converts a hostname
  written in international characters with the old IDNA 2003 rules, but
  browsers use UTS-46. Tested here, the two give different hosts for
  `faß.de`: `fass.de` (Python) versus `xn--fa-hia.de` (browsers). So the
  check would vet one server while visitors go to another.
  - Convert the host once with the `idna` package (UTS-46).
  - Resolve that converted host.
  - Store and redirect that same ASCII URL.
- **Slow DNS.** `loop.getaddrinfo` borrows asyncio's default thread pool,
  which has 8 threads on this laptop. A timeout stops the *wait*, not the
  thread, so an attacker whose nameserver answers slowly can tie up every
  thread, and the database driver uses that same pool. Use a truly async
  resolver such as `aiodns`, with a cap on how many lookups run at once.
- **Pin the Python patch version.** `ipaddress`'s built-in tables have changed
  between patch releases, so the tests should run on the version you deploy.
- **Keep it async.** `socket.getaddrinfo` blocks the event loop. This backend
  is fully async (§2), so use asyncio's `loop.getaddrinfo` instead.

### What no check at creation time can stop

- **The domain's DNS changing later**, known as DNS rebinding. A domain can
  resolve to a public address when you check it and to a private one
  afterwards. OWASP notes that resolution happens *"when the business code
  will be executed"*, not when you validated.
- **The target redirecting onward.** A public URL can itself redirect to an
  internal address. The shortener only sees the first hop.

For a service that only redirects, these are reasonable limits to accept.
They belong in the README's known-limitations section.

### Where it shows up in the learning plan

- **Step 4:** before any code exists, Claude explains why the check matters.
- **Step 10:** you write the check yourself, with the learning-output-style
  plugin, and write the tricky cases above as tests before the code.
- **Step 10's break test:** on a throwaway branch, let `169.254.169.254`
  through and see which reviewer catches it.

## Sources

- `CLAUDE.md` §2 (fully async) and §6 validation steps 1 and 3;
  `ASSIGNMENT.md` §5 ("this is an SSRF guard, not busywork");
  `.claude/agents/verification-agent.md` (security checklist);
  `docs/LEARNING-PLAN.md` steps 4 and 10.
- Course repo, `modules/module-12-url-shortener-project.md` line 16.
- <https://portswigger.net/web-security/ssrf> (definition; attacks on
  localhost and back-end systems; bypassing filters through open redirection).
- <https://cheatsheetseries.owasp.org/cheatsheets/Server_Side_Request_Forgery_Prevention_Cheat_Sheet.html>
  (metadata endpoints for AWS, GCP and Azure; disabling redirect following;
  DNS resolution happening at execution time; encoding tricks).
- Local run on Python 3.12.3: `socket.getaddrinfo` on the numeric hosts
  above, and `ipaddress` flags for `169.254.169.254`, `10.0.0.5`,
  `192.168.1.1`, `127.0.0.1`, `::1`, `::ffff:169.254.169.254`, `0.0.0.0` and
  `8.8.8.8` (only `8.8.8.8` has `is_global` True).
- Update runs on Python 3.12.3:
  - `is_global`, `is_multicast`, `sixtofour`, `teredo` and membership of
    `2000::/3` for the addresses in the table above, plus the 6to4 address
    `2002:a9fe:a9fe::1` (unwraps to `169.254.169.254`) and a Teredo address.
  - `"faß.de".encode("idna")` gives `fass.de`, while `idna.encode("faß.de",
    uts46=True)` gives `xn--fa-hia.de`.
  - The default thread pool size here is min(32, cores + 4) = 8.
- **Not verified here:** that the metadata service returns credentials (that
  comes from the providers' documentation, not a test), and the behaviour of
  Python versions other than 3.12.3.

## Related

- [002. What "a slice" means](002-what-is-a-slice.md) (slice 3 builds this
  check)
- [003. What the verification agent is](003-what-is-the-verification-agent.md)
  (its security checklist covers it)
- [001. What goes in a README, and how to keep it updated automatically](001-readme-standard-and-auto-updates.md)
  (known limitations)
