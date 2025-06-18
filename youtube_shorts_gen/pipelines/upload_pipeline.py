"""YouTube upload pipeline for YouTube shorts."""

import logging
from pathlib import Path
from typing import Any

from youtube_shorts_gen.upload.upload_to_youtube import YouTubeUploader

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

def run_upload_pipeline(run_dir: str) -> dict:
    """
    Run the YouTube upload pipeline.

    Args:
        run_dir: Directory containing the video to upload

    Returns:
        Dictionary with upload results
    """
    logging.info("[Upload Pipeline] Starting YouTube upload pipeline")

    try:
        final_video_path = Path(run_dir) / "final_story_video.mp4"

        # 1. Attempt upload
        video_url = _upload_final_video(run_dir)

        if video_url:
            logging.info("[Upload Pipeline] Uploaded to YouTube: %s", video_url)
            return _build_success_response(video_url, final_video_path)

        logging.info(
            "[Upload Pipeline] Video not uploaded to YouTube: %s",
            final_video_path
        )
        return _build_failure_response(
            "Upload failed but no exception was raised",
            final_video_path
        )
    except Exception as e:
        logging.exception("[Upload Pipeline] Failed: %s", e)
        return {"success": False, "error": str(e)}
