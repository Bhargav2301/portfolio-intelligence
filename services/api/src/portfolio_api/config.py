from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from uuid import UUID

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    app_env: str = "development"
    log_level: str = "INFO"
    database_url: str = "sqlite+aiosqlite:///./data/portfolio_intelligence.db"
    dev_workspace_id: UUID = UUID("00000000-0000-0000-0000-000000000001")
    dev_user_id: UUID = UUID("00000000-0000-0000-0000-000000000002")

    storage_backend: str = "local"
    storage_directory: Path = Path("./data/uploads")
    object_storage_endpoint: str | None = None
    object_storage_region: str = "us-east-1"
    object_storage_bucket: str = "portfolio-intelligence"
    object_storage_access_key: str | None = None
    object_storage_secret_key: str | None = None
    object_storage_secure: bool = True

    max_upload_bytes: int = Field(default=52_428_800, ge=1, le=524_288_000)
    malware_scan_required: bool = False
    clamav_host: str = "localhost"
    clamav_port: int = 3310

    oidc_issuer_url: str | None = None
    oidc_client_id: str | None = None
    oidc_client_secret: str | None = None
    field_encryption_key: str | None = None

    @property
    def is_production(self) -> bool:
        return self.app_env.lower() == "production"

    @model_validator(mode="after")
    def production_must_fail_closed(self) -> "Settings":
        if self.is_production:
            missing: list[str] = []
            if not self.oidc_issuer_url:
                missing.append("OIDC_ISSUER_URL")
            if not self.oidc_client_id:
                missing.append("OIDC_CLIENT_ID")
            if not self.oidc_client_secret:
                missing.append("OIDC_CLIENT_SECRET")
            if not self.field_encryption_key:
                missing.append("FIELD_ENCRYPTION_KEY")
            if not self.malware_scan_required:
                missing.append("MALWARE_SCAN_REQUIRED=true")
            if self.database_url.startswith("sqlite"):
                missing.append("production PostgreSQL DATABASE_URL")
            if self.storage_backend.lower() != "s3":
                missing.append("STORAGE_BACKEND=s3")
            if not self.object_storage_endpoint:
                missing.append("OBJECT_STORAGE_ENDPOINT")
            if not self.object_storage_access_key:
                missing.append("OBJECT_STORAGE_ACCESS_KEY")
            if not self.object_storage_secret_key:
                missing.append("OBJECT_STORAGE_SECRET_KEY")
            if not self.object_storage_secure:
                missing.append("OBJECT_STORAGE_SECURE=true")
            if missing:
                raise ValueError("Production configuration is incomplete: " + ", ".join(missing))
            raise ValueError(
                "Production mode is disabled until OIDC membership enforcement and the "
                "production security test gate are implemented."
            )
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
