"""Interactive entry point: pick a content source, build a Short, upload it."""

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
from youtube_shorts_gen.pipelines.timelapse_pipeline import run_timelapse_pipeline
from youtube_shorts_gen.pipelines.upload_pipeline import run_upload_pipeline
from youtube_shorts_gen.pipelines.youtube_transcript_pipeline import (
    run_youtube_transcript_pipeline,
)
from youtube_shorts_gen.utils.config import (
    FINAL_VIDEO_FILENAME,
    SLEEP_SECONDS,
    STORY_PROMPT_FILENAME,
    VIDEO_FPS,
)
from youtube_shorts_gen.utils.openai_client import get_openai_client
from youtube_shorts_gen.utils.setup import setup_logging, setup_run_directory

AI_CHOICE = "1"
INTERNET_CHOICE = "2"
YOUTUBE_TRANSCRIPT_CHOICE = "3"
TIMELAPSE_CHOICE = "4"
_VALID_CHOICES = (
    AI_CHOICE,
    INTERNET_CHOICE,
    YOUTUBE_TRANSCRIPT_CHOICE,
    TIMELAPSE_CHOICE,
)

# Guard rails for the interactive time-lapse year-range prompt.
_MAX_YEAR_SPAN = 100


def _get_content_source_choice() -> str:
    """Prompt for a content source, repeating until a valid choice is entered."""
    while True:
        choice = input(
            f"Choose content source - AI ({AI_CHOICE}), "
            f"Internet ({INTERNET_CHOICE}), "
            f"YouTube Transcript ({YOUTUBE_TRANSCRIPT_CHOICE}), or "
            f"Time-lapse Video ({TIMELAPSE_CHOICE}): "
        )
        if choice in _VALID_CHOICES:
            return choice
        logging.warning("Invalid choice. Please enter again")


def _execute_chosen_pipeline(choice: str, run_dir: Path) -> dict[str, Any]:
    """Execute the content-generation pipeline selected by the user."""
    if choice == INTERNET_CHOICE:
        return run_internet_content_pipeline(str(run_dir))
    if choice == YOUTUBE_TRANSCRIPT_CHOICE:
        youtube_url = input("Enter YouTube video URL: ")
        return run_youtube_transcript_pipeline(str(run_dir), youtube_url)
    if choice == AI_CHOICE:
        return run_ai_content_pipeline(str(run_dir))
    if choice == TIMELAPSE_CHOICE:
        return _run_timelapse_pipeline(str(run_dir))
    return {"success": False, "error": f"Invalid choice: {choice}"}


def _upload_transcript_video(video_path: str, index: int, total: int) -> None:
    """Upload one transcript-segment video via a temporary staging directory."""
    logging.info("Processing video %d/%d: %s", index, total, Path(video_path).name)
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)
        shutil.copy(video_path, temp_path / FINAL_VIDEO_FILENAME)

        prompt_src = Path(video_path).parent / STORY_PROMPT_FILENAME
        prompt_dst = temp_path / STORY_PROMPT_FILENAME
        if prompt_src.exists():
            shutil.copy(prompt_src, prompt_dst)
            logging.info("Copied %s for upload", STORY_PROMPT_FILENAME)
        else:
            prompt_dst.write_text(
                f"YouTube Shorts video segment {video_path}", encoding="utf-8"
            )
            logging.info("Created placeholder %s for upload", STORY_PROMPT_FILENAME)

        upload_result = run_upload_pipeline(temp_dir)
        if upload_result.get("success", False):
            logging.info("[SUCCESS] Uploaded video %d/%d to YouTube", index, total)
        else:
            logging.info("[INFO] Failed to upload video %d/%d to YouTube", index, total)


def _process_pipeline_output(content_result: dict[str, Any], run_dir: Path) -> None:
    """Upload the pipeline output, handling both single- and multi-video results."""
    if not content_result.get("success", False):
        logging.error("[FAILURE] Content generation failed")
        return

    final_paths = content_result.get("final_video_paths")
    if final_paths:
        logging.info("Processing %d generated videos...", len(final_paths))
        for index, video_path in enumerate(final_paths, start=1):
            _upload_transcript_video(video_path, index, len(final_paths))
        return

    logging.info("Content generation successful. Proceeding to upload...")
    upload_result = run_upload_pipeline(str(run_dir))
    if upload_result.get("success", False):
        logging.info("[SUCCESS] Uploaded to YouTube")
    else:
        logging.info("[INFO] Video created but not uploaded to YouTube")


def _prompt_year_range() -> tuple[int, int]:
    """Prompt for a validated ``start-end`` year range."""
    while True:
        year_range = input("Enter year range (e.g., '1950-2020'): ")
        try:
            start_year, end_year = (int(part) for part in year_range.split("-"))
        except ValueError:
            logging.warning("Invalid format. Use 'YYYY-YYYY' (e.g., '1950-2020').")
            continue
        if start_year >= end_year:
            logging.warning("Start year must be less than end year.")
            continue
        if end_year - start_year > _MAX_YEAR_SPAN:
            logging.warning("Maximum range is %d years.", _MAX_YEAR_SPAN)
            continue
        return start_year, end_year


def _run_timelapse_pipeline(run_dir: str) -> dict[str, Any]:
    """Gather interactive inputs and run the time-lapse pipeline."""
    try:
        music_path = (
            input("Enter background music file path (blank for none): ").strip() or None
        )
        subject_prompt = input("Enter subject prompt (e.g., 'Red Ferrari Car'): ")
        start_year, end_year = _prompt_year_range()

        default_title = f"Evolution of {subject_prompt} ({start_year}-{end_year})"
        video_title = input(f"Enter video title (default: '{default_title}'): ")

        default_description = (
            f"Time-lapse showing the evolution of {subject_prompt} "
            f"from {start_year} to {end_year}."
        )
        video_description = input(
            f"Enter video description (default: '{default_description}'): "
        )

        client = get_openai_client()
        logging.info(
            "Running time-lapse pipeline for '%s' from %d to %d",
            subject_prompt,
            start_year,
            end_year,
        )
        video_path = run_timelapse_pipeline(
            run_dir=run_dir,
            client=client,
            subject_prompt=subject_prompt,
            start_year=start_year,
            end_year=end_year,
            fps=VIDEO_FPS,
            upload_to_youtube=True,
            video_title=video_title or default_title,
            video_description=video_description or default_description,
            music_path=music_path,
        )

        if video_path and Path(video_path).exists():
            return {
                "success": True,
                "final_video_path": video_path,
                "message": f"Time-lapse video created successfully: {video_path}",
            }
        return {"success": False, "error": "Failed to create time-lapse video"}
    except Exception as exc:
        logging.exception("Error in time-lapse pipeline")
        return {"success": False, "error": f"Time-lapse pipeline error: {exc}"}


def run_pipeline_once() -> None:
    """Run a single complete pipeline iteration: setup, execute, upload."""
    run_dir: Path | None = None
    try:
        run_dir = setup_run_directory()
        choice = _get_content_source_choice()
        content_result = _execute_chosen_pipeline(choice, run_dir)
        _process_pipeline_output(content_result, run_dir)
        logging.info("[DONE] Pipeline iteration completed for: %s", run_dir)
    except Exception:
        logging.exception(
            "[CRITICAL] Pipeline failed with an unexpected error for run %s", run_dir
        )


def main() -> None:
    """Set up logging and run the pipeline on a loop."""
    setup_logging()
    while True:
        run_pipeline_once()
        logging.info("Waiting %d minutes until the next run...", SLEEP_SECONDS // 60)
        time.sleep(SLEEP_SECONDS)


if __name__ == "__main__":
    main()
