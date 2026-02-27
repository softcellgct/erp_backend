"""
Application configuration.

All settings are loaded from environment variables (.env file).
Access via: `from core.config import settings`
"""

import os
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # ── Database ──────────────────────────────────────
    database_url: str

    # ── Auth / JWT ────────────────────────────────────
    secret_key: str
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 60

    # ── MinIO / Object Storage ────────────────────────
    minio_endpoint: str
    minio_access_key: str = "minioadmin"
    minio_secret_key: str = "minioadmin"
    minio_secure: bool = False
    minio_bucket: str = "erp"

    # ── CORS ──────────────────────────────────────────
    cors_origins: list[str] = ["*"]

    # ── App ───────────────────────────────────────────
    app_name: str = "ERP Backend"
    debug: bool = False

    class Config:
        env_file = os.path.join(os.path.dirname(__file__), "..", ".env")


settings = Settings()
