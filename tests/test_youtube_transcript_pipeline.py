"""Tests for the YouTube transcript pipeline and its collaborators."""

from pathlib import Path
from unittest.mock import MagicMock, patch

from youtube_shorts_gen.content.transcript_segmenter import TranscriptSegmenter
from youtube_shorts_gen.pipelines.youtube_transcript_pipeline import (
    run_youtube_transcript_pipeline,
)
from youtube_shorts_gen.scrapers.youtube_transcript_scraper import (
    YouTubeTranscriptScraper,
)

_PIPE = "youtube_shorts_gen.pipelines.youtube_transcript_pipeline"


def test_extract_video_id_handles_url_formats():
    scraper = YouTubeTranscriptScraper()
    vid = "dQw4w9WgXcQ"
    assert scraper.extract_video_id(f"https://www.youtube.com/watch?v={vid}") == vid
    assert scraper.extract_video_id(f"https://youtu.be/{vid}") == vid
    assert scraper.extract_video_id(f"https://www.youtube.com/embed/{vid}") == vid
    assert scraper.extract_video_id(f"https://www.youtube.com/shorts/{vid}") == vid
    assert scraper.extract_video_id("https://example.com") is None


@patch(f"{_PIPE}.process_segment_into_video")
@patch(f"{_PIPE}.TranscriptSegmenter")
@patch(f"{_PIPE}.get_openai_client")
@patch(f"{_PIPE}.YouTubeTranscriptScraper")
def test_pipeline_success(
    mock_scraper, mock_client, mock_segmenter, mock_process, tmp_path
):
    mock_scraper.return_value.fetch_transcript.return_value = "Sample transcript text"
    mock_client.return_value = MagicMock()
    mock_segmenter.return_value.segment_transcript.return_value = [
        "Segment one.",
        "Segment two.",
    ]

    def process_side_effect(client, segment, segment_dir, index):
        video = Path(segment_dir) / "output_story_video.mp4"
        video.touch()
        return {"segment_index": index, "final_video": str(video)}

    mock_process.side_effect = process_side_effect

    result = run_youtube_transcript_pipeline(
        str(tmp_path), "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
    )

    assert result["success"] is True
    assert len(result["segments"]) == 2
    assert len(result["segment_results"]) == 2
    assert len(result["final_video_paths"]) == 2
    assert (tmp_path / "full_transcript.txt").exists()
    assert (tmp_path / "segments" / "segment_1.txt").exists()
    assert (tmp_path / "segments" / "segment_2.txt").exists()


@patch(f"{_PIPE}.YouTubeTranscriptScraper")
def test_pipeline_failure_when_no_transcript(mock_scraper, tmp_path):
    mock_scraper.return_value.fetch_transcript.return_value = None

    result = run_youtube_transcript_pipeline(
        str(tmp_path), "https://www.youtube.com/watch?v=invalid"
    )

    assert result["success"] is False
    assert "Failed to fetch transcript" in result["error"]


def test_segment_transcript_returns_empty_for_short_input():
    segmenter = TranscriptSegmenter(client=MagicMock())
    assert segmenter.segment_transcript("too short") == []


def test_segment_transcript_generates_segments():
    client = MagicMock()
    response = MagicMock()
    response.choices = [MagicMock()]
    response.choices[0].message.content = "Generated segment text."
    client.chat.completions.create.return_value = response

    segmenter = TranscriptSegmenter(client=client)
    transcript = "word " * 80  # well above the minimum length threshold
    segments = segmenter.segment_transcript(transcript)

    assert isinstance(segments, list)
    assert all(isinstance(s, str) for s in segments)
    assert client.chat.completions.create.called
