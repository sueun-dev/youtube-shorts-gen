"""Internet content pipeline for YouTube shorts generation."""

import logging
import shutil
from pathlib import Path

from youtube_shorts_gen.content.script_and_image_from_internet import (
    ScriptAndImageFromInternet,
)
from youtube_shorts_gen.media.paragraph_processor import ParagraphProcessor


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

    try:
        script = ScriptAndImageFromInternet(run_dir)
        result = script.run()
        logging.info(
            "Generated %d images for %d sentences",
            len(result["image_paths"]),
            len(result["sentences"]),
        )

        story_text = result["story"]
        paragraph_processor = ParagraphProcessor(run_dir)
        process_result = paragraph_processor.process(story_text)

        logging.info(
            "Created final video with %d segments", len(process_result["segment_paths"])
        )

        # Copy from output_story_video.mp4 to final_story_video.mp4 for consistency
        output_video = Path(run_dir) / "output_story_video.mp4"
        final_video = Path(run_dir) / "final_story_video.mp4"
        if output_video.exists():
            shutil.copy(output_video, final_video)
            logging.info("Copied output video to final video path: %s", final_video)

        logging.info(
            "[Internet Pipeline] Successfully generated content and created video"
        )

        return {
            "success": True,
            "script_result": result,
            "process_result": process_result,
            "final_video_path": final_video,
        }
    except requests.RequestException as e:
        # Handle network/API related errors
        logging.exception("[Internet Pipeline] Network error: %s", e)
        return {"success": False, "error": f"Network error: {str(e)}"}
    except (ValueError, KeyError) as e:
        # Handle data processing errors
        logging.exception("[Internet Pipeline] Data processing error: %s", e)
        return {"success": False, "error": f"Data processing error: {str(e)}"}
    except OSError as e:
        # Handle file operations errors
        logging.exception("[Internet Pipeline] File operation error: %s", e)
        return {"success": False, "error": f"File operation error: {str(e)}"}
    except Exception as e:
        # Fallback for unexpected errors
        logging.exception("[Internet Pipeline] Unexpected error: %s", e)
        return {"success": False, "error": str(e)}
