"""YouTube transcript pipeline: video transcript -> segmented narrated shorts."""

import logging
import shutil
from pathlib import Path
from typing import Any

from openai import OpenAI

from youtube_shorts_gen.content.transcript_segmenter import TranscriptSegmenter
from youtube_shorts_gen.media.runway import VideoGenerator
from youtube_shorts_gen.media.tts_generator import TTSGenerator
from youtube_shorts_gen.media.video_assembler import VideoAssembler
from youtube_shorts_gen.scrapers.youtube_transcript_scraper import (
    YouTubeTranscriptScraper,
)
from youtube_shorts_gen.utils.config import (
    FINAL_VIDEO_FILENAME,
    MAX_RUNWAY_VIDEOS_PER_SEGMENT,
    NEWS_SCENE_PROMPT_TEMPLATE,
    RUNWAY_DEFAULT_DURATION_SECONDS,
    STORY_PROMPT_FILENAME,
)
from youtube_shorts_gen.utils.openai_client import get_openai_client
from youtube_shorts_gen.utils.openai_image import (
    generate_image as generate_openai_image,
)

# === Helper functions (Single Responsibility) ===


def _save_transcript(run_dir: str, transcript: str) -> Path:
    """Save the full transcript to a file and return its path."""
    transcript_path = Path(run_dir) / "full_transcript.txt"
    transcript_path.write_text(transcript, encoding="utf-8")
    logging.info("[YouTube Transcript Pipeline] Transcript saved: %s", transcript_path)
    return transcript_path


def _segment_transcript(client: OpenAI, transcript: str) -> list[str]:
    """Segment transcript text into smaller script segments."""
    segmenter = TranscriptSegmenter(client)
    return segmenter.segment_transcript(transcript)


def _write_segment_files(run_dir: str, script_segments: list[str]) -> Path:
    """Write each script segment to its own text file; return the directory path."""
    segments_dir = Path(run_dir) / "segments"
    segments_dir.mkdir(exist_ok=True)
    for i, segment in enumerate(script_segments, start=1):
        (segments_dir / f"segment_{i}.txt").write_text(segment, encoding="utf-8")
    logging.info(
        "[YouTube Transcript Pipeline] %d script segments created", len(script_segments)
    )
    return segments_dir


def _copy_segment_video(src: Path, dst: Path) -> None:
    """Copy a generated segment video to its destination path if it exists."""
    if src.exists():
        shutil.copy(src, dst)


def _write_mapping_file(
    run_dir: str,
    youtube_url: str,
    script_segments: list[str],
    final_video_paths: list[str],
) -> None:
    """Write a human-readable mapping file summarising segments and videos."""
    mapping_path = Path(run_dir) / "segments_mapping.txt"
    with mapping_path.open("w", encoding="utf-8") as f:
        f.write(f"YouTube URL: {youtube_url}\n")
        f.write(f"Total segments: {len(script_segments)}\n\n")
        for i, segment in enumerate(script_segments):
            f.write(f"--- Segment {i + 1} ---\n")
            f.write(f"{segment[:200]}...\n")
            if i < len(final_video_paths):
                f.write(f"Video: {Path(final_video_paths[i]).name}\n")
            f.write("\n")


def _build_success_response(
    segments: list[str],
    segment_results: list[dict[str, Any]],
    final_video_paths: list[str],
) -> dict[str, Any]:
    return {
        "success": True,
        "segments": segments,
        "segment_results": segment_results,
        "final_video_paths": final_video_paths,
    }


def generate_image_for_line(client: OpenAI, text: str, output_path: Path) -> str:
    """Generate an image for a single transcript line."""
    prompt = NEWS_SCENE_PROMPT_TEMPLATE.format(text=text)
    return generate_openai_image(client, prompt, output_path)


def _generate_line_assets(
    client: OpenAI,
    lines: list[str],
    images_dir: Path,
    tts_generator: TTSGenerator,
    video_generator: VideoGenerator,
) -> tuple[list[str], list[str], list[str]]:
    """Generate an image, narration, and (optionally) a Runway video per line.

    Returns aligned-ish lists of (image paths, audio paths, runway video paths).
    Runway video generation is capped at ``MAX_RUNWAY_VIDEOS_PER_SEGMENT``; later
    lines reuse the last successful Runway clip.
    """
    image_paths: list[str] = []
    audio_paths: list[str] = []
    runway_video_paths: list[str] = []
    last_runway_video_path: str | None = None

    for i, line in enumerate(lines, start=1):
        image_path = images_dir / f"line_{i}.png"
        image_result = generate_image_for_line(client, line, image_path)
        if not image_result:
            continue
        image_paths.append(image_result)

        tts_generator.audio_path = tts_generator.run_dir / f"line_{i}_audio.mp3"
        audio_path = tts_generator.generate_from_text(line)
        if not audio_path:
            continue
        audio_paths.append(audio_path)

        if i <= MAX_RUNWAY_VIDEOS_PER_SEGMENT:
            try:
                runway_video_path = video_generator.generate(
                    image_path=image_result,
                    prompt_text=line,
                    duration=RUNWAY_DEFAULT_DURATION_SECONDS,
                )
            except Exception:
                logging.exception("Runway video generation failed for line %d", i)
                runway_video_path = ""
            if runway_video_path:
                runway_video_paths.append(runway_video_path)
                last_runway_video_path = runway_video_path
                logging.info("Generated Runway video for line %d", i)
        elif last_runway_video_path:
            runway_video_paths.append(last_runway_video_path)
            logging.info("Reusing last Runway video for line %d", i)
        else:
            logging.info("Using static image for line %d", i)

    return image_paths, audio_paths, runway_video_paths


def _assemble_segment_videos(
    video_assembler: VideoAssembler,
    image_paths: list[str],
    audio_paths: list[str],
    runway_video_paths: list[str],
) -> list[str]:
    """Build one video per line, preferring Runway clips over static images."""
    segment_videos: list[str] = []
    for i in range(min(len(image_paths), len(audio_paths))):
        if i < len(runway_video_paths) and Path(runway_video_paths[i]).exists():
            segment_video = video_assembler.create_segment_video_with_runway(
                video_path=runway_video_paths[i], audio_path=audio_paths[i], index=i
            )
            logging.info("Created segment video with Runway for line %d", i + 1)
        else:
            segment_video = video_assembler.create_segment_video(
                image_path=image_paths[i], audio_path=audio_paths[i], index=i
            )
            logging.info("Created segment video with static image for line %d", i + 1)
        if segment_video:
            segment_videos.append(segment_video)
    return segment_videos


def process_segment_into_video(
    client: OpenAI, segment: str, segment_dir: Path, segment_index: int
) -> dict[str, Any]:
    """Turn one script segment into a concatenated video; return a result dict."""
    try:
        images_dir = segment_dir / "images"
        images_dir.mkdir(exist_ok=True)
        audio_dir = segment_dir / "audio"
        audio_dir.mkdir(exist_ok=True)

        lines = [line for line in segment.split("\n") if line.strip()]
        tts_generator = TTSGenerator(str(audio_dir), lang="ko")
        video_generator = VideoGenerator(str(segment_dir))

        image_paths, audio_paths, runway_video_paths = _generate_line_assets(
            client, lines, images_dir, tts_generator, video_generator
        )

        video_assembler = VideoAssembler(str(segment_dir))
        segment_videos = _assemble_segment_videos(
            video_assembler, image_paths, audio_paths, runway_video_paths
        )

        if segment_videos:
            final_video = video_assembler.concatenate_segments(
                segment_videos, final_video_name=f"segment_{segment_index}_video.mp4"
            )
        else:
            final_video = ""
            logging.error("Segment %d video creation failed", segment_index)

        runway_generated = min(len(lines), MAX_RUNWAY_VIDEOS_PER_SEGMENT)
        return {
            "segment_index": segment_index,
            "segment_text": segment,
            "image_paths": image_paths,
            "audio_paths": audio_paths,
            "runway_video_paths": runway_video_paths,
            "segment_videos": segment_videos,
            "final_video": final_video,
            "runway_videos_generated": runway_generated,
            "runway_videos_reused": max(0, len(runway_video_paths) - runway_generated),
        }
    except Exception as exc:
        logging.exception("Segment %d processing error", segment_index)
        return {"segment_index": segment_index, "error": str(exc)}


# === Public API ===


def run_youtube_transcript_pipeline(run_dir: str, youtube_url: str) -> dict[str, Any]:
    """Run the YouTube-transcript content pipeline.

    Fetches a video's transcript, splits it into short scripts, and turns each
    segment into a narrated video (image + TTS per line, with optional Runway
    motion), then concatenates the per-line videos per segment.

    Args:
        run_dir: Directory to store all generated files.
        youtube_url: URL of the YouTube video to fetch the transcript from.

    Returns:
        Dictionary with pipeline results (always contains a ``success`` key).
    """
    logging.info("[YouTube Transcript Pipeline] Started for %s", youtube_url)

    try:
        # Fetching the transcript needs no OpenAI client, so do it first.
        scraper = YouTubeTranscriptScraper()
        transcript = scraper.fetch_transcript(youtube_url)
        if not transcript:
            return {
                "success": False,
                "error": f"Failed to fetch transcript from YouTube URL: {youtube_url}",
            }

        _save_transcript(run_dir, transcript)

        client = get_openai_client()
        script_segments = _segment_transcript(client, transcript)
        if not script_segments:
            return {
                "success": False,
                "error": "Failed to split transcript into short scripts",
            }

        _write_segment_files(run_dir, script_segments)

        segment_results: list[dict[str, Any]] = []
        final_video_paths: list[str] = []

        for i, segment in enumerate(script_segments, start=1):
            logging.info(
                "[YouTube Transcript Pipeline] Processing segment %d/%d",
                i,
                len(script_segments),
            )
            segment_dir = Path(run_dir) / f"segment_{i}"
            segment_dir.mkdir(exist_ok=True)
            (segment_dir / "story.txt").write_text(segment, encoding="utf-8")
            (segment_dir / STORY_PROMPT_FILENAME).write_text(segment, encoding="utf-8")

            result = process_segment_into_video(client, segment, segment_dir, i)
            segment_results.append(result)

            if fv := result.get("final_video"):
                src_path = Path(fv)
                main_final = Path(run_dir) / f"segment_{i}_video.mp4"
                _copy_segment_video(src_path, main_final)
                final_video_paths.append(str(main_final))
                _copy_segment_video(src_path, segment_dir / FINAL_VIDEO_FILENAME)
                logging.info("[YouTube Transcript Pipeline] Segment %d completed", i)

        _write_mapping_file(run_dir, youtube_url, script_segments, final_video_paths)
        logging.info(
            "[YouTube Transcript Pipeline] %d segments processed",
            len(script_segments),
        )
        return _build_success_response(
            script_segments, segment_results, final_video_paths
        )
    except Exception as exc:
        logging.exception("[YouTube Transcript Pipeline] Failed")
        return {"success": False, "error": str(exc)}
