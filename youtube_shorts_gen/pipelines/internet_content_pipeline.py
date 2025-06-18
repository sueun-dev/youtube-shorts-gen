import logging
import shutil
from pathlib import Path
from typing import Any

from youtube_shorts_gen.content.script_and_image_from_internet import (
    ScriptAndImageFromInternet,
)
from youtube_shorts_gen.media.paragraph_processor import ParagraphProcessor
from youtube_shorts_gen.utils.openai_client import get_openai_client


def _generate_script_and_images(run_dir: str, client) -> dict[str, Any]:
    """Generate story text and images from internet content."""
    script_runner = ScriptAndImageFromInternet(run_dir, client)
    result: dict[str, Any] = script_runner.run()
    logging.info(
        "Generated %d images for %d sentences",
        len(result["image_paths"]),
        len(result["sentences"]),
    )
    return result


def _process_story_paragraphs(run_dir: str, client, story_text: str) -> dict[str, Any]:
    """Split, summarise and render each paragraph into a video segment."""
    paragraph_processor = ParagraphProcessor(run_dir, client)
    process_result: dict[str, Any] = paragraph_processor.process(story_text)
    logging.info(
        "Created final video with %d segments", len(process_result["segment_paths"])
    )
    return process_result


def _copy_final_video(run_dir: str) -> Path:
    """Copy the intermediate video (`output_story_video.mp4`) to the final filename.

    Returns the path of the copied video, or the expected final path if the source
    file does not exist (no-op)."""
    output_video = Path(run_dir) / "output_story_video.mp4"
    final_video = Path(run_dir) / "final_story_video.mp4"
    if output_video.exists():
        shutil.copy(output_video, final_video)
        logging.info("Copied output video to final video path: %s", final_video)
    return final_video


def _build_success_response(
    script_result: dict[str, Any],
    process_result: dict[str, Any],
    final_video_path: Path,
) -> dict[str, Any]:
    """Create the success response dictionary returned by the pipeline."""
    return {
        "success": True,
        "script_result": script_result,
        "process_result": process_result,
        "final_video_path": final_video_path,
    }

def run_internet_content_pipeline(run_dir: str) -> dict:
    """Run the internet content generation pipeline.

    Fetches content from the internet, generates images, processes paragraphs,
    and creates a final video from the content.

    Args:
        run_dir: Directory to store all generated files

    Returns:
        dict: Dictionary with pipeline results containing:
            - success: Boolean indicating if the pipeline succeeded
            - script_result: Results from the script generation
            - process_result: Results from the paragraph processing
            - final_video_path: Path to the final video
            - error: Error message if success is False
    """
    logging.info("[Internet Pipeline] Starting internet content generation pipeline")

    client = get_openai_client()

    try:
        # 1. Generate script and images from internet content.
        script_result = _generate_script_and_images(run_dir, client)

        # 2. Unify story text into a single string for downstream processing.
        story_text: str | list[str] = script_result["story"]
        if isinstance(story_text, list):
            story_text = " ".join(story_text)

        # 3. Process paragraphs (TTS, slideshow, video segments …).
        process_result = _process_story_paragraphs(run_dir, client, story_text)

        # 4. Copy/rename the final video artefact.
        final_video = _copy_final_video(run_dir)

        logging.info(
            "[Internet Pipeline] Successfully generated content and created video"
        )

        return _build_success_response(script_result, process_result, final_video)
    except Exception as e:
        logging.exception("[Internet Pipeline] Unexpected error: %s", e)
        return {"success": False, "error": str(e)}
