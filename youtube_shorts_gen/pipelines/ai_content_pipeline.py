"""AI content pipeline for YouTube shorts generation."""

import logging
from typing import Any

from youtube_shorts_gen.content.script_and_image_gen import ScriptAndImageGenerator
from youtube_shorts_gen.media.runway import VideoGenerator
from youtube_shorts_gen.media.tts_generator import TTSGenerator
from youtube_shorts_gen.media.video_audio_sync import VideoAudioSyncer
from youtube_shorts_gen.utils.openai_client import get_openai_client

# === Helper functions (Single Responsibility) ===

def _generate_script_and_images(run_dir: str, client) -> dict[str, Any]:
    """Generate script and images using the LLM and DALLE."""
    generator = ScriptAndImageGenerator(run_dir, client)
    result: dict[str, Any] = generator.run()
    logging.info(
        "[AI Pipeline] Generated %d images for story",
        len(result.get("image_paths", []))
    )
    return result


def _generate_ai_video(run_dir: str) -> dict[str, Any]:
    """Generate a base video from the images using Runway."""
    video_generator = VideoGenerator(run_dir)
    result: dict[str, Any] = video_generator.generate()
    logging.info("[AI Pipeline] Base video generated via Runway")
    return result


def _generate_tts(run_dir: str) -> str:
    """Generate TTS narration for the story text file inside run_dir."""
    tts_generator = TTSGenerator(run_dir)
    audio_path: str = tts_generator.generate_from_file()
    logging.info("[AI Pipeline] TTS audio generated: %s", audio_path)
    return audio_path


def _sync_video_audio(run_dir: str) -> str:
    """Synchronise the generated video and audio returning final video path."""
    syncer = VideoAudioSyncer(run_dir)
    final_path: str = syncer.sync()
    logging.info("[AI Pipeline] Video and audio synchronised: %s", final_path)
    return final_path


def _build_success_response(
    script_result: dict[str, Any],
    video_result: dict[str, Any],
    tts_path: str,
    final_video_path: str,
) -> dict[str, Any]:
    return {
        "success": True,
        "script_result": script_result,
        "video_result": video_result,
        "tts_result": tts_path,
        "final_video_path": final_video_path,
    }


# === Public API ===

def run_ai_content_pipeline(run_dir: str) -> dict:
    """
    Run the AI content generation pipeline.

    Args:
        run_dir: Directory to store all generated files

    Returns:
        Dictionary with pipeline results
    """
    logging.info("[AI Pipeline] Starting AI content generation pipeline")

    client = get_openai_client()

    try:
        # 1. Script and image generation
        script_result = _generate_script_and_images(run_dir, client)

        # 2. Video generation
        video_result = _generate_ai_video(run_dir)

        # 3. TTS generation
        tts_path = _generate_tts(run_dir)

        # 4. Video-audio synchronisation
        final_video_path = _sync_video_audio(run_dir)

        logging.info("[AI Pipeline] Successfully generated content and created video")

        return _build_success_response(
            script_result, video_result, tts_path, final_video_path
        )
    except Exception as e:
        logging.exception("[AI Pipeline] Failed: %s", e)
        return {"success": False, "error": str(e)}
