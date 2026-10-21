"""Environment-backed application configuration."""

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

BACKEND_DIR = Path(__file__).resolve().parent
load_dotenv(BACKEND_DIR / ".env")


def _csv(value: str) -> list[str]:
    return [item.strip() for item in value.split(",") if item.strip()]


@dataclass(frozen=True)
class Settings:
    database_url: str
    secret_key: str
    access_token_minutes: int
    cors_origins: list[str]
    admin_bootstrap_token: str
    environment: str
    employee_directory_enabled: bool
    refresh_session_days: int
    secure_cookies: bool
    token_issuer: str
    token_audience: str
    password_min_length: int
    password_require_uppercase: bool
    password_require_lowercase: bool
    password_require_digit: bool
    password_require_symbol: bool
    password_history_count: int


settings = Settings(
    database_url=os.getenv("DATABASE_URL", f"sqlite:///{BACKEND_DIR / 'users.db'}"),
    secret_key=os.getenv("NEXORA_SECRET_KEY", "local-development-key-change-before-deploying"),
    access_token_minutes=max(1, int(os.getenv("ACCESS_TOKEN_MINUTES", "15"))),
    cors_origins=_csv(os.getenv("CORS_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173")),
    admin_bootstrap_token=os.getenv("ADMIN_BOOTSTRAP_TOKEN", ""),
    environment=os.getenv("APP_ENV", "development").lower(),
    employee_directory_enabled=os.getenv("EMPLOYEE_DIRECTORY_ENABLED", "false").lower() == "true",
    refresh_session_days=max(1, int(os.getenv("REFRESH_SESSION_DAYS", "7"))),
    secure_cookies=os.getenv(
        "COOKIE_SECURE", "true" if os.getenv("APP_ENV", "development").lower() == "production" else "false",
    ).lower() == "true",
    token_issuer=os.getenv("TOKEN_ISSUER", "nexora-workforce"),
    token_audience=os.getenv("TOKEN_AUDIENCE", "nexora-workforce-api"),
    password_min_length=max(8, int(os.getenv("PASSWORD_MIN_LENGTH", "8"))),
    password_require_uppercase=os.getenv("PASSWORD_REQUIRE_UPPERCASE", "false").lower() == "true",
    password_require_lowercase=os.getenv("PASSWORD_REQUIRE_LOWERCASE", "false").lower() == "true",
    password_require_digit=os.getenv("PASSWORD_REQUIRE_DIGIT", "false").lower() == "true",
    password_require_symbol=os.getenv("PASSWORD_REQUIRE_SYMBOL", "false").lower() == "true",
    password_history_count=max(0, int(os.getenv("PASSWORD_HISTORY_COUNT", "0"))),
)

if settings.environment == "production" and (
    settings.secret_key == "local-development-key-change-before-deploying"
    or len(settings.secret_key) < 32
):
    raise RuntimeError("Set NEXORA_SECRET_KEY to a random value of at least 32 characters in production.")
