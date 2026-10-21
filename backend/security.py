
import re
import uuid
from datetime import datetime, timedelta, timezone
from pwdlib import PasswordHash
from jose import jwt, JWTError

from config import settings

password_hash = PasswordHash.recommended()

# Deferred import to avoid circular imports; models imports database/config only.
import models  # noqa: E402


def hash_password(password: str) -> str:
    return password_hash.hash(password)


def verify_password(
    plain_password: str,
    hashed_password: str,
) -> bool:
    return password_hash.verify(
        plain_password,
        hashed_password,
    )


def validate_password_complexity(password: str) -> None:
    """Enforce configurable password complexity policy. Raises ValueError with details."""
    errors = []
    if len(password) < settings.password_min_length:
        errors.append(f"at least {settings.password_min_length} characters")
    if settings.password_require_uppercase and not re.search(r"[A-Z]", password):
        errors.append("one uppercase letter")
    if settings.password_require_lowercase and not re.search(r"[a-z]", password):
        errors.append("one lowercase letter")
    if settings.password_require_digit and not re.search(r"[0-9]", password):
        errors.append("one digit")
    if settings.password_require_symbol and not re.search(r"[^A-Za-z0-9]", password):
        errors.append("one symbol")
    if errors:
        raise ValueError("Password must contain " + ", ".join(errors))


def check_password_history(db, user_id: int, new_password: str) -> None:
    """Reject the new password if it matches any of the last N password hashes for the user."""
    if settings.password_history_count <= 0:
        return
    recent = db.query(models.PasswordHistory).filter_by(user_id=user_id).order_by(
        models.PasswordHistory.created_at.desc(),
    ).limit(settings.password_history_count).all()
    for entry in recent:
        if verify_password(new_password, entry.hashed_password):
            raise ValueError("Password cannot be one of your previous passwords.")


ALGORITHM = "HS256"


def create_access_token(data: dict, secret_key: str | None = None, expires_minutes: int | None = None) -> str:
    """Create a signed, short-lived JWT access token."""
    to_encode = data.copy()
    now = datetime.now(timezone.utc)
    expires = expires_minutes or settings.access_token_minutes
    to_encode.update({
        "iat": now,
        "exp": now + timedelta(minutes=expires),
        "jti": str(uuid.uuid4()),
        "typ": "access",
        "iss": settings.token_issuer,
        "aud": settings.token_audience,
    })
    return jwt.encode(to_encode, secret_key or settings.secret_key, algorithm=ALGORITHM)


def verify_access_token(token: str, secret_key: str | None = None):
    """Verify a JWT and return its payload, or None if invalid."""
    try:
        payload = jwt.decode(
            token,
            secret_key or settings.secret_key,
            algorithms=[ALGORITHM],
            issuer=settings.token_issuer,
            audience=settings.token_audience,
        )
        audience = payload.get("aud")
        audience_matches = (
            audience == settings.token_audience
            or isinstance(audience, list) and settings.token_audience in audience
        )
        if (
            payload.get("typ") != "access"
            or not payload.get("sub")
            or payload.get("iss") != settings.token_issuer
            or not audience_matches
            or not payload.get("exp")
            or not payload.get("iat")
            or not payload.get("jti")
        ):
            return None
        return payload
    except JWTError:
        return None


