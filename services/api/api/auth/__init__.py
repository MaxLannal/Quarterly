"""Accounts (decision 5, SPEC "Accounts and anonymity"): email verification, argon2id passwords,
Redis sessions with CSRF, rate limits and log redaction.

Privacy rules this package keeps: an email address is written only to `account.email` (and, for
at most 10 minutes, to the Redis record of a pending verification); IP addresses are only ever
used as a keyed hash in a Redis counter that expires within 24 hours; nothing here logs either.
"""
