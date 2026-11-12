# Prompt 04 · Anonymous accounts (blind signatures)

> Recommended: Fable 5.2 (security-critical). Plan mode first. Parallel with 02, 03, 05. Finish with the `security-privacy-reviewer` subagent.

---

Context: `CLAUDE.md`, SPEC "Accounts and anonymity" (follow its protocol steps 1-6 exactly) and the auth stubs from prompt 01.

Build:
1. **Email step:** accept only `@uchicago.edu`; `h = HMAC(ISSUANCE_HMAC_KEY, lowercase(email))`; quota check in `issuance_ledger` (1 per academic year); 6-digit code with 10-minute TTL in Redis; email provider abstraction with a console backend for development. A logging filter that removes anything shaped like an email address, with a test proving it.
2. **Blind issuance:** client uses `@cloudflare/blindrsa-ts` with RSABSSA-SHA384-PSS-Randomized. Server BlindSign = raw RSA private operation plus the RFC's self-check; key per academic year with a key id; public key served at `/auth/keys`. Increment the ledger and delete Redis state on success.
3. **Registration:** a fresh request with no cookies from earlier steps (`credentials: 'omit'`); verify the final signature with Python `cryptography` (PSS, SHA-384, MGF1-SHA384, salt 48); reject spent tokens; argon2id passwords (argon2-cffi); store hashes of 10 client-generated recovery codes. Passkeys may be a stub in v1.
4. **Sessions:** Redis-backed, httpOnly, Secure, SameSite=Lax cookie; CSRF token on state-changing requests; rate limits on every auth endpoint.
5. **Account:** export plans as JSON; delete account with the option to delete or keep posts as "[deleted account]".
6. **Frontend:** sign-up (4 steps) and login pages as in the mockup, including the recovery-code screen.

Tests: RFC 9474 Appendix A test vectors on both client and server; double-spend rejected; quota enforced; a schema test that fails if any column could join `issuance_ledger` to `account`; no email or IP reaches the database or logs (inspect captured logs in the test).

Do not invent cryptography beyond the RFC. If a library choice is uncertain, stop and ask.

Done when `make check` passes. Run `security-privacy-reviewer`, fix every high and medium finding, then `spec-reviewer`. Update `docs/PROGRESS.md`.
