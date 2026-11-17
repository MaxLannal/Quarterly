"""argon2id checks are limited per process, so a burst of logins cannot exhaust memory
(final security review E)."""

from __future__ import annotations

import threading

import pytest
from api.auth import passwords
from fastapi import HTTPException


def test_a_full_house_answers_503_instead_of_hashing(monkeypatch: pytest.MonkeyPatch) -> None:
    full = threading.BoundedSemaphore(1)
    full.acquire()  # every slot taken
    monkeypatch.setattr(passwords, "_slots", full)
    monkeypatch.setattr(passwords, "WAIT_S", 0.01)
    for call in (
        lambda: passwords.verify_password(None, "pw"),
        lambda: passwords.hash_password("pw"),
    ):
        with pytest.raises(HTTPException) as caught:
            call()
        assert caught.value.status_code == 503


def test_slots_are_given_back() -> None:
    stored = passwords.hash_password("correct horse")
    for _ in range(passwords.MAX_CONCURRENT + 2):
        assert passwords.verify_password(stored, "correct horse")
        assert not passwords.verify_password(stored, "wrong")
    assert passwords._slots.acquire(blocking=False)  # nothing left held
    passwords._slots.release()
