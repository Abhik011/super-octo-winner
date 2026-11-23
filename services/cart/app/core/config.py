from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

ENV_FILE = Path(__file__).resolve().parents[2] / ".env"


class Settings(BaseSettings):
    APP_NAME: str = "Ecommerce Cart Service"
    API_VERSION: str = "v1"

    DATABASE_URL: str
    REDIS_URL: str = "redis://localhost:6379/3"

    CATALOG_SERVICE_URL: str = "http://127.0.0.1:8002"

    JWT_SECRET_KEY: str
    JWT_ALGORITHM: str = "HS256"
    
    model_config = SettingsConfigDict(
        env_file=ENV_FILE,
        env_file_encoding="utf-8",
        extra="ignore",
    )


settings = Settings()
