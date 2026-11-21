"""Application settings. Every value can be overridden with an environment variable
(or a .env file next to the backend). Nothing secret is hard-coded for production:
the defaults below are development conveniences only."""
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_prefix="SADA_", extra="ignore")

    app_name: str = "Sada Platform API"
    environment: str = "development"  # development | test | production
    debug: bool = True

    # Persistence
    database_url: str = "postgresql+psycopg://sada:sada@localhost:5432/sada"
    redis_url: str = "redis://localhost:6379/0"

    # Auth
    jwt_secret: str = "dev-only-secret-change-me-before-any-deployment-0123456789"
    jwt_algorithm: str = "HS256"
    access_token_minutes: int = 60

    # OTP (simulated in the prototype: the code is returned by the API in dev/test)
    otp_ttl_seconds: int = 300
    otp_dev_echo: bool = True

    # Sada AI service
    ai_service_url: str = "http://localhost:8100"
    ai_timeout_seconds: float = 8.0

    # Audio upload constraints (UC-02)
    audio_max_bytes: int = 10 * 1024 * 1024
    audio_allowed_formats: tuple[str, ...] = ("wav", "flac")

    # Evidence (retained review copies) storage
    evidence_dir: str = "./var/evidence"

    # CORS
    cors_origins: tuple[str, ...] = ("http://localhost:5173", "http://127.0.0.1:5173")


@lru_cache
def get_settings() -> Settings:
    return Settings()
