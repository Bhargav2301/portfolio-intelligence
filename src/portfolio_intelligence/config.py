from __future__ import annotations

import os
from dataclasses import dataclass


def _as_bool(value: str) -> bool:
    return value.strip().lower() in {"1", "true", "yes", "on"}


@dataclass(frozen=True, slots=True)
class Settings:
    environment: str = "development"
    log_level: str = "INFO"
    database_url: str = "postgresql://portfolio:portfolio@localhost:5432/portfolio_intelligence"
    evidence_max_age_seconds: int = 86_400
    market_data_max_age_seconds: int = 900
    allow_personalized_advice: bool = False

    @classmethod
    def from_environment(cls) -> Settings:
        defaults = cls()
        return cls(
            environment=os.getenv("PI_ENVIRONMENT", defaults.environment),
            log_level=os.getenv("PI_LOG_LEVEL", defaults.log_level),
            database_url=os.getenv("PI_DATABASE_URL", defaults.database_url),
            evidence_max_age_seconds=int(
                os.getenv("PI_EVIDENCE_MAX_AGE_SECONDS", str(defaults.evidence_max_age_seconds))
            ),
            market_data_max_age_seconds=int(
                os.getenv(
                    "PI_MARKET_DATA_MAX_AGE_SECONDS",
                    str(defaults.market_data_max_age_seconds),
                )
            ),
            allow_personalized_advice=_as_bool(
                os.getenv("PI_ALLOW_PERSONALIZED_ADVICE", "false")
            ),
        )
