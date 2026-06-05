"""AstraOS API — Core Configuration."""

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

# ── Single canonical path for all ML artefacts ──────────────────────────────
# apps/api/src/core/config.py → parent×3 = apps/api/
ML_MODEL_DIR: Path = Path(__file__).parent.parent.parent / "data" / "models"
ML_MODEL_DIR.mkdir(parents=True, exist_ok=True)


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # App
    app_name: str = "AstraOS"
    app_env: str = "development"
    app_debug: bool = True

    # Database
    database_url: str = "postgresql+asyncpg://astraos:astraos_dev@localhost:5432/astraos"
    database_url_sync: str = "postgresql://astraos:astraos_dev@localhost:5432/astraos"

    # Redis
    redis_url: str = "redis://localhost:6379/0"

    # JWT
    jwt_secret_key: str = "CHANGE_ME_TO_A_RANDOM_64_CHAR_STRING"
    jwt_algorithm: str = "HS256"
    jwt_access_token_expire_minutes: int = 15
    jwt_refresh_token_expire_days: int = 7

    # Broker Key Encryption (independent of JWT)
    broker_encryption_key: str = ""

    # Security
    enforce_https: bool = False  # Set True in production
    login_max_attempts: int = 5
    login_lockout_minutes: int = 15

    # LLM
    gemini_api_key: str = ""
    llm_provider: str = "gemini_free"
    openai_api_key: str = ""

    # Providers (free defaults)
    market_data_provider: str = "yfinance"
    broker_provider: str = "paper"
    news_provider: str = "rss_gdelt"

    # Angel One SmartAPI (FREE real-time NSE data)
    angel_api_key: str = ""
    angel_client_id: str = ""
    angel_password: str = ""
    angel_totp_secret: str = ""

    # Zerodha Kite Connect (premium, Rs 2000/month)
    kite_api_key: str = ""
    kite_api_secret: str = ""
    kite_access_token: str = ""

    # Alerts — Telegram
    telegram_bot_token: str = ""
    telegram_chat_id: str = ""

    # Alerts — WhatsApp (Twilio API)
    whatsapp_account_sid: str = ""
    whatsapp_auth_token: str = ""
    whatsapp_from_number: str = ""  # e.g. "whatsapp:+14155238886"

    # Alerts — Email / SMTP
    smtp_host: str = "smtp.gmail.com"
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_password: str = ""
    alert_email_from: str = ""
    alert_email_to: str = ""

    # Google OAuth
    google_client_id: str = ""
    google_client_secret: str = ""

    # CORS
    cors_origins: str = "http://localhost:3000"

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",")]

    model_config = SettingsConfigDict(
        env_file="../../.env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )


@lru_cache
def get_settings() -> Settings:
    s = Settings()

    # Security validation — refuse to start in production with insecure defaults
    if s.app_env == "production":
        if s.jwt_secret_key == "CHANGE_ME_TO_A_RANDOM_64_CHAR_STRING":
            raise ValueError("FATAL: JWT_SECRET_KEY must be changed for production")
        if len(s.jwt_secret_key) < 32:
            raise ValueError("FATAL: JWT_SECRET_KEY must be at least 32 characters")
        if not s.enforce_https:
            import warnings
            warnings.warn("ENFORCE_HTTPS is False in production — HTTPS is strongly recommended", stacklevel=2)
        if s.app_debug:
            raise ValueError("FATAL: APP_DEBUG must be False in production")

    return s


settings = get_settings()
