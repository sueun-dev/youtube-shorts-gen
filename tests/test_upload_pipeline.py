"""Tests for the YouTube upload pipeline wrapper."""

from unittest.mock import MagicMock, patch

from youtube_shorts_gen.pipelines.upload_pipeline import run_upload_pipeline

_U = "youtube_shorts_gen.pipelines.upload_pipeline"


def test_upload_success(tmp_path):
    uploader = MagicMock()
    uploader.upload.return_value = "https://youtu.be/abc123"
    with patch(f"{_U}.YouTubeUploader", return_value=uploader):
        result = run_upload_pipeline(str(tmp_path))

    assert result["success"] is True
    assert result["video_url"] == "https://youtu.be/abc123"
    assert result["final_video_path"].name == "final_story_video.mp4"


def test_upload_returns_no_url_is_failure(tmp_path):
    uploader = MagicMock()
    uploader.upload.return_value = None
    with patch(f"{_U}.YouTubeUploader", return_value=uploader):
        result = run_upload_pipeline(str(tmp_path))

    assert result["success"] is False
    assert "final_video_path" in result


def test_upload_exception_is_caught(tmp_path):
    uploader = MagicMock()
    uploader.upload.side_effect = RuntimeError("auth failed")
    with patch(f"{_U}.YouTubeUploader", return_value=uploader):
        result = run_upload_pipeline(str(tmp_path))

    assert result["success"] is False
    assert "auth failed" in result["error"]
    assert "final_video_path" in result
