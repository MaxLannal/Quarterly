# Open questions

Questions for Richard. Each has a default so work can continue; nothing here is a guessed catalog fact.

## Decisions (docs/SPEC.md "Summary and decisions to confirm")

1. **Decision 5 (accounts) — resolved 2026-11-12.** Richard edited row 5 to "Email and password
   is stored on the backend" and confirmed it: accounts store the verified `@uchicago.edu` email and
   an argon2id password hash; no blind signatures. CLAUDE.md and SPEC "Accounts and anonymity" were
   updated to match. Forum anonymity (per-page pseudonyms, HMAC author refs) is unchanged.
2. **Decision 12 (name).** The UI uses "Quarterly" / "Quarterly Planner". The forum name is written
   "Quarterly Forumn"; the UI uses "Quarterly Forum" assuming a typo. Code identifiers keep the
   neutral names (`planner_core`, `api`, ...); the Compose project and DB are `quarterly`.

## Infrastructure

3. **OpenRouter model names** in `llm_routing.yaml` (`anthropic/claude-opus-5.5` style) are not
   verified against OpenRouter's catalog; confirm before prompt 07. `max_tokens` values there are
   starting defaults, not from the spec.

## Contracts (prompt 01)

4. **"Terms Offered" to `p_offered`.** Until schedule data exists, listed quarters get p = 0.95 and
   unlisted Autumn/Winter/Spring get p = 0.05 (`method: catalog`), so V04 warns when a course is
   placed outside its catalog quarters. Confirm this mapping or give another.
5. **One `program_version` per program per catalog year.** Editing a published version in place
   would change plans made under it; v1 relies on review items for such edits. Revisit before
   prompt 09.

## Prompt 04

Choices made so work could continue; each is the conservative option and easy to change.

6. **Email provider.** `EMAIL_BACKEND=console` (development: prints the code and pending id, never
   the address) or `smtp` (stdlib `smtplib`, STARTTLS with certificate verification, works with
   any transactional provider). No provider SDK was added. Which provider, and the `EMAIL_FROM`
   address? The API refuses to start with the console backend, development secrets
   or a non-Secure cookie unless `ENVIRONMENT` is explicitly `development` or `test`.
7. **Plus-addressing and aliases.** Only plain `local@uchicago.edu` is accepted: no subdomains
   (`@cs.uchicago.edu`, `@alumni.uchicago.edu`) and no `+tag`, so one mailbox cannot verify
   several accounts. If real student addresses need either, relax `normalize_uchicago_email`.
8. **Rate-limit numbers** (`api/auth/ratelimit.py` and the `ip_limit(...)` on each route): 5 codes
   per address per hour, 5 wrong codes per pending id, 10 failed logins per login name per 15
   minutes, 10 failed password confirmations per account per 15 minutes; per IP per day: 40
   email/reset starts, 40 registrations, 100 code checks, 300 logins. IP limits are loose because
   campus networks share addresses. Confirm or tune.
9. **Client IP behind the proxy (needs a two-line change outside prompt 04's files).** The API
   sees nginx's address unless nginx sends the client's: add
   `proxy_set_header X-Forwarded-For $remote_addr;` to `apps/web/docker/nginx.conf` and set
   `TRUSTED_PROXY_HOPS=1` for the `api` service. Until then every user behind the proxy shares one
   IP bucket. With `TRUSTED_PROXY_HOPS=0` the header is ignored (it could be forged).
10. **"IP counter never written to disk."** The app stores only `HMAC(key, day ‖ ip)` as a Redis
    key with a 24-hour TTL, never the address. Redis itself snapshots to its volume by default;
    for the letter of the spec, run Redis with `--save "" --appendonly no` (sessions and pending
    codes are then lost on a Redis restart, which is acceptable) or accept the keyed hash on disk.
11. **Session lifetime** is 30 days, fixed (not extended on use). Reset ends all sessions; a
    password change ends all but the current one.
12. **Forum identity.** `api.auth.hashing.author_ref(account_id, page_id)` implements the SPEC's
    `HMAC(server_key, account_id ‖ page_id)`; account deletion recomputes it per forum page to
    find an account's rows, so prompt 08 must use the same function for `author_ref`,
    `voter_ref` and `reporter_ref`. With "delete my posts", a comment that someone else replied
    to is blanked ("[deleted]", no author) instead of removed, so the replies survive; vote rows
    are removed but tallied scores are not recomputed. Confirm.
13. **CSRF for later prompts.** Every POST/PATCH/DELETE sent with a session cookie needs
    `X-CSRF-Token` (from `SessionOut.csrf_token`), enforced app-wide. Exempt: the pre-session
    `/auth/*` steps and the stateless `POST /verify`. Frontend code can use the client in
    `apps/web/src/features/auth/api.ts`, which adds the header.
14. **Plans API.** CONTRACTS lists `/plans` CRUD and `/plans/import` as "04/06"; prompt 04 built
    only the read path for `GET /account/export` (`api/auth/account_data.py`, which assumes
    `goal.params` holds the goal's type-specific fields). The rest is left to prompt 06.
15. **Suspended accounts** (`account.status`, `suspended_until`) can still log in; the forum
    (prompt 08) should enforce suspension where it matters.

