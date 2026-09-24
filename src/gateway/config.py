from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql+asyncpg://gateway:gateway@localhost:5433/ai_gateway"
    redis_url: str = "redis://localhost:6379/0"
    environment: str = "local"
    log_level: str = "INFO"
    # JWT signing key for the Control API. Override in .env for anything beyond local dev.
    secret_key: str = "change-me-in-production"


settings = Settings()
