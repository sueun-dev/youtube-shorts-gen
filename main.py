import logging
import time
from datetime import datetime
from pathlib import Path
from typing import Any

from youtube_shorts_gen.pipelines.ai_content_pipeline import run_ai_content_pipeline
from youtube_shorts_gen.pipelines.internet_content_pipeline import (
    run_internet_content_pipeline,
)
from youtube_shorts_gen.pipelines.upload_pipeline import run_upload_pipeline
from youtube_shorts_gen.utils.config import RUNS_BASE_DIR, SLEEP_SECONDS

# Constants for user choices
AI_CHOICE = "1"
INTERNET_CHOICE = "2"

# Constants for pipeline result dictionary keys
RESULT_KEY_SUCCESS = "success"
RESULT_KEY_ERROR = "error"
RESULT_KEY_VIDEO_URL = "video_url"
RESULT_KEY_FINAL_VIDEO_PATH = "final_video_path"


def setup_logging() -> None:
    """Configure logging for the application.

    Sets up basic logging configuration with timestamp formatting.
    """
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(levelname)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )


def _setup_run_directory() -> Path:
    """Create and return a timestamped directory for the current run."""
    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    run_dir = Path(RUNS_BASE_DIR) / timestamp
    run_dir.mkdir(parents=True)
    logging.info("[SETUP] Created run directory: %s", run_dir)
    return run_dir


def _get_content_source_choice() -> str:
    """Prompt user for content source and validate the input."""
    while True:
        # Break long prompt into shorter strings
        prompt = (
            f"Choose content source - AI ({AI_CHOICE}) or "
            f"Internet ({INTERNET_CHOICE}): "
        )
        choice = input(prompt)
        if choice in [AI_CHOICE, INTERNET_CHOICE]:
            return choice
        logging.warning(
            "Invalid choice. Please enter '%s' for AI or '%s' for Internet.",
            AI_CHOICE,
            INTERNET_CHOICE,
        )


def _execute_chosen_pipeline(choice: str, run_dir: Path) -> dict[str, Any]:
    """Execute the chosen content generation pipeline."""
    if choice == INTERNET_CHOICE:
        logging.info("Starting Internet content pipeline...")
        return run_internet_content_pipeline(str(run_dir))
    logging.info("Starting AI content pipeline...")
    return run_ai_content_pipeline(str(run_dir))


def _process_pipeline_output(content_result: dict[str, Any], run_dir: Path) -> None:
    """Process the output of the content pipeline, handling upload and logging."""
    if content_result.get(RESULT_KEY_SUCCESS, False):
        logging.info("Content generation successful. Proceeding to upload...")
        upload_result = run_upload_pipeline(str(run_dir))

        if upload_result.get(RESULT_KEY_SUCCESS, False):
            logging.info(
                "[SUCCESS] Uploaded to YouTube: %s",
                upload_result.get(RESULT_KEY_VIDEO_URL, "N/A"),
            )
        else:
            logging.info(
                "[INFO] Video created but not uploaded to YouTube: %s",
                content_result.get(RESULT_KEY_FINAL_VIDEO_PATH, "Unknown path"),
            )
    else:
        logging.error(
            "[FAILURE] Content generation failed: %s",
            content_result.get(RESULT_KEY_ERROR, "Unknown error"),
        )


def run_pipeline_once() -> None:
    """Run one complete pipeline iteration.

    Includes setup, execution, and processing of the content pipeline.
    """
    run_dir: Path | None = None
    try:
        run_dir = _setup_run_directory()
        logging.info("[START] New Run: %s", run_dir)

        choice = _get_content_source_choice()
        content_result = _execute_chosen_pipeline(choice, run_dir)
        _process_pipeline_output(content_result, run_dir)

        logging.info("[DONE] Pipeline iteration completed for: %s", run_dir)

    except (OSError, ValueError, KeyError):
        logging.exception(
            "[CRITICAL] Pipeline failed with a known error type for run %s:", run_dir
        )
    except Exception:
        logging.exception(
            "[CRITICAL] Pipeline failed with an unexpected error for run %s:", run_dir
        )


def main() -> None:
    setup_logging()

    while True:
        run_pipeline_once()
        sleep_minutes = SLEEP_SECONDS // 60
        logging.info("Waiting %d minutes until the next run...", sleep_minutes)
        time.sleep(SLEEP_SECONDS)


if __name__ == "__main__":
    main()
