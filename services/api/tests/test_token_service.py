"""
test_token_service.py — Unit tests for JWT token generation and decoding

Verifies token structure, expiration handling, tampered tokens, different keys,
and explicit zero-expiration deltas.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from jose import jwt

from app.domains.auth.service import (
    ALGORITHM,
    SECRET_KEY,
    create_access_token,
    decode_access_token,
)


def test_create_and_decode_valid_token() -> None:
    """A generated access token decodes correctly and preserves payload data."""
    payload_data = {"sub": "42", "role": "manager"}
    token = create_access_token(data=payload_data)

    assert isinstance(token, str)
    decoded = decode_access_token(token)

    assert decoded is not None
    assert decoded["sub"] == "42"
    assert decoded["role"] == "manager"
    assert "exp" in decoded
    # Expiration is in the future
    exp_dt = datetime.fromtimestamp(decoded["exp"], tz=timezone.utc)
    assert exp_dt > datetime.now(timezone.utc)


def test_decode_expired_token_returns_none() -> None:
    """A token whose expiration timestamp is in the past must fail validation."""
    payload_data = {"sub": "10", "role": "user"}
    # Token expired 10 minutes ago
    expired_token = create_access_token(
        data=payload_data, expires_delta=timedelta(minutes=-10)
    )

    decoded = decode_access_token(expired_token)
    assert decoded is None


def test_decode_token_with_zero_expiration_delta() -> None:
    """
    A token created with timedelta(0) sets exp to the current timestamp
    and does not inherit the default 60-minute expiration window.
    """
    before = int(datetime.now(timezone.utc).timestamp())
    payload_data = {"sub": "15", "role": "user"}
    instant_token = create_access_token(
        data=payload_data, expires_delta=timedelta(seconds=0)
    )
    after = int(datetime.now(timezone.utc).timestamp())

    # Verify that exp is bounded by [before, after] and not +3600s
    unverified = jwt.decode(
        instant_token,
        SECRET_KEY,
        algorithms=[ALGORITHM],
        options={"verify_exp": False},
    )
    assert before <= unverified["exp"] <= after + 1


def test_decode_token_with_negative_expiration_delta() -> None:
    """A token created with negative timedelta (e.g. -1s) immediately returns None on decode."""
    payload_data = {"sub": "20", "role": "user"}
    expired_token = create_access_token(
        data=payload_data, expires_delta=timedelta(seconds=-1)
    )
    assert decode_access_token(expired_token) is None


def test_decode_tampered_token_returns_none() -> None:
    """Modifying the token string or payload signature must invalidate the token."""
    token = create_access_token(data={"sub": "1", "role": "user"})
    parts = token.split(".")
    assert len(parts) == 3

    # Tamper with the payload part
    tampered_token = f"{parts[0]}.eyJyYW5kb20iOiAidmFsdWUifQ.{parts[2]}"
    assert decode_access_token(tampered_token) is None

    # Tamper with signature
    tampered_sig = f"{parts[0]}.{parts[1]}.invalidsignature123"
    assert decode_access_token(tampered_sig) is None


def test_decode_token_signed_with_different_secret() -> None:
    """A token signed with an unknown secret key must be rejected."""
    payload = {
        "sub": "99",
        "role": "admin",
        "exp": datetime.now(timezone.utc) + timedelta(minutes=30),
    }
    alien_token = jwt.encode(payload, "completely-different-secret", algorithm=ALGORITHM)

    assert decode_access_token(alien_token) is None


def test_decode_malformed_token_strings() -> None:
    """decode_access_token returns None for arbitrary strings, empty strings, or garbage."""
    assert decode_access_token("") is None
    assert decode_access_token("not-a-jwt") is None
    assert decode_access_token("a.b.c.d.e") is None
