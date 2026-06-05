"""YouTube upload pipeline for YouTube shorts."""

import logging
from pathlib import Path
from typing import Any

from youtube_shorts_gen.upload.upload_to_youtube import YouTubeUploader
from youtube_shorts_gen.utils.config import FINAL_VIDEO_FILENAME

# === Helper functions (Single Responsibility) ===


def _upload_final_video(run_dir: str) -> str | None:
    """Upload the final video in `run_dir` to YouTube and return the video URL."""
    uploader = YouTubeUploader(run_dir)
    return uploader.upload()


def _build_success_response(video_url: str, final_path: Path) -> dict[str, Any]:
    return {"success": True, "video_url": video_url, "final_video_path": final_path}


def _build_failure_response(message: str, final_path: Path) -> dict[str, Any]:
    return {"success": False, "error": message, "final_video_path": final_path}


# === Public API ===


def run_upload_pipeline(run_dir: str) -> dict[str, Any]:
    """Run the YouTube upload pipeline.

    Args:
        run_dir: Directory containing the video to upload.

    Returns:
        Dictionary with upload results (always contains a ``success`` key).
    """
    logging.info("[Upload Pipeline] Starting YouTube upload pipeline")
    final_video_path = Path(run_dir) / FINAL_VIDEO_FILENAME

    try:
        video_url = _upload_final_video(run_dir)

        if video_url:
            logging.info("[Upload Pipeline] Uploaded to YouTube: %s", video_url)
            return _build_success_response(video_url, final_video_path)

        logging.info(
            "[Upload Pipeline] Video not uploaded to YouTube: %s", final_video_path
        )
        return _build_failure_response(
            "Upload failed but no exception was raised", final_video_path
        )
    except Exception as exc:
        logging.exception("[Upload Pipeline] Failed")
        return _build_failure_response(str(exc), final_video_path)
