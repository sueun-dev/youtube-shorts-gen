"""Internet-content pipeline: web story -> images -> narrated video segments."""

import logging
from pathlib import Path
from typing import Any

from mutagen.mp3 import MP3

from youtube_shorts_gen.content.script_and_image_from_internet import (
    ScriptAndImageFromInternet,
)
from youtube_shorts_gen.media.paragraph_tts import ParagraphTTS
from youtube_shorts_gen.media.runway import VideoGenerator
from youtube_shorts_gen.media.video_assembler import VideoAssembler
from youtube_shorts_gen.utils.config import FINAL_VIDEO_FILENAME
from youtube_shorts_gen.utils.openai_client import get_openai_client

# Fallback narration duration (seconds) when an audio file cannot be measured.
_DEFAULT_AUDIO_DURATION_SECONDS = 5.0


def _generate_tts_and_get_durations(
    run_dir: str, sentences: list[str]
) -> tuple[list[str], list[float]]:
    """Generate TTS audio for each sentence and measure their durations.

    Args:
        run_dir: Directory to store generated audio files.
        sentences: Sentences to convert to speech.

    Returns:
        A tuple of (audio file paths, audio durations in seconds).
    """
    tts_generator = ParagraphTTS(run_dir)
    audio_paths = tts_generator.generate_for_paragraphs(sentences)

    audio_durations: list[float] = []
    for audio_path in audio_paths:
        if not audio_path:
            # Keep durations index-aligned with audio_paths; empty entries are
            # skipped downstream.
            audio_durations.append(0.0)
            continue
        try:
            duration = MP3(audio_path).info.length
            logging.info("Audio file %s has duration %.2fs", audio_path, duration)
        except Exception as exc:
            # Any failure to read the MP3 falls back to a default duration.
            logging.warning(
                "Failed to measure duration for %s (%s); using default %.1fs",
                audio_path,
                exc,
                _DEFAULT_AUDIO_DURATION_SECONDS,
            )
            duration = _DEFAULT_AUDIO_DURATION_SECONDS
        audio_durations.append(duration)

    return audio_paths, audio_durations


def _build_one_segment(
    index: int,
    sentence: str,
    image_path: str,
    audio_path: str,
    duration: float,
    video_generator: VideoGenerator,
    video_assembler: VideoAssembler,
    segments_dir: Path,
    looped_videos_dir: Path,
) -> str | None:
    """Build a single audio-synced video segment, returning its path or ``None``."""
    logging.info(
        "Generating video for segment %d with target duration %.2fs", index, duration
    )
    base_video_path = video_generator.generate(
        image_path=image_path, prompt_text=sentence, duration=duration
    )

    looped_video_path = str(looped_videos_dir / f"looped_segment_{index}.mp4")
    silent_video_path = video_assembler.create_looped_video(
        input_video_path=base_video_path,
        target_duration=duration,
        output_video_path=looped_video_path,
    )
    if not silent_video_path:
        logging.warning(
            "Failed to loop segment %d; using the original short video", index
        )
        silent_video_path = base_video_path

    output_segment_path = str(segments_dir / f"segment_{index}.mp4")
    merged_path = video_assembler.merge_audio_video(
        video_path=silent_video_path,
        audio_path=audio_path,
        output_path=output_segment_path,
    )
    if merged_path:
        logging.info("Created synchronized segment %d: %s", index, merged_path)
        return merged_path

    logging.error("Failed to merge audio and video for segment %d", index)
    return None


def _generate_synced_video_segments(
    run_dir: str,
    sentences: list[str],
    image_paths: list[str],
    audio_paths: list[str],
    audio_durations: list[float],
) -> list[str]:
    """Generate Runway videos matched to audio durations and merge each with audio.

    Args:
        run_dir: Directory to store generated videos.
        sentences: Sentences used as Runway prompts.
        image_paths: Image path per sentence.
        audio_paths: Audio path per sentence.
        audio_durations: Duration per audio file.

    Returns:
        Paths to the final synchronised video segments.
    """
    video_generator = VideoGenerator(run_dir)
    video_assembler = VideoAssembler(run_dir)

    segments_dir = Path(run_dir) / "segments"
    segments_dir.mkdir(exist_ok=True)
    looped_videos_dir = Path(run_dir) / "looped_videos"
    looped_videos_dir.mkdir(exist_ok=True)

    segment_paths: list[str] = []
    rows = zip(sentences, image_paths, audio_paths, audio_durations, strict=False)
    for i, (sentence, image_path, audio_path, duration) in enumerate(rows, start=1):
        if not audio_path:
            logging.warning("Skipping segment %d: TTS produced no audio", i)
            continue
        try:
            merged_path = _build_one_segment(
                i,
                sentence,
                image_path,
                audio_path,
                duration,
                video_generator,
                video_assembler,
                segments_dir,
                looped_videos_dir,
            )
            if merged_path:
                segment_paths.append(merged_path)
        except Exception:
            logging.exception("Failed to create segment %d", i)

    return segment_paths


def _concatenate_video_segments(run_dir: str, segment_paths: list[str]) -> str:
    """Concatenate all video segments into a single final video.

    Args:
        run_dir: Directory to store the final video.
        segment_paths: Paths to the video segments.

    Returns:
        Path to the final concatenated video.
    """
    video_assembler = VideoAssembler(run_dir)
    final_video_path = video_assembler.concatenate_segments(
        segment_paths, final_video_name=FINAL_VIDEO_FILENAME
    )
    logging.info(
        "Concatenated %d segments into final video: %s",
        len(segment_paths),
        final_video_path,
    )
    return final_video_path


def run_internet_content_pipeline(run_dir: str) -> dict[str, Any]:
    """Run the internet-content generation pipeline.

    Fetches a story from the web, generates an image per sentence, creates a
    Runway video per sentence, narrates each with TTS, and assembles a final,
    audio-synced video.

    Args:
        run_dir: Directory to store all generated files.

    Returns:
        Dictionary with pipeline results (always contains a ``success`` key).
    """
    logging.info("[Internet Pipeline] Starting internet content pipeline")

    client = get_openai_client()

    try:
        script_runner = ScriptAndImageFromInternet(run_dir, client)
        script_result: dict[str, Any] = script_runner.run()
        sentences: list[str] = script_result.get("sentences", [])
        image_paths: list[str] = script_result.get("image_paths", [])
        logging.info(
            "Generated %d images for %d sentences", len(image_paths), len(sentences)
        )

        audio_paths, audio_durations = _generate_tts_and_get_durations(
            run_dir, sentences
        )
        segment_paths = _generate_synced_video_segments(
            run_dir, sentences, image_paths, audio_paths, audio_durations
        )
        final_video_path = _concatenate_video_segments(run_dir, segment_paths)

        logging.info("[Internet Pipeline] Successfully created video")

        return {
            "success": True,
            "script_result": script_result,
            "audio_paths": audio_paths,
            "segment_paths": segment_paths,
            "final_video_path": final_video_path,
        }
    except Exception as exc:
        logging.exception("[Internet Pipeline] Unexpected error")
        return {"success": False, "error": str(exc)}
