import pytest

from app import config


@pytest.fixture(autouse=True)
def no_backup_model_by_default(monkeypatch):
    """Tests never reach the real OpenRouter: the key in a developer's .env is ignored unless a test sets one."""
    monkeypatch.setattr(config, "OPENROUTER_API_KEY", "")
