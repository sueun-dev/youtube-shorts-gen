#!/usr/bin/env python
"""
Entry point for Internet content generation pipeline.
This script runs only the Internet content generation part of the YouTube Shorts Generator.
"""

import logging
import sys
from datetime import datetime
from pathlib import Path

from youtube_shorts_gen.pipelines.internet_content_pipeline import (
    run_internet_content_pipeline,
)
from youtube_shorts_gen.pipelines.upload_pipeline import run_upload_pipeline
from youtube_shorts_gen.utils.config import RUNS_BASE_DIR


def setup_logging() -> None:
    """Configure logging for the application."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(levelname)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )


def main() -> int:
    """Run the Internet content generation pipeline."""
    setup_logging()

    # Create a timestamped directory for this run
    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    run_dir = Path(RUNS_BASE_DIR) / timestamp
    run_dir.mkdir(parents=True, exist_ok=True)

    logging.info("[START] New Internet Content Run: %s", run_dir)

    try:
        # Run Internet content pipeline
        content_result = run_internet_content_pipeline(str(run_dir))

        # Only proceed to upload if content generation was successful
        if content_result.get("success", False):
            # Ask if user wants to upload
            upload_choice = input("Upload to YouTube? (y/n): ").lower()

            if upload_choice == "y":
                # Upload to YouTube
                upload_result = run_upload_pipeline(str(run_dir))

                if upload_result.get("success", False):
                    logging.info(
                        "[DONE] Uploaded to YouTube: %s", upload_result["video_url"]
                    )
                else:
                    logging.info(
                        "[DONE] Video created but not uploaded to YouTube: %s",
                        content_result.get("final_video_path", "Unknown path"),
                    )
            else:
                logging.info(
                    "[DONE] Video created but not uploaded to YouTube: %s",
                    content_result.get("final_video_path", "Unknown path"),
                )
        else:
            logging.error(
                "[ERROR] Content generation failed: %s",
                content_result.get("error", "Unknown error"),
            )
            return 1

        logging.info("[DONE] Pipeline completed for: %s", run_dir)
        return 0
    except Exception as e:
        logging.exception("[ERROR] Pipeline failed: %s", e)
        return 1


if __name__ == "__main__":
    sys.exit(main())
