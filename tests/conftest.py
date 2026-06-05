"""Shared pytest fixtures for the test suite."""

import sys
from pathlib import Path
from unittest.mock import MagicMock

import pytest

# Allow importing the package when tests are run from any working directory.
sys.path.insert(0, str(Path(__file__).parent.parent))

# A 1x1 transparent PNG, base64-encoded, reused by image-generation mocks.
TEST_IMAGE_B64 = (
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmM"
    "IQAAAABJRU5ErkJggg=="
)


@pytest.fixture
def test_run_dir(tmp_path):
    """Return a fresh per-test run directory (auto-cleaned by pytest)."""
    return str(tmp_path)


@pytest.fixture
def mock_openai_client():
    """A MagicMock OpenAI client with chat and image responses configured."""
    client = MagicMock()

    chat_response = MagicMock()
    chat_response.choices = [MagicMock()]
    chat_response.choices[0].message.content = "Test story content"
    client.chat.completions.create.return_value = chat_response

    image_data = MagicMock()
    image_data.b64_json = TEST_IMAGE_B64
    image_response = MagicMock()
    image_response.data = [image_data]
    client.images.generate.return_value = image_response

    return client


@pytest.fixture
def mock_env_vars(monkeypatch):
    """Set placeholder API keys in the environment for the duration of a test."""
    monkeypatch.setenv("OPENAI_API_KEY", "test_api_key")
    monkeypatch.setenv("RUNWAY_API_KEY", "test_runway_key")
    monkeypatch.setenv("ELEVENLABS_API_KEY", "test_elevenlabs_key")
