import os
from unittest.mock import patch

from app.config import Settings, get_settings, is_insecure


def test_defaults():
    s = Settings()
    assert s.DATABASE_PATH == "data/lyrics.db"
    assert s.API_KEYS_ENABLED is True
    assert s.RATE_LIMIT_RPM == 60
    assert s.LOG_LEVEL == "INFO"
    assert s.CORS_ORIGINS == ""
    assert s.HOST == "127.0.0.1"
    assert s.PORT == 8000


def test_env_overrides():
    with patch.dict(os.environ, {"HOST": "0.0.0.0", "PORT": "9000", "API_KEYS_ENABLED": "false"}, clear=False):
        get_settings.cache_clear()
        s = get_settings()
        assert s.HOST == "0.0.0.0"
        assert s.PORT == 9000
        assert s.API_KEYS_ENABLED is False
    get_settings.cache_clear()


def test_is_insecure_remote_no_key():
    with patch("app.config.get_settings") as mock:
        mock.return_value = Settings(HOST="0.0.0.0", API_KEYS_ENABLED=False)
        assert is_insecure() is True


def test_is_insecure_localhost_no_key():
    with patch("app.config.get_settings") as mock:
        mock.return_value = Settings(HOST="127.0.0.1", API_KEYS_ENABLED=False)
        assert is_insecure() is False


def test_is_insecure_remote_with_key():
    with patch("app.config.get_settings") as mock:
        mock.return_value = Settings(HOST="0.0.0.0", API_KEYS_ENABLED=True)
        assert is_insecure() is False