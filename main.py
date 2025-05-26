import logging
import time
from datetime import datetime
from pathlib import Path

from youtube_shorts_gen.pipelines.ai_content_pipeline import run_ai_content_pipeline
from youtube_shorts_gen.pipelines.internet_content_pipeline import (
    run_internet_content_pipeline,
)
from youtube_shorts_gen.pipelines.upload_pipeline import run_upload_pipeline
from youtube_shorts_gen.utils.config import RUNS_BASE_DIR, SLEEP_SECONDS


def setup_logging() -> None:
    """Configure logging for the application.

    Sets up basic logging configuration with timestamp formatting.
    """
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(levelname)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )


def run_pipeline_once() -> None:
    """Run one complete pipeline iteration.

    Creates a timestamped directory for the current run, prompts for content source,
    executes the appropriate pipeline, and handles the upload process if content
    generation is successful.

    Returns:
        None
    """
    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    run_dir = Path(RUNS_BASE_DIR) / timestamp
    run_dir.mkdir(parents=True, exist_ok=True)

    logging.info("[START] New Run: %s", run_dir)

    try:
        choice = input("Choose content source - AI (1) or Internet (2): ")

        if choice == "2":
            content_result = run_internet_content_pipeline(str(run_dir))
        else:
            content_result = run_ai_content_pipeline(str(run_dir))

        if content_result.get("success", False):
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
            logging.error(
                "[ERROR] Content generation failed: %s",
                content_result.get("error", "Unknown error"),
            )

        logging.info("[DONE] Pipeline completed for: %s", run_dir)
    except (OSError, ValueError, KeyError) as e:
        logging.exception("[ERROR] Pipeline failed with error: %s", e)
    except Exception as e:
        logging.exception("[ERROR] Pipeline failed with unexpected error: %s", e)


def main() -> None:
    setup_logging()

    while True:
        run_pipeline_once()
        logging.info("Waiting %d minutes until next run...", SLEEP_SECONDS // 60)
        time.sleep(SLEEP_SECONDS)


if __name__ == "__main__":
    main()
