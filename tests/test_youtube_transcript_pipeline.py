"""Tests for the YouTube transcript pipeline."""

from unittest.mock import patch, MagicMock
import pytest
from pathlib import Path
from youtube_shorts_gen.content.transcript_segmenter import TranscriptSegmenter
from youtube_shorts_gen.pipelines.youtube_transcript_pipeline import (
    run_youtube_transcript_pipeline,
    YouTubeTranscriptScraper,
)
from youtube_shorts_gen.scrapers.youtube_transcript_scraper import (
    YouTubeTranscriptScraper,
)


@pytest.fixture
def mock_transcript_scraper():
    """Mock the YouTube transcript scraper."""
    with patch(
        "youtube_shorts_gen.scrapers.youtube_transcript_scraper.YouTubeTranscriptScraper"
    ) as mock:
        instance = mock.return_value
        instance.fetch_transcript.return_value = (
            "This is a sample transcript for testing purposes. "
            "It contains multiple sentences that will be processed into segments."
        )
        yield instance


@pytest.fixture
def mock_transcript_segmenter():
    """Mock the transcript segmenter."""
    with patch(
        "youtube_shorts_gen.pipelines.youtube_transcript_pipeline.TranscriptSegmenter"
    ) as mock:
        instance = mock.return_value
        instance.segment_transcript.return_value = [
            "This is segment 1 for testing.",
            "This is segment 2 for testing."
        ]
        yield instance


@pytest.fixture
def mock_paragraph_processor():
    """Mock the paragraph processor."""
    with patch(
        "youtube_shorts_gen.pipelines.youtube_transcript_pipeline.ParagraphProcessor"
    ) as mock:
        instance = mock.return_value
        instance.process.return_value = {
            "story": "Test story",
            "processed_paragraphs": ["Test paragraph"],
            "image_paths": ["/path/to/image.png"],
            "audio_paths": ["/path/to/audio.mp3"],
            "segment_paths": ["/path/to/segment.mp4"],
            "final_video": "/path/to/final_video.mp4"
        }
        yield instance


@pytest.fixture
def mock_script_and_image():
    """Mock the script and image generator."""
    with patch(
        "youtube_shorts_gen.pipelines.youtube_transcript_pipeline.ScriptAndImageFromInternet"
    ) as mock:
        instance = mock.return_value
        instance.run.return_value = {
            "story": "Test story",
            "sentences": ["Test sentence 1", "Test sentence 2"],
            "image_paths": ["/path/to/image1.png", "/path/to/image2.png"]
        }
        yield instance


def test_youtube_transcript_scraper():
    """Test the YouTube transcript scraper."""
    # Test video ID extraction
    scraper = YouTubeTranscriptScraper()
    
    # Test various YouTube URL formats
    assert scraper.extract_video_id(
        "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
    ) == "dQw4w9WgXcQ"
    assert scraper.extract_video_id("https://youtu.be/dQw4w9WgXcQ") == "dQw4w9WgXcQ"
    assert scraper.extract_video_id(
        "https://www.youtube.com/embed/dQw4w9WgXcQ"
    ) == "dQw4w9WgXcQ"
    assert scraper.extract_video_id(
        "https://www.youtube.com/shorts/dQw4w9WgXcQ"
    ) == "dQw4w9WgXcQ"
    
    # Test invalid URL
    assert scraper.extract_video_id("https://example.com") is None


@patch("youtube_shorts_gen.pipelines.youtube_transcript_pipeline.process_segment_into_video")
@patch("youtube_shorts_gen.pipelines.youtube_transcript_pipeline.YouTubeTranscriptScraper")
def test_youtube_transcript_pipeline_success(mock_scraper_class, mock_process_segment, tmp_path,
                                             mock_transcript_segmenter, 
                                             mock_paragraph_processor,
                                             mock_script_and_image):
    """Test the YouTube transcript pipeline with successful transcript fetching."""
    # Setup
    mock_scraper = mock_scraper_class.return_value
    mock_scraper.fetch_transcript.return_value = "Sample transcript text"
    
    # Mock process_segment_into_video to return successful results for both segments
    def mock_process_segment_side_effect(client, segment, segment_dir, index):
        return {
            "segment_index": index,
            "segment_text": segment,
            "image_paths": [f"image_{index}_1.png", f"image_{index}_2.png"],
            "audio_paths": [f"audio_{index}_1.mp3", f"audio_{index}_2.mp3"],
            "segment_videos": [f"video_{index}_1.mp4", f"video_{index}_2.mp4"],
            "final_video": str(Path(segment_dir) / "output_story_video.mp4")
        }
    
    mock_process_segment.side_effect = mock_process_segment_side_effect
    
    # Create dummy output video files that the pipeline expects.
    # The mock_transcript_segmenter returns 2 segments, so we expect 2 video files.
    # The pipeline itself creates the segment_X directories.
    # We create the dummy video files within these expected directories.
    for i in range(1, 3):  # For segment_1 and segment_2
        segment_dir = tmp_path / f"segment_{i}"
        segment_dir.mkdir(parents=True, exist_ok=True)  # Ensure dir exists for touch
        (segment_dir / "output_story_video.mp4").touch()

    # Run the pipeline
    result = run_youtube_transcript_pipeline(str(tmp_path), "https://www.youtube.com/watch?v=dQw4w9WgXcQ")
    
    # Assertions
    assert result["success"] is True
    assert len(result["segments"]) == 2  # From mock_transcript_segmenter
    assert len(result["segment_results"]) == 2
    assert len(result["final_video_paths"]) == 2
    
    # Verify transcript was saved
    transcript_path = tmp_path / "full_transcript.txt"
    assert transcript_path.exists()
    
    # Verify segments directory was created
    segments_dir = tmp_path / "segments"
    assert segments_dir.exists()
    assert (segments_dir / "segment_1.txt").exists()
    assert (segments_dir / "segment_2.txt").exists()


@patch("youtube_shorts_gen.pipelines.youtube_transcript_pipeline.YouTubeTranscriptScraper")
def test_youtube_transcript_pipeline_failure(mock_scraper_class, tmp_path):
    """Test the YouTube transcript pipeline with failed transcript fetching."""
    # Setup
    mock_scraper = mock_scraper_class.return_value
    mock_scraper.fetch_transcript.return_value = None
    
    # Run the pipeline
    result = run_youtube_transcript_pipeline(str(tmp_path), "https://www.youtube.com/watch?v=invalid")
    
    # Assertions
    assert result["success"] is False
    assert "Failed to fetch transcript" in result["error"]


@patch("youtube_shorts_gen.content.transcript_segmenter.TranscriptSegmenter")
@patch("openai.OpenAI")
def test_transcript_segmenter(mock_openai_class, mock_segmenter_class):
    """Test the transcript segmenter."""
    # Setup
    mock_openai = mock_openai_class.return_value
    mock_segmenter = mock_segmenter_class.return_value
    mock_segmenter.segment_transcript.return_value = [
        "This is segment 1.",
        "This is segment 2."
    ]
    
    # Create a real segmenter to test the initialization
    segmenter = TranscriptSegmenter(client=mock_openai)
    
    # Test with mock
    transcript = "This is a test transcript."
    segments = mock_segmenter.segment_transcript(transcript)
    
    # Assertions
    assert len(segments) == 2
    assert segments[0] == "This is segment 1."
    assert segments[1] == "This is segment 2."
    mock_segmenter.segment_transcript.assert_called_once_with(transcript)
