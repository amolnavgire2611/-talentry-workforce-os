from jose import jwt

from config import settings
from security import ALGORITHM, create_access_token, verify_access_token, validate_password_complexity


TEST_SECRET = "issuer-audience-test-secret-with-enough-entropy"


def test_access_tokens_require_the_configured_issuer_and_audience():
    valid = create_access_token({"sub": "42", "sid": "session-42"}, secret_key=TEST_SECRET)
    assert verify_access_token(valid, TEST_SECRET)["sub"] == "42"

    claims = jwt.get_unverified_claims(valid)
    claims["iss"] = "another-issuer"
    wrong_issuer = jwt.encode(claims, TEST_SECRET, algorithm=ALGORITHM)
    assert verify_access_token(wrong_issuer, TEST_SECRET) is None

    claims = jwt.get_unverified_claims(valid)
    claims["aud"] = "another-service"
    wrong_audience = jwt.encode(claims, TEST_SECRET, algorithm=ALGORITHM)
    assert verify_access_token(wrong_audience, TEST_SECRET) is None

    claims = jwt.get_unverified_claims(valid)
    del claims["iss"]
    missing_issuer = jwt.encode(claims, TEST_SECRET, algorithm=ALGORITHM)
    assert verify_access_token(missing_issuer, TEST_SECRET) is None

    assert settings.token_issuer
    assert settings.token_audience


def test_password_complexity_rejects_short_passwords():
    try:
        validate_password_complexity("Ab1!")
        assert False, "Should have raised ValueError"
    except ValueError as e:
        assert "at least" in str(e)


def test_password_complexity_accepts_min_length_passwords():
    validate_password_complexity("password123!")
    validate_password_complexity("Ab1!xy12")
    validate_password_complexity("Str0ng!Pass")


def test_rate_limiting_blocks_excessive_registration_attempts(client):
    """Too many registration attempts from the same IP should be rate limited."""
    for i in range(20):
        response = client.post("/api/auth/register", json={
            "name": f"User {i}",
            "email": f"user{i}@example.com",
            "password": "Strong!Pass123",
        })
        if response.status_code == 429:
            break
    else:
        assert False, "Expected rate limiting after 20 registration attempts"
    # Verify the rate limited response
    assert response.status_code == 429


def test_rate_limiting_blocks_excessive_password_reset_attempts(client):
    """Too many password reset attempts from the same IP should be rate limited."""
    for i in range(5):
        response = client.post("/api/auth/password/forgot", json={
            "email": f"user{i}@example.com",
        })
        if response.status_code == 429:
            break
    else:
        assert False, "Expected rate limiting after 5 password reset attempts"
    assert response.status_code == 429
