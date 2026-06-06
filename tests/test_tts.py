"""Tests for the TTSGenerator and ParagraphTTS text-to-speech modules."""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from youtube_shorts_gen.media.paragraph_tts import ParagraphTTS
from youtube_shorts_gen.media.tts_generator import TTSGenerator
from youtube_shorts_gen.utils.config import (
    STORY_AUDIO_FILENAME,
    STORY_PROMPT_FILENAME,
)


def _make_client(chunks):
    """Return a MagicMock ElevenLabs client whose convert yields chunks."""
    client = MagicMock()
    client.text_to_speech.convert.return_value = iter(chunks)
    return client


# --------------------------------------------------------------------------- #
# TTSGenerator
# --------------------------------------------------------------------------- #
def test_generate_from_text_writes_mp3(tmp_path, monkeypatch):
    """generate_from_text writes joined byte chunks and returns the path."""
    monkeypatch.setenv("ELEVENLABS_API_KEY", "k")
    client = _make_client([b"aa", b"bb"])

    with patch(
        "youtube_shorts_gen.media.tts_generator.ElevenLabs",
        return_value=client,
    ) as mock_eleven:
        gen = TTSGenerator(str(tmp_path))
        result = gen.generate_from_text("hello world")

    expected = tmp_path / STORY_AUDIO_FILENAME
    assert result == str(expected)
    assert expected.exists()
    assert expected.read_bytes() == b"aabb"
    mock_eleven.assert_called_once_with(api_key="k")
    # The text we passed is forwarded to the API.
    _, kwargs = client.text_to_speech.convert.call_args
    assert kwargs["text"] == "hello world"


def test_generate_from_text_missing_api_key_raises(tmp_path, monkeypatch):
    """Missing ELEVENLABS_API_KEY raises OSError and writes no file."""
    monkeypatch.delenv("ELEVENLABS_API_KEY", raising=False)

    with patch("youtube_shorts_gen.media.tts_generator.ElevenLabs") as mock_eleven:
        gen = TTSGenerator(str(tmp_path))
        with pytest.raises(OSError, match="ELEVENLABS_API_KEY"):
            gen.generate_from_text("hello")

    mock_eleven.assert_not_called()
    assert not (tmp_path / STORY_AUDIO_FILENAME).exists()


def test_generate_from_file_missing_story_raises(tmp_path, monkeypatch):
    """generate_from_file raises FileNotFoundError when the story is absent."""
    monkeypatch.setenv("ELEVENLABS_API_KEY", "k")

    with patch("youtube_shorts_gen.media.tts_generator.ElevenLabs") as mock_eleven:
        gen = TTSGenerator(str(tmp_path))
        with pytest.raises(FileNotFoundError, match=STORY_PROMPT_FILENAME):
            gen.generate_from_file()

    mock_eleven.assert_not_called()


def test_generate_from_file_reads_and_synthesizes(tmp_path, monkeypatch):
    """generate_from_file reads the story file then synthesizes its text."""
    monkeypatch.setenv("ELEVENLABS_API_KEY", "k")
    prompt = tmp_path / STORY_PROMPT_FILENAME
    prompt.write_text("  once upon a time  ", encoding="utf-8")
    client = _make_client([b"xx", b"yy"])

    with patch(
        "youtube_shorts_gen.media.tts_generator.ElevenLabs",
        return_value=client,
    ):
        gen = TTSGenerator(str(tmp_path))
        result = gen.generate_from_file()

    expected = tmp_path / STORY_AUDIO_FILENAME
    assert result == str(expected)
    assert Path(result).read_bytes() == b"xxyy"
    # The file content is stripped before being sent to the API.
    _, kwargs = client.text_to_speech.convert.call_args
    assert kwargs["text"] == "once upon a time"


# --------------------------------------------------------------------------- #
# ParagraphTTS
# --------------------------------------------------------------------------- #
def test_init_creates_audio_dir(tmp_path):
    """Constructing ParagraphTTS creates the paragraph_audio directory."""
    tts = ParagraphTTS(str(tmp_path))
    assert tts.audio_dir == tmp_path / "paragraph_audio"
    assert tts.audio_dir.is_dir()


def test_generate_for_paragraphs_writes_all(tmp_path, monkeypatch):
    """generate_for_paragraphs returns a path per paragraph with byte content."""
    monkeypatch.setenv("ELEVENLABS_API_KEY", "k")
    client = _make_client([b"aa", b"bb"])
    client.text_to_speech.convert.side_effect = lambda **_: iter([b"aa", b"bb"])

    with patch(
        "youtube_shorts_gen.media.paragraph_tts.ElevenLabs",
        return_value=client,
    ):
        tts = ParagraphTTS(str(tmp_path))
        paths = tts.generate_for_paragraphs(["first", "second"])

    assert paths == [
        str(tmp_path / "paragraph_audio" / "paragraph_1.mp3"),
        str(tmp_path / "paragraph_audio" / "paragraph_2.mp3"),
    ]
    for path in paths:
        assert Path(path).read_bytes() == b"aabb"


def test_generate_for_paragraphs_aligns_failures_as_empty(
    tmp_path, monkeypatch, caplog
):
    """A failed paragraph is logged and kept as "" so results stay aligned."""
    monkeypatch.setenv("ELEVENLABS_API_KEY", "k")
    client = MagicMock()

    def _convert(**_):
        if client.text_to_speech.convert.call_count == 1:
            return iter([b"ok"])
        raise RuntimeError("boom")

    client.text_to_speech.convert.side_effect = _convert

    with (
        patch(
            "youtube_shorts_gen.media.paragraph_tts.ElevenLabs",
            return_value=client,
        ),
        caplog.at_level("ERROR"),
    ):
        tts = ParagraphTTS(str(tmp_path))
        paths = tts.generate_for_paragraphs(["good", "bad"])

    # The result stays index-aligned: success keeps its path, failure is "".
    assert paths == [str(tmp_path / "paragraph_audio" / "paragraph_1.mp3"), ""]
    assert Path(paths[0]).read_bytes() == b"ok"
    assert not (tmp_path / "paragraph_audio" / "paragraph_2.mp3").exists()
    assert "paragraph 2" in caplog.text


def test_generate_for_paragraph_missing_api_key_returns_none(tmp_path, monkeypatch):
    """generate_for_paragraph returns None when the API key is unset."""
    monkeypatch.delenv("ELEVENLABS_API_KEY", raising=False)

    with patch("youtube_shorts_gen.media.paragraph_tts.ElevenLabs") as mock_eleven:
        tts = ParagraphTTS(str(tmp_path))
        result = tts.generate_for_paragraph("text", 0)

    assert result is None
    mock_eleven.assert_not_called()
