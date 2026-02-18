import os
from typing import List
from pydantic import field_validator
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    environment: str = os.environ.get("ENVIRONMENT", "development")
    debug: bool = environment == "development"

    database_url: str = os.environ.get("DATABASE_URL", "")

    anthropic_api_key: str = os.environ.get("ANTHROPIC_API_KEY", "")

    upload_dir: str = os.environ.get("UPLOAD_DIR", "/app/uploads")
    max_upload_size: int = 1024 * 1024 * 1024  # 1GB

    # Authentication - API key for protecting endpoints
    api_secret_key: str = os.environ.get("API_SECRET_KEY", "")

    # CORS - restrict in production, allow all in development
    cors_origins: List[str] = ["http://localhost:5173", "http://localhost:3000"]

    @field_validator("cors_origins", mode="before")
    @classmethod
    def parse_cors_origins(cls, v):
        """Accept both comma-separated strings and JSON arrays"""
        if isinstance(v, str):
            return [origin.strip() for origin in v.split(",") if origin.strip()]
        return v

    model_config = {
        "env_file": ".env",
        "extra": "ignore",
        "protected_namespaces": (),
    }


settings = Settings()
