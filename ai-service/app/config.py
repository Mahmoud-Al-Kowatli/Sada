from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_prefix="SADA_AI_", extra="ignore")

    service_name: str = "Sada AI"
    scratch_dir: str = "./var/scratch"
    assessments_db: str = "sqlite:///./var/assessments.db"

    # audio contract
    target_sample_rate: int = 16000
    window_seconds: float = 4.0
    hop_seconds: float = 3.0  # 1 s overlap
    min_valid_seconds: float = 3.0
    max_seconds: float = 60.0
    max_silence_ratio: float = 0.85
    max_clipping_ratio: float = 0.02
    silence_rms_db: float = -45.0

    # classifier: "stub" (no weights needed) | "lfcc_resnet18" (needs torch + checkpoint)
    classifier: str = "stub"
    checkpoint_path: str = "./models/lfcc_resnet18.pt"
    model_version: str = "stub-0.1"
    threshold: float = 0.65  # calibrated on the Arabic dev set; overridable per deployment


@lru_cache
def get_settings() -> Settings:
    return Settings()
