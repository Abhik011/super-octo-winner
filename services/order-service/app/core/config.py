from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    APP_NAME: str = "Order Service"
    APP_ENV: str = "development"
    DEBUG: bool = False

    DATABASE_URL: str
    DB_ECHO: bool = False

    JWT_SECRET_KEY: str
    JWT_ALGORITHM: str = "HS256"

    IDENTITY_SERVICE_URL: str = "http://127.0.0.1:8001"
    CATALOG_SERVICE_URL: str = "http://127.0.0.1:8002"
    CART_SERVICE_URL: str = "http://127.0.0.1:8004"
    INVENTORY_SERVICE_URL: str = "http://127.0.0.1:8003"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


settings = Settings()