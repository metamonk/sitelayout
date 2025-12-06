from typing import List, Union

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


def parse_cors(v: Union[str, List[str]]) -> List[str]:
    """Parse CORS origins from string or list."""
    if isinstance(v, str) and v:
        return [origin.strip() for origin in v.split(",") if origin.strip()]
    elif isinstance(v, list):
        return v
    return []


class Settings(BaseSettings):
    # Project
    PROJECT_NAME: str = "Site Layout API"
    VERSION: str = "0.1.0"
    API_V1_STR: str = "/api/v1"

    # CORS - accepts comma-separated string or JSON array from env
    ALLOWED_ORIGINS: Union[str, List[str]] = (
        "http://localhost:3000,http://localhost:8000"
    )

    @field_validator("ALLOWED_ORIGINS", mode="before")
    @classmethod
    def parse_allowed_origins(cls, v: Union[str, List[str]]) -> List[str]:
        return parse_cors(v)

    # Database
    DATABASE_URL: str = "postgresql://user:password@localhost:5432/sitelayout"

    # Authentication
    SECRET_KEY: str = "your-secret-key-change-in-production"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 7  # 7 days

    # Google OAuth (optional)
    GOOGLE_CLIENT_ID: str = ""
    GOOGLE_CLIENT_SECRET: str = ""

    # File uploads
    MAX_UPLOAD_SIZE: int = 50 * 1024 * 1024  # 50MB
    UPLOAD_DIR: str = "./uploads"

    # Environment
    ENVIRONMENT: str = "development"
    DEBUG: bool = True

    model_config = SettingsConfigDict(
        env_file=".env", case_sensitive=True, extra="allow"
    )


settings = Settings()
