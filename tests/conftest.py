import pytest
from fastapi.testclient import TestClient

from app.config import load_settings
from app.main import create_app


@pytest.fixture()
def settings(tmp_path):
    return load_settings(llm_provider="offline", gemini_api_key=None, retriever="tfidf",
                         rate_limit_per_minute=3, log_path=tmp_path / "requests.jsonl")


@pytest.fixture()
def client(settings):
    return TestClient(create_app(settings))
