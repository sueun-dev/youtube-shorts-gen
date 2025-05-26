"""YouTube upload pipeline for YouTube shorts."""

import logging
from pathlib import Path

from youtube_shorts_gen.upload.upload_to_youtube import YouTubeUploader


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
        # Upload to YouTube
        uploader = YouTubeUploader(run_dir)
        video_url = uploader.upload()

        final_video_path = Path(run_dir) / "final_story_video.mp4"

        if video_url:
            logging.info("[Upload Pipeline] Uploaded to YouTube: %s", video_url)
            return {
                "success": True,
                "video_url": video_url,
                "final_video_path": final_video_path,
            }
        else:
            logging.info(
                "[Upload Pipeline] Video not uploaded to YouTube: %s", final_video_path
            )
            return {
                "success": False,
                "error": "Upload failed but no exception was raised",
                "final_video_path": final_video_path,
            }
    except Exception as e:
        logging.exception("[Upload Pipeline] Failed: %s", e)
        return {"success": False, "error": str(e)}
