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
    service_name: str = "portfolio-core-api"
    database_url: str = "sqlite+aiosqlite:///./data/portfolio_intelligence.db"
    rds_iam_auth: bool = False
    dev_workspace_id: UUID = UUID("00000000-0000-0000-0000-000000000001")
    dev_user_id: UUID = UUID("00000000-0000-0000-0000-000000000002")

    storage_backend: str = "local"
    storage_directory: Path = Path("./data/uploads")
    object_storage_endpoint: str | None = None
    object_storage_region: str = "us-east-1"
    object_storage_bucket: str = "portfolio-intelligence"
    object_storage_access_key: str | None = None
    object_storage_secret_key: str | None = None
    object_storage_kms_key_id: str | None = None
    object_storage_secure: bool = True
    object_storage_presign_seconds: int = Field(default=600, ge=60, le=3_600)
    direct_upload_enabled: bool = True

    max_upload_bytes: int = Field(default=52_428_800, ge=1, le=524_288_000)
    malware_scan_required: bool = False
    clamav_host: str = "localhost"
    clamav_port: int = 3310

    oidc_issuer_url: str | None = None
    oidc_jwks_url: str | None = None
    oidc_client_id: str | None = None
    oidc_client_secret: str | None = None
    oidc_required_scopes: str = "openid"
    identity_propagation_enabled: bool = False
    rls_verification_complete: bool = False
    telemetry_redaction_verified: bool = False
    session_secret: str | None = None
    field_encryption_key: str | None = None
    kms_data_key_id: str | None = None
    kms_capability_signing_key_id: str | None = None
    agent_core_shared_secret: str | None = None

    aws_region: str = "ap-south-1"
    job_queue_url: str | None = None
    audit_queue_url: str | None = None
    redis_url: str | None = None
    otel_exporter_otlp_endpoint: str | None = None
    allowed_origins: str = "http://localhost:3000"
    idempotency_retention_hours: int = Field(default=24, ge=24, le=168)
    step_up_max_age_seconds: int = Field(default=300, ge=60, le=900)

    @property
    def is_production(self) -> bool:
        return self.app_env.lower() == "production"

    @property
    def requires_oidc(self) -> bool:
        return self.app_env.lower() in {"staging", "production"}

    @property
    def cors_origins(self) -> list[str]:
        return [origin.strip() for origin in self.allowed_origins.split(",") if origin.strip()]

    @model_validator(mode="after")
    def production_must_fail_closed(self) -> Settings:
        if self.requires_oidc:
            missing: list[str] = []
            if not self.oidc_issuer_url:
                missing.append("OIDC_ISSUER_URL")
            if not self.oidc_client_id:
                missing.append("OIDC_CLIENT_ID")
            if not self.field_encryption_key and not self.kms_data_key_id:
                missing.append("FIELD_ENCRYPTION_KEY or KMS_DATA_KEY_ID")
            if not self.malware_scan_required:
                missing.append("MALWARE_SCAN_REQUIRED=true")
            if self.database_url.startswith("sqlite"):
                missing.append("production PostgreSQL DATABASE_URL")
            if not self.rds_iam_auth:
                missing.append("RDS_IAM_AUTH=true")
            if self.storage_backend.lower() != "s3":
                missing.append("STORAGE_BACKEND=s3")
            if not self.object_storage_secure:
                missing.append("OBJECT_STORAGE_SECURE=true")
            if not self.object_storage_kms_key_id:
                missing.append("OBJECT_STORAGE_KMS_KEY_ID")
            if self.direct_upload_enabled:
                missing.append("DIRECT_UPLOAD_ENABLED=false")
            if not self.identity_propagation_enabled:
                missing.append("IDENTITY_PROPAGATION_ENABLED=true")
            if not self.rls_verification_complete:
                missing.append("RLS_VERIFICATION_COMPLETE=true")
            if not self.telemetry_redaction_verified:
                missing.append("TELEMETRY_REDACTION_VERIFIED=true")
            if not self.otel_exporter_otlp_endpoint:
                missing.append("OTEL_EXPORTER_OTLP_ENDPOINT")
            if not self.agent_core_shared_secret:
                missing.append("AGENT_CORE_SHARED_SECRET")
            if not self.job_queue_url:
                missing.append("JOB_QUEUE_URL")
            if not self.audit_queue_url:
                missing.append("AUDIT_QUEUE_URL")
            if not all(origin.startswith("https://") for origin in self.cors_origins):
                missing.append("HTTPS-only ALLOWED_ORIGINS")
            if missing:
                raise ValueError("Production configuration is incomplete: " + ", ".join(missing))
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
