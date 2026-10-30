from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "PharmaVerse AI"
    app_version: str = "0.1.0"
    debug: bool = True

    database_url: str = (
        "postgresql+psycopg://postgres:postgres@localhost:5432/pharmaverse"
    )

    jwt_secret: str = "CHANGE_THIS_SECRET"
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 60

    cors_origins: str = "http://localhost:5173"

    fabric_enabled: bool = False
    fabric_gateway_url: str = ""
    fabric_gateway_secret: str = ""
    fabric_gateway_timeout: float = 5.0

    pharmaverse_ml_artifact: str | None = None

    # ------------------------------------------------------------------ #
    # Live FDA / openFDA configuration                                     #
    # ------------------------------------------------------------------ #
    # Timeout in seconds for each outbound openFDA HTTP request.
    # Keep this low: a slow FDA response must not block the FastAPI worker.
    fda_api_timeout_seconds: float = 8.0

    # How long (seconds) to keep a cached FDA response before re-fetching.
    # openFDA NDC and Drug Shortages are updated daily; enforcement weekly.
    # A conservative default of 3 600 s (1 hour) avoids hammering FDA while
    # still reflecting the same-day update cadence for the daily sources.
    fda_cache_ttl_seconds: float = 3600.0

    @field_validator("debug", mode="before")
    @classmethod
    def _parse_debug(cls, value: object) -> bool:
        if isinstance(value, bool):
            return value
        if isinstance(value, str):
            normalized = value.strip().lower()
            if normalized in ("true", "1", "yes", "on", "t", "dev", "development"):
                return True
            if normalized in ("false", "0", "no", "off", "f", "release", "prod", "production"):
                return False
        return bool(value)

    model_config = SettingsConfigDict(
        env_file=".env",
        extra="ignore"
    )


settings = Settings()