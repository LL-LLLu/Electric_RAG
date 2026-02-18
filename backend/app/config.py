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

    # CORS - stored as comma-separated string, accessed via cors_origins_list
    cors_origins: str = "http://localhost:5173,http://localhost:3000"

    @property
    def cors_origins_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]

    model_config = {
        "env_file": ".env",
        "extra": "ignore",
        "protected_namespaces": (),
    }


settings = Settings()
