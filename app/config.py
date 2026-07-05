from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file='.env', env_file_encoding='utf-8')

    DATABASE_PATH: str = "data/lyrics.db"
    API_KEYS_ENABLED: bool = True
    RATE_LIMIT_RPM: int = 60
    LOG_LEVEL: str = "INFO"
    CORS_ORIGINS: str = ""
    HOST: str = "127.0.0.1"
    PORT: int = 8000
    METRICS_ENABLED: bool = True
    HSTS_ENABLED: bool = False


@lru_cache
def get_settings() -> Settings:
    return Settings()


def is_insecure() -> bool:
    s = get_settings()
    host_nonlocal = s.HOST not in ("127.0.0.1", "localhost", "::1")
    return not s.API_KEYS_ENABLED and host_nonlocal