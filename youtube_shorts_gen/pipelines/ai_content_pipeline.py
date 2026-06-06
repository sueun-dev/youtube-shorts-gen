"""AI content pipeline for YouTube shorts generation."""

import logging
import shutil
from pathlib import Path
from typing import Any

from openai import OpenAI

from youtube_shorts_gen.content.script_and_image_gen import ScriptAndImageGenerator
from youtube_shorts_gen.media.runway import VideoGenerator
from youtube_shorts_gen.media.tts_generator import TTSGenerator
from youtube_shorts_gen.media.video_audio_sync import VideoAudioSyncer
from youtube_shorts_gen.utils.config import OUTPUT_VIDEO_FILENAME
from youtube_shorts_gen.utils.openai_client import get_openai_client

# === Helper functions (Single Responsibility) ===


def _generate_script_and_images(run_dir: str, client: OpenAI) -> dict[str, Any]:
    """Generate script and images using the chat and image models."""
    generator = ScriptAndImageGenerator(run_dir, client)
    result: dict[str, Any] = generator.run()
    logging.info(
        "[AI Pipeline] Generated %d images for story",
        len(result.get("image_paths", [])),
    )
    return result


def _generate_ai_video(run_dir: str) -> dict[str, Any]:
    """Generate a base video with Runway and stage it for synchronisation.

    Runway saves its clip under ``<run_dir>/videos/`` and returns that path, but
    the audio/video syncer reads ``<run_dir>/output_story_video.mp4``. Copy the
    clip to that expected location so the next step can find it.
    """
    video_generator = VideoGenerator(run_dir)
    video_path = video_generator.generate()
    if not video_path:
        raise RuntimeError("Runway returned no video (generation timed out)")
    staged_path = Path(run_dir) / OUTPUT_VIDEO_FILENAME
    shutil.copy(video_path, staged_path)
    logging.info("[AI Pipeline] Base video staged for sync: %s", staged_path)
    return {"video_path": str(staged_path)}


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


def run_ai_content_pipeline(run_dir: str) -> dict[str, Any]:
    """Run the AI content generation pipeline.

    Args:
        run_dir: Directory to store all generated files.

    Returns:
        Dictionary with pipeline results (always contains a ``success`` key).
    """
    logging.info("[AI Pipeline] Starting AI content generation pipeline")

    client = get_openai_client()

    try:
        script_result = _generate_script_and_images(run_dir, client)
        video_result = _generate_ai_video(run_dir)
        tts_path = _generate_tts(run_dir)
        final_video_path = _sync_video_audio(run_dir)

        logging.info("[AI Pipeline] Successfully generated content and created video")

        return _build_success_response(
            script_result, video_result, tts_path, final_video_path
        )
    except Exception as exc:
        logging.exception("[AI Pipeline] Failed")
        return {"success": False, "error": str(exc)}
