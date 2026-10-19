
import uuid
from datetime import datetime, timedelta, timezone
from pwdlib import PasswordHash
from jose import jwt, JWTError

from config import settings

password_hash = PasswordHash.recommended()


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


