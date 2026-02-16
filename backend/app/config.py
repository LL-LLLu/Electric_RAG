import os
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
    cors_origins: list = os.environ.get(
        "CORS_ORIGINS", "http://localhost:5173,http://localhost:3000"
    ).split(",")

    class Config:
        env_file = ".env"
        extra = "ignore"


settings = Settings()
