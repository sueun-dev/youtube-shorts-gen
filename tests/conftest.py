"""
Test configuration file for pytest.

This file sets up the test environment and provides fixtures that can be
reused across tests.
"""

import os
import sys
from pathlib import Path

import pytest

# Add the project root to sys.path to allow importing from the package
sys.path.insert(0, str(Path(__file__).parent.parent))


# Create a fixture for temporary test directories
@pytest.fixture
def test_run_dir():
    """Create a temporary test directory for each test."""
    test_dir = "test_runs/temp_test_dir"
    os.makedirs(test_dir, exist_ok=True)
    yield test_dir
    # We don't actually clean up for safety, but we could in a real scenario


# Mock OpenAI client fixture
@pytest.fixture
def mock_openai_client(monkeypatch):
    """Creates a mock OpenAI client for testing."""
    from unittest.mock import MagicMock

    mock_client = MagicMock()

    # Configure chat completions
    mock_response = MagicMock()
    mock_response.choices = [MagicMock()]
    mock_response.choices[0].message.content = "Test story content"
    mock_client.chat.completions.create.return_value = mock_response

    # Configure image generation
    mock_data = MagicMock()
    # Simple base64 encoded 1x1 transparent PNG image
    mock_data.b64_json = (
        "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmM"
        "IQAAAABJRU5ErkJggg=="
    )
    mock_image_response = MagicMock()
    mock_image_response.data = [mock_data]
    mock_client.images.generate.return_value = mock_image_response

    # Mock the OpenAI client constructor
    class MockOpenAI:
        def __init__(self, *args, **kwargs):
            pass

        def __new__(cls, *args, **kwargs):
            return mock_client

    # Apply the monkeypatch
    monkeypatch.setattr("youtube_shorts_gen.youtube_script_gen.OpenAI", MockOpenAI)

    return mock_client


# Create a fixture for environment variables
@pytest.fixture
def mock_env_vars(monkeypatch):
    """Set up mock environment variables for testing."""
    monkeypatch.setenv("OPENAI_API_KEY", "test_api_key")
    monkeypatch.setenv("RUNWAY_API_KEY", "test_runway_key")
