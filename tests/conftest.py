"""Shared pytest fixtures for the app's flat-module imports."""

import sys
from pathlib import Path

import pytest

APP_DIR = Path(__file__).resolve().parents[1] / "app"
if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))

from app.config import AppConfig


@pytest.fixture
def sample_config() -> AppConfig:
    return AppConfig(
        api_key="sk-test-key-123456",
        base_url="https://api.example.com",
        model="test-model",
    )


@pytest.fixture
def sample_messages() -> list[dict[str, str]]:
    return [
        {"role": "system", "content": "You are a helpful assistant."},
        {"role": "user", "content": "Test prompt"},
    ]
