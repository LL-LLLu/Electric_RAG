import os
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    environment: str = os.environ.get("ENVIRONMENT", "development")
    debug: bool = environment == "development"

    database_url: str = os.environ.get("DATABASE_URL", "")

    anthropic_api_key: str = os.environ.get("ANTHROPIC_API_KEY", "")

    upload_dir: str = os.environ.get("UPLOAD_DIR", "/app/uploads")
    max_upload_size: int = 1024 * 1024 * 1024  # 1GB

    cors_origins: list = ["*"]

    class Config:
        env_file = ".env"


settings = Settings()
