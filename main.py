import logging
import shutil
import tempfile
import time
from pathlib import Path
from typing import Any

from openai import OpenAI

from youtube_shorts_gen.pipelines.ai_content_pipeline import run_ai_content_pipeline
from youtube_shorts_gen.pipelines.internet_content_pipeline import (
    run_internet_content_pipeline,
)
from youtube_shorts_gen.pipelines.timelapse_pipeline import run_timelapse_pipeline
from youtube_shorts_gen.pipelines.upload_pipeline import run_upload_pipeline
from youtube_shorts_gen.pipelines.youtube_transcript_pipeline import (
    run_youtube_transcript_pipeline,
)
from youtube_shorts_gen.utils.config import SLEEP_SECONDS
from youtube_shorts_gen.utils.openai_client import get_openai_client
from youtube_shorts_gen.utils.setup import setup_logging, setup_run_directory

AI_CHOICE = "1"
INTERNET_CHOICE = "2"
YOUTUBE_TRANSCRIPT_CHOICE = "3"
TIMELAPSE_CHOICE = "4"


def _get_content_source_choice() -> str:
    """Prompt the user for a content source and validate the input.

    Repeatedly requests input until a valid choice is entered.

    Returns:
        str: The validated choice entered by the user.
    """
    while True:

        choice = input(
            f"Choose content source - AI ({AI_CHOICE}), "
            f"Internet ({INTERNET_CHOICE}), "
            f"YouTube Transcript ({YOUTUBE_TRANSCRIPT_CHOICE}), or "
            f"Time-lapse Video ({TIMELAPSE_CHOICE}): "
        )
        if choice in (AI_CHOICE, INTERNET_CHOICE, YOUTUBE_TRANSCRIPT_CHOICE, TIMELAPSE_CHOICE):
            return choice
        logging.warning("Invalid choice. Please enter again")


def _execute_chosen_pipeline(choice: str, run_dir: Path) -> dict[str, Any]:
    """Execute the content generation pipeline selected by the user.

    Args:
        choice: One of AI_CHOICE, INTERNET_CHOICE, YOUTUBE_TRANSCRIPT_CHOICE, or TIMELAPSE_CHOICE.
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
        
    if choice == TIMELAPSE_CHOICE:
        return _run_timelapse_pipeline(str(run_dir))

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


def _run_timelapse_pipeline(run_dir: str) -> dict[str, Any]:
    """Run the time-lapse video generation pipeline.
    
    Args:
        run_dir: Directory to store generated files
        
    Returns:
        Dict containing the result of the pipeline execution
    """
    try:
        # Get user inputs
        music_path_input = input("Enter background music file path (leave blank for no music): ").strip()
        if not music_path_input:
            music_path_input = None
        subject_prompt = input("Enter subject prompt (e.g., 'Red Ferrari Car'): ")
        
        # Get year range
        while True:
            try:
                year_range = input("Enter year range (e.g., '1950-2020'): ")
                start_year, end_year = map(int, year_range.split('-'))
                if start_year >= end_year:
                    logging.warning("Start year must be less than end year.")
                    continue
                if end_year - start_year > 100:
                    logging.warning("Maximum range is 100 years. Please enter a smaller range.")
                    continue
                break
            except ValueError:
                logging.warning("Invalid year range format. Use format 'YYYY-YYYY' (e.g., '1950-2020').")
        
        # Fixed playback settings (no interactive prompt)
        main_frame_duration = 0.5  # seconds each yearly image is shown
        inter_frame_duration = 0.033  # seconds per interpolated frame (3 frames ≈ 0.1s)
        num_inter_frames = 3  # three interpolated frames per transition
        fps = 30  # encode video at 30 fps
        
        # Get video title and description
        video_title = input(f"Enter video title (default: 'Evolution of {subject_prompt} ({start_year}-{end_year})'): ")
        if not video_title:
            video_title = f"Evolution of {subject_prompt} ({start_year}-{end_year})"
            
        video_description = input(f"Enter video description (default: 'Time-lapse showing the evolution of {subject_prompt} from {start_year} to {end_year}.'): ")
        if not video_description:
            video_description = f"Time-lapse showing the evolution of {subject_prompt} from {start_year} to {end_year}."
        
        # Get OpenAI client
        client = get_openai_client()
        
        # Run the pipeline
        logging.info(f"Running time-lapse pipeline for '{subject_prompt}' from {start_year} to {end_year} at {fps} FPS")
        video_path = run_timelapse_pipeline(
            run_dir=run_dir,
            client=client,
            subject_prompt=subject_prompt,
            start_year=start_year,
            end_year=end_year,
            fps=fps,
            upload_to_youtube=True,
            video_title=video_title,
            video_description=video_description,
            num_inter_frames=num_inter_frames,
            inter_frame_duration=inter_frame_duration,
            main_frame_duration=main_frame_duration,
            music_path=music_path_input
        )
        
        if video_path and Path(video_path).exists():
            return {
                "success": True,
                "final_video_path": video_path,
                "message": f"Time-lapse video created successfully: {video_path}"
            }
        else:
            return {
                "success": False,
                "error": "Failed to create time-lapse video"
            }
    
    except Exception as e:
        logging.exception("Error in time-lapse pipeline: %s", e)
        return {
            "success": False,
            "error": f"Time-lapse pipeline error: {str(e)}"
        }


def run_pipeline_once() -> None:
    """Run a single complete pipeline iteration.

    Includes setup, execution, and processing of the content pipeline.
    """
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
    """Set up logging and run the pipeline periodically."""
    setup_logging()
    while True:
        run_pipeline_once()
        sleep_minutes = SLEEP_SECONDS // 60
        logging.info("Waiting %d minutes until the next run...", sleep_minutes)
        time.sleep(SLEEP_SECONDS)


if __name__ == "__main__":
    main()
