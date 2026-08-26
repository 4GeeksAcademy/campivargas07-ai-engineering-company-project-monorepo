"""
test_password_service.py — Unit tests for password hashing and verification

Verifies bcrypt hashing, salting uniqueness, correct/incorrect verification,
special characters, and resilience against corrupt hashes.
"""

from __future__ import annotations

import pytest

from app.domains.auth.service import hash_password, verify_password


def test_hash_password_generates_valid_bcrypt_hash() -> None:
    """A hashed password should be a non-empty string with standard bcrypt prefix."""
    plain = "MiClaveSegura123!"
    hashed = hash_password(plain)

    assert isinstance(hashed, str)
    assert hashed != plain
    assert hashed.startswith("$2b$") or hashed.startswith("$2a$")


def test_verify_password_matches_correct_password() -> None:
    """verify_password returns True when plain password matches hash."""
    plain = "Brasaland2026*"
    hashed = hash_password(plain)

    assert verify_password(plain, hashed) is True


def test_verify_password_rejects_incorrect_password() -> None:
    """verify_password returns False when plain password does not match hash."""
    plain = "PasswordCorrecta123"
    wrong = "PasswordErronea456"
    hashed = hash_password(plain)

    assert verify_password(wrong, hashed) is False


def test_hash_salting_produces_unique_hashes() -> None:
    """Two hashes of the exact same password must differ due to unique random salts."""
    password = "MismaContraseña123"
    hash_1 = hash_password(password)
    hash_2 = hash_password(password)

    assert hash_1 != hash_2
    assert verify_password(password, hash_1) is True
    assert verify_password(password, hash_2) is True


@pytest.mark.parametrize(
    "special_password",
    [
        "Ñandú#2026!@$",
        "🍔Brasa🔥Land🍗100%",
        "espacios en blanco y simbolos @#$%^&*()_+~`",
        "A" * 72,  # Bcrypt maximum effective password length
    ],
)
def test_password_with_special_characters_and_emojis(special_password: str) -> None:
    """Hashing and verifying supports complex UTF-8 strings, spaces, and emojis."""
    hashed = hash_password(special_password)
    assert verify_password(special_password, hashed) is True
    wrong_password = "wrong_" + special_password if len(special_password) <= 60 else "Z" + special_password[1:]
    assert verify_password(wrong_password, hashed) is False


def test_verify_password_gracefully_handles_corrupt_hash() -> None:
    """verify_password should return False and not raise exceptions when hash is malformed."""
    assert verify_password("cualquier_clave", "not_a_valid_bcrypt_hash") is False
    assert verify_password("cualquier_clave", "$2b$12$invalidcorruptedstringhere") is False
    assert verify_password("cualquier_clave", "") is False
