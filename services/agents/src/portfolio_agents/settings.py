from __future__ import annotations

from functools import lru_cache

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class AgentSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    app_env: str = "development"
    core_api_url: str = "http://localhost:8000"
    agent_core_shared_secret: str | None = None
    dev_workspace_id: str = "00000000-0000-0000-0000-000000000001"
    openai_api_key: str | None = None
    openai_model: str | None = None
    postgres_checkpoint_dsn: str | None = None
    rds_iam_auth: bool = False
    aws_region: str = "ap-south-1"
    oidc_issuer_url: str | None = None
    oidc_client_id: str | None = None
    identity_propagation_enabled: bool = False
    agent_evaluation_verified: bool = False
    agent_max_steps: int = Field(default=16, ge=1, le=30)
    agent_max_tool_calls: int = Field(default=12, ge=1, le=50)
    agent_timeout_seconds: int = Field(default=300, ge=5, le=900)
    agent_max_cost_usd: float = Field(default=1.0, ge=0.01, le=100)

    @property
    def is_production(self) -> bool:
        return self.app_env.lower() == "production"

    @property
    def requires_oidc(self) -> bool:
        return self.app_env.lower() in {"staging", "production"}

    @property
    def live_model_enabled(self) -> bool:
        return bool(self.openai_api_key and self.openai_model)

    @model_validator(mode="after")
    def validate_production(self) -> AgentSettings:
        if self.requires_oidc:
            missing: list[str] = []
            if not self.openai_api_key:
                missing.append("OPENAI_API_KEY")
            if not self.openai_model:
                missing.append("OPENAI_MODEL")
            if not self.postgres_checkpoint_dsn:
                missing.append("POSTGRES_CHECKPOINT_DSN")
            if not self.rds_iam_auth:
                missing.append("RDS_IAM_AUTH=true")
            if not self.oidc_issuer_url:
                missing.append("OIDC_ISSUER_URL")
            if not self.oidc_client_id:
                missing.append("OIDC_CLIENT_ID")
            if not self.identity_propagation_enabled:
                missing.append("IDENTITY_PROPAGATION_ENABLED=true")
            if not self.agent_evaluation_verified:
                missing.append("AGENT_EVALUATION_VERIFIED=true")
            if not self.agent_core_shared_secret:
                missing.append("AGENT_CORE_SHARED_SECRET")
            if missing:
                raise ValueError(
                    "Production agent configuration is incomplete: " + ", ".join(missing)
                )
        return self


@lru_cache
def get_agent_settings() -> AgentSettings:
    return AgentSettings()
