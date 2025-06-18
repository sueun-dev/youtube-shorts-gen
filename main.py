import logging
import shutil
import tempfile
import time
from pathlib import Path
from typing import Any

from youtube_shorts_gen.pipelines.ai_content_pipeline import run_ai_content_pipeline
from youtube_shorts_gen.pipelines.internet_content_pipeline import (
    run_internet_content_pipeline,
)
from youtube_shorts_gen.pipelines.upload_pipeline import run_upload_pipeline
from youtube_shorts_gen.pipelines.youtube_transcript_pipeline import (
    run_youtube_transcript_pipeline,
)
from youtube_shorts_gen.utils.config import SLEEP_SECONDS
from youtube_shorts_gen.utils.setup import setup_logging, setup_run_directory

AI_CHOICE = "1"
INTERNET_CHOICE = "2"
YOUTUBE_TRANSCRIPT_CHOICE = "3"


def _get_content_source_choice() -> str:
    """Prompt the user for a content source and validate the input.

    Repeatedly requests input until a valid choice is entered.

    Returns:
        str: The validated choice entered by the user.
    """
    while True:
        choice = input(
            f"Choose content source - AI ({AI_CHOICE}), "
            f"Internet ({INTERNET_CHOICE}), or "
            f"YouTube Transcript ({YOUTUBE_TRANSCRIPT_CHOICE}): "
        )
        if choice in (AI_CHOICE, INTERNET_CHOICE, YOUTUBE_TRANSCRIPT_CHOICE):
            return choice
        logging.warning("Invalid choice. Please enter again")


def _execute_chosen_pipeline(choice: str, run_dir: Path) -> dict[str, Any]:
    """Execute the content generation pipeline selected by the user.

    Args:
        choice: One of AI_CHOICE, INTERNET_CHOICE, or YOUTUBE_TRANSCRIPT_CHOICE.
        run_dir: The directory in which to run the pipeline.

    Returns:
        Dict[str, Any]: The result of the pipeline execution.
    """
    if choice == INTERNET_CHOICE:
        return run_internet_content_pipeline(str(run_dir))

    if choice == YOUTUBE_TRANSCRIPT_CHOICE:
        youtube_url = input("Enter YouTube video URL: ")
        return run_youtube_transcript_pipeline(str(run_dir), youtube_url)

    if choice == AI_CHOICE:
        return run_ai_content_pipeline(str(run_dir))

    return {"success": False, "error": f"Invalid choice: {choice}"}


def _process_pipeline_output(
    content_result: dict[str, Any], run_dir: Path
) -> None:
    """Process the output of the content pipeline, handling upload and logging.

    Args:
        content_result: The dictionary containing pipeline output data.
        run_dir: The directory where output was generated.
    """
    if content_result.get("success", False):
        final_paths = content_result.get("final_video_paths")
        if final_paths:
            logging.info("Multiple videos created from YouTube transcript.")

            logging.info("Processing %d generated videos...", len(final_paths))
            for index, video_path in enumerate(final_paths, start=1):
                logging.info(
                    "Processing video %d/%d: %s",
                    index, len(final_paths), Path(video_path).name
                )
                
                with tempfile.TemporaryDirectory() as temp_dir:
                    temp_video_path = Path(temp_dir) / "final_story_video.mp4"
                    shutil.copy(video_path, temp_video_path)

                    segment_dir = Path(video_path).parent
                    prompt_path = segment_dir / "story_prompt.txt"
                    temp_prompt_path = Path(temp_dir) / "story_prompt.txt"
                    if prompt_path.exists():
                        shutil.copy(prompt_path, temp_prompt_path)
                        logging.info(
                            "Copied story_prompt.txt for upload: %s",
                            prompt_path
                        )
                    else:
                        with temp_prompt_path.open(
                            "w", encoding="utf-8"
                        ) as prompt_file:
                            prompt_file.write(
                                f"YouTube Shorts video segment {video_path}"
                            )
                        logging.info("Created dummy story_prompt.txt for upload")

                    upload_result = run_upload_pipeline(temp_dir)
                    if upload_result.get("success", False):
                        logging.info(
                            "[SUCCESS] Uploaded video %d/%d to YouTube",
                            index, len(final_paths)
                        )
                    else:
                        logging.info(
                            "[INFO] Failed to upload video %d/%d to YouTube",
                            index, len(final_paths)
                        )
            
            if not final_paths:
                logging.error("No videos found to upload.")
        else:
            logging.info("Content generation successful. Proceeding to upload...")
            upload_result = run_upload_pipeline(str(run_dir))
            if upload_result.get("success", False):
                logging.info("[SUCCESS] Uploaded to YouTube")
            else:
                logging.info("[INFO] Video created but not uploaded to YouTube")
    else:
        logging.error("[FAILURE] Content generation failed")


def run_pipeline_once() -> None:
    """Run a single complete pipeline iteration.

    Includes setup, execution, and processing of the content pipeline.
    """
    run_dir: Path | None = None
    try:
        run_dir = setup_run_directory()
        logging.info("[START] New run: %s", run_dir)

        choice = _get_content_source_choice()
        content_result = _execute_chosen_pipeline(choice, run_dir)
        _process_pipeline_output(content_result, run_dir)

        logging.info("[DONE] Pipeline iteration completed for: %s", run_dir)
    except Exception:
        logging.exception(
            "[CRITICAL] Pipeline failed with an unexpected error for run %s", run_dir
        )


def main() -> None:
    """Set up logging and run the pipeline periodically."""
    setup_logging()
    while True:
        run_pipeline_once()
        sleep_minutes = SLEEP_SECONDS // 60
        logging.info("Waiting %d minutes until the next run...", sleep_minutes)
        time.sleep(SLEEP_SECONDS)


if __name__ == "__main__":
    main()
