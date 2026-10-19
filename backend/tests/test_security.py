from jose import jwt

from config import settings
from security import ALGORITHM, create_access_token, verify_access_token


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
