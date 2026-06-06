"""Tests for story prompt generation, run-directory setup, and the
OpenAI client accessor."""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from youtube_shorts_gen.content.story_prompt_gen import generate_dynamic_prompt
from youtube_shorts_gen.utils import openai_client, setup
from youtube_shorts_gen.utils.config import (
    ACTIONS,
    ANIMALS,
    BACKGROUNDS,
    DANCES,
    HUMANS,
)

_PROMPT_MOD = "youtube_shorts_gen.content.story_prompt_gen"
_SETUP_MOD = "youtube_shorts_gen.utils.setup"
_CLIENT_MOD = "youtube_shorts_gen.utils.openai_client"


# --------------------------------------------------------------------------- #
# generate_dynamic_prompt
# --------------------------------------------------------------------------- #
def test_generate_dynamic_prompt_returns_nonempty_str():
    """Happy path: a non-empty string of stable type is returned."""
    result = generate_dynamic_prompt()

    assert isinstance(result, str)
    assert result.strip()


def test_generate_dynamic_prompt_includes_one_element_per_list():
    """The rendered prompt embeds a chosen element from each config list."""
    result = generate_dynamic_prompt()

    assert any(animal in result for animal in ANIMALS)
    assert any(human in result for human in HUMANS)
    assert any(bg in result for bg in BACKGROUNDS)
    assert any(dance in result for dance in DANCES)
    assert any(action in result for action in ACTIONS)


def test_generate_dynamic_prompt_uses_random_choices():
    """random.choice drives selection; patching it fixes the output."""
    with patch(
        f"{_PROMPT_MOD}.random.choice",
        side_effect=lambda seq: seq[0],
    ) as mock_choice:
        result = generate_dynamic_prompt()

    assert mock_choice.call_count == 5
    assert ANIMALS[0] in result
    assert HUMANS[0] in result
    assert BACKGROUNDS[0] in result
    assert DANCES[0] in result
    assert ACTIONS[0] in result


def test_generate_dynamic_prompt_stable_type_across_calls():
    """Type stays str across several independent invocations."""
    results = [generate_dynamic_prompt() for _ in range(5)]

    assert all(isinstance(r, str) and r for r in results)


def test_generate_dynamic_prompt_propagates_choice_errors():
    """Errors from random.choice (e.g. empty sequence) bubble up."""
    with (
        patch(f"{_PROMPT_MOD}.random.choice", side_effect=IndexError("empty")),
        pytest.raises(IndexError),
    ):
        generate_dynamic_prompt()


# --------------------------------------------------------------------------- #
# setup_run_directory
# --------------------------------------------------------------------------- #
def test_setup_run_directory_creates_dir_under_base(tmp_path, monkeypatch):
    """Happy path: a timestamped run dir is created under the base dir."""
    monkeypatch.setattr(setup, "RUNS_BASE_DIR", str(tmp_path))

    run_dir = setup.setup_run_directory()

    assert isinstance(run_dir, Path)
    assert run_dir.exists()
    assert run_dir.is_dir()
    assert run_dir.parent == tmp_path


def test_setup_run_directory_uses_timestamp_name(tmp_path, monkeypatch):
    """The directory name comes from the formatted timestamp."""
    monkeypatch.setattr(setup, "RUNS_BASE_DIR", str(tmp_path))

    fixed = MagicMock()
    fixed.strftime.return_value = "2026-06-05_12-00-00"
    with patch(f"{_SETUP_MOD}.datetime") as mock_dt:
        mock_dt.now.return_value = fixed
        run_dir = setup.setup_run_directory()

    assert run_dir.name == "2026-06-05_12-00-00"
    assert run_dir == tmp_path / "2026-06-05_12-00-00"
    fixed.strftime.assert_called_once_with("%Y-%m-%d_%H-%M-%S")


def test_setup_run_directory_raises_when_dir_exists(tmp_path, monkeypatch):
    """mkdir(parents=True) without exist_ok raises on collision."""
    monkeypatch.setattr(setup, "RUNS_BASE_DIR", str(tmp_path))

    fixed = MagicMock()
    fixed.strftime.return_value = "collision"
    (tmp_path / "collision").mkdir()

    with patch(f"{_SETUP_MOD}.datetime") as mock_dt:
        mock_dt.now.return_value = fixed
        with pytest.raises(FileExistsError):
            setup.setup_run_directory()


# --------------------------------------------------------------------------- #
# get_openai_client
# --------------------------------------------------------------------------- #
def test_get_openai_client_returns_instance(monkeypatch):
    """Happy path: a non-empty key yields an OpenAI client instance."""
    monkeypatch.setattr(openai_client, "OPENAI_API_KEY", "sk-test")
    monkeypatch.setattr(openai_client, "_CLIENT", None)

    sentinel = MagicMock(name="OpenAIInstance")
    fake_openai = MagicMock(return_value=sentinel)
    monkeypatch.setattr(openai_client, "OpenAI", fake_openai)

    client = openai_client.get_openai_client()

    assert client is sentinel
    fake_openai.assert_called_once_with(api_key="sk-test")


def test_get_openai_client_caches_instance(monkeypatch):
    """The client is constructed once and reused on subsequent calls."""
    monkeypatch.setattr(openai_client, "OPENAI_API_KEY", "sk-test")
    monkeypatch.setattr(openai_client, "_CLIENT", None)

    fake_openai = MagicMock()
    monkeypatch.setattr(openai_client, "OpenAI", fake_openai)

    first = openai_client.get_openai_client()
    second = openai_client.get_openai_client()

    assert first is second
    fake_openai.assert_called_once()


def test_get_openai_client_raises_on_empty_key(monkeypatch):
    """Error path: an empty API key raises ValueError before constructing."""
    monkeypatch.setattr(openai_client, "OPENAI_API_KEY", "")
    monkeypatch.setattr(openai_client, "_CLIENT", None)

    fake_openai = MagicMock()
    monkeypatch.setattr(openai_client, "OpenAI", fake_openai)

    with pytest.raises(ValueError, match="OPENAI_API_KEY"):
        openai_client.get_openai_client()

    fake_openai.assert_not_called()
