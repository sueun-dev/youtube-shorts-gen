"""AI content pipeline for YouTube shorts generation."""

import logging
from pathlib import Path

from youtube_shorts_gen.content.script_and_image_gen import ScriptAndImageGenerator
from youtube_shorts_gen.media.runway import VideoGenerator
from youtube_shorts_gen.media.tts_generator import TTSGenerator
from youtube_shorts_gen.media.video_audio_sync import VideoAudioSyncer


def run_ai_content_pipeline(run_dir: str) -> dict:
    """
    Run the AI content generation pipeline.

    Args:
        run_dir: Directory to store all generated files

    Returns:
        Dictionary with pipeline results
    """
    logging.info("[AI Pipeline] Starting AI content generation pipeline")

    try:
        # Generate script and images using AI
        script = ScriptAndImageGenerator(run_dir)
        script_result = script.run()

        # Generate video using RunwayML
        video_generator = VideoGenerator(run_dir)
        video_result = video_generator.generate()

        # Generate TTS audio from the story
        tts_generator = TTSGenerator(run_dir)
        tts_result = tts_generator.generate_from_file()

        # Synchronize video with audio
        synchronizer = VideoAudioSyncer(run_dir)
        sync_result = synchronizer.sync()

        logging.info("[AI Pipeline] Successfully generated content and created video")

        return {
            "success": True,
            "script_result": script_result,
            "video_result": video_result,
            "tts_result": tts_result,
            "sync_result": sync_result,
            "final_video_path": Path(run_dir) / "final_story_video.mp4",
        }
    except Exception as e:
        logging.exception("[AI Pipeline] Failed: %s", e)
        return {"success": False, "error": str(e)}
