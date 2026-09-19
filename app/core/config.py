from functools import lru_cache
from pathlib import Path

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )

    PROJECT_NAME: str = "Abeokuta Smart Tourism Guide System API"
    API_V1_PREFIX: str = "/api/v1"
    ENVIRONMENT: str = "development"

    DATA_DIR: str = "./data"
    DATABASE_URL: str = ""
    SQL_ECHO: bool = False

    SECRET_KEY: str = "change-me-to-a-long-random-string"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    CORS_ORIGINS: str = "http://localhost:3000,http://localhost:5173"
    SEED_ON_STARTUP: bool = True
    DOCS_ENABLED: bool = True

    DEMO_USER_PASSWORD: str = "abeokuta2026"
    ADMIN_EMAIL: str = ""
    ADMIN_PASSWORD: str = ""
    ADMIN_NAME: str = "Admin"
    DEFAULT_SLOT_CAPACITY: int = 40
    MAX_VISITORS_PER_BOOKING: int = 20
    MAX_BOOKING_DAYS_AHEAD: int = 90

    WALKING_SPEED_KMH: float = 4.8
    DRIVING_SPEED_KMH: float = 22.0
    DETOUR_FACTOR: float = 1.25

    @field_validator("ENVIRONMENT")
    @classmethod
    def _lower(cls, v: str) -> str:
        return v.strip().lower()

    @property
    def is_production(self) -> bool:
        return self.ENVIRONMENT in {"production", "prod"}

    @property
    def cors_origins_list(self) -> list[str]:
        return [o.strip() for o in self.CORS_ORIGINS.split(",") if o.strip()]

    @property
    def database_url(self) -> str:
        """Fall back to a file inside DATA_DIR when DATABASE_URL is not set.

        Note the four-slash form for absolute paths: sqlite:////data/x.db.
        Three slashes means a path relative to the working directory.
        """
        if self.DATABASE_URL:
            return self.DATABASE_URL
        path = Path(self.DATA_DIR).resolve() / "abeokuta.db"
        return f"sqlite:///{path}"

    @property
    def sqlite_path(self) -> Path | None:
        url = self.database_url
        if not url.startswith("sqlite"):
            return None
        raw = url.split("sqlite:///")[-1]
        return Path(raw) if raw and raw != ":memory:" else None


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
