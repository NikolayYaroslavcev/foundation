from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_host: str = "0.0.0.0"
    app_port: int = 8000

    database_url: str

    postgres_user: str = "foundation"
    postgres_password: str = "foundation"
    postgres_db: str = "foundation"
    postgres_host: str = "db"
    postgres_port: int = 5432


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
