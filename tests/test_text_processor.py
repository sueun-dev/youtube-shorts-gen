"""Tests for youtube_shorts_gen.media.text_processor.TextProcessor."""

from unittest.mock import MagicMock

from openai import OpenAIError

from youtube_shorts_gen.media.text_processor import TextProcessor
from youtube_shorts_gen.utils.config import (
    MAX_PARAGRAPHS_FOR_SHORTS,
    SUMMARIZE_THRESHOLD_CHARS,
)


def _make_processor(run_dir, client=None):
    """Build a TextProcessor with a mock OpenAI client."""
    return TextProcessor(str(run_dir), client or MagicMock())


def _chat_response(content):
    """Build a mock OpenAI chat completion response with given content."""
    response = MagicMock()
    response.choices = [MagicMock()]
    response.choices[0].message.content = content
    return response


def test_split_multi_paragraph_story_into_segments(tmp_path):
    """A multi-paragraph story is split into stripped paragraph segments."""
    processor = _make_processor(tmp_path)
    text = "First paragraph.\n\n  Second paragraph.  \n\nThird paragraph."

    segments = processor.get_content_segments(text)

    assert segments == [
        "First paragraph.",
        "Second paragraph.",
        "Third paragraph.",
    ]


def test_paragraphs_capped_at_max(tmp_path):
    """More than MAX_PARAGRAPHS_FOR_SHORTS paragraphs are truncated to the cap."""
    processor = _make_processor(tmp_path)
    num_paragraphs = MAX_PARAGRAPHS_FOR_SHORTS + 5
    # Keep each paragraph short so summarization never triggers.
    paragraphs = [f"Paragraph number {i}." for i in range(num_paragraphs)]
    text = "\n\n".join(paragraphs)

    segments = processor.get_content_segments(text)

    assert len(segments) == MAX_PARAGRAPHS_FOR_SHORTS
    assert segments == paragraphs[:MAX_PARAGRAPHS_FOR_SHORTS]


def test_long_paragraph_is_summarized_via_client(tmp_path):
    """A paragraph over the threshold is summarized using the client's output."""
    client = MagicMock()
    summary = "A short summary of the long paragraph."
    client.chat.completions.create.return_value = _chat_response(summary)
    processor = _make_processor(tmp_path, client)

    long_paragraph = "word " * (SUMMARIZE_THRESHOLD_CHARS + 50)
    assert len(long_paragraph) > SUMMARIZE_THRESHOLD_CHARS

    segments = processor.get_content_segments(long_paragraph)

    client.chat.completions.create.assert_called_once()
    assert segments == [summary]


def test_summarize_failure_falls_back_to_truncation(tmp_path):
    """If the client raises, the paragraph is truncated to 500 chars, no raise."""
    client = MagicMock()
    client.chat.completions.create.side_effect = OpenAIError("boom")
    processor = _make_processor(tmp_path, client)

    long_paragraph = "x" * (SUMMARIZE_THRESHOLD_CHARS + 600)
    assert len(long_paragraph) > 500

    segments = processor.get_content_segments(long_paragraph)

    client.chat.completions.create.assert_called_once()
    assert segments == [long_paragraph[:500]]
    assert len(segments[0]) == 500


def test_short_paragraph_is_not_summarized(tmp_path):
    """Paragraphs at or below the threshold are returned untouched."""
    client = MagicMock()
    processor = _make_processor(tmp_path, client)
    # Two short paragraphs so the single-large-segment fallback is not hit.
    text = "A short first line.\n\nA short second line."

    segments = processor.get_content_segments(text)

    client.chat.completions.create.assert_not_called()
    assert segments == ["A short first line.", "A short second line."]


def test_summarize_disabled_returns_raw_segments(tmp_path):
    """When summarization is disabled the long paragraph is returned as-is."""
    client = MagicMock()
    processor = _make_processor(tmp_path, client)
    long_paragraph = "y" * (SUMMARIZE_THRESHOLD_CHARS + 100)

    segments = processor.get_content_segments(
        long_paragraph, summarize_long_paragraphs=False
    )

    client.chat.completions.create.assert_not_called()
    assert segments == [long_paragraph]


def test_mapping_file_sentences_take_priority(tmp_path):
    """Sentences from the mapping file are used and short-circuit splitting."""
    client = MagicMock()
    mapping = tmp_path / "sentence_image_mapping.txt"
    mapping.write_text(
        "Sentence 1: First mapped sentence.\n"
        "Image: /tmp/img1.png\n\n"
        "Sentence 2: Second mapped sentence.\n"
        "Image: /tmp/img2.png\n",
        encoding="utf-8",
    )
    processor = _make_processor(tmp_path, client)

    segments = processor.get_content_segments("ignored text here")

    assert segments == ["First mapped sentence.", "Second mapped sentence."]
    client.chat.completions.create.assert_not_called()


def test_single_large_paragraph_falls_back_to_sentences(tmp_path):
    """One large paragraph with multiple sentences is re-split by sentence."""
    client = MagicMock()
    processor = _make_processor(tmp_path, client)
    sentence = "This is a fairly wordy sentence about dragons and knights. "
    text = sentence * 12  # one paragraph, >500 chars, many sentences

    segments = processor.get_content_segments(
        text, summarize_long_paragraphs=False
    )

    assert len(segments) > 1
    assert all(s.endswith(".") for s in segments)


def test_empty_text_returns_empty_list(tmp_path):
    """Whitespace-only input yields no segments without errors."""
    client = MagicMock()
    processor = _make_processor(tmp_path, client)

    segments = processor.get_content_segments("   \n\n   ")

    assert segments == []
    client.chat.completions.create.assert_not_called()
