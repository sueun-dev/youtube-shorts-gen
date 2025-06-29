"""YouTube transcript pipeline for YouTube shorts generation."""

import logging
import os
import shutil
from pathlib import Path
from typing import Any

from youtube_shorts_gen.content.transcript_segmenter import TranscriptSegmenter
from youtube_shorts_gen.media.tts_generator import TTSGenerator
from youtube_shorts_gen.media.video_assembler import VideoAssembler
from youtube_shorts_gen.utils.config import MAX_RUNWAY_VIDEOS_PER_SEGMENT
from youtube_shorts_gen.scrapers.youtube_transcript_scraper import (
    YouTubeTranscriptScraper,
)
from youtube_shorts_gen.utils.openai_client import (
    get_openai_client,  # remain for run function to create client
)
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


def _segment_transcript(client, transcript: str) -> list[str]:
    """Segment transcript text into smaller script segments."""
    segmenter = TranscriptSegmenter(client)
    return segmenter.segment_transcript(transcript)


def _write_segment_files(run_dir: str, script_segments: list[str]) -> Path:
    """Write each script segment to its own text file; returns directory path."""
    segments_dir = Path(run_dir) / "segments"
    segments_dir.mkdir(exist_ok=True)
    for i, segment in enumerate(script_segments):
        (segments_dir / f"segment_{i+1}.txt").write_text(segment, encoding="utf-8")
    logging.info(
        "[YouTube Transcript Pipeline] %d script segments created", len(script_segments)
    )
    return segments_dir


def _copy_segment_video(src: Path, dst: Path) -> None:
    """Copy a generated segment video to its destination path."""
    if src.exists():
        shutil.copy(src, dst)


def _write_mapping_file(
    run_dir: str,
    youtube_url: str,
    script_segments: list[str],
    final_video_paths: list[str]
) -> None:
    """Write a human-readable mapping file summarising segments and videos."""
    mapping_path = Path(run_dir) / "segments_mapping.txt"
    with mapping_path.open("w", encoding="utf-8") as f:
        f.write(f"YouTube URL: {youtube_url}\n")
        f.write(f"Total segments: {len(script_segments)}\n\n")
        for i, segment in enumerate(script_segments):
            f.write(f"--- Segment {i+1} ---\n")
            f.write(f"{segment[:200]}...\n")
            if i < len(final_video_paths):
                f.write(f"Video: {os.path.basename(final_video_paths[i])}\n")
            f.write("\n")


def _build_success_response(
    segments: list[str],
    segment_results: list[dict[str, Any]],
    final_video_paths: list[str]
) -> dict[str, Any]:
    return {
        "success": True,
        "segments": segments,
        "segment_results": segment_results,
        "final_video_paths": final_video_paths,
    }


# Re-export previously defined helper for clarity

def generate_image_for_line(client, text: str, output_path: Path) -> str:
    """Generate an image for a given transcript line using shared utility."""
    prompt = f"정치 뉴스 장면: {text}"
    return generate_openai_image(client, prompt, output_path)


def process_segment_into_video(
    client, segment: str, segment_dir: Path, segment_index: int
) -> dict[str, Any]:
    """Each segment is processed to create a video.
    
    Args:
        segment: Segment text
        segment_dir: Segment directory path
        segment_index: Segment index
        
    Returns:
        Segment processing result dictionary
    """
    try:
        
        # Image save directory creation
        images_dir = segment_dir / "images"
        images_dir.mkdir(exist_ok=True)
        
        # Audio save directory creation
        audio_dir = segment_dir / "audio"
        audio_dir.mkdir(exist_ok=True)
        
        # Videos save directory creation
        videos_dir = segment_dir / "videos"
        videos_dir.mkdir(exist_ok=True)
        
        # Segment split into lines
        lines = [line for line in segment.split('\n') if line.strip()]
        
        # Image, video, and TTS generation for each line
        image_paths: list[str] = []
        audio_paths: list[str] = []
        runway_video_paths: list[str] = []
        
        # Reuse a single TTS generator per segment for efficiency
        tts_generator = TTSGenerator(str(audio_dir), lang="ko")
        
        # Initialize Runway VideoGenerator
        from youtube_shorts_gen.media.runway import VideoGenerator
        video_generator = VideoGenerator(str(segment_dir))
        
        # Track the last successfully generated Runway video path for reuse
        last_runway_video_path = None
        
        for i, line in enumerate(lines):
            if not line.strip():
                continue
            
            # Generate image
            image_path = images_dir / f"line_{i+1}.png"
            image_result = generate_image_for_line(client, line, image_path)
            if not image_result:
                continue
            image_paths.append(image_result)
            
            # Generate TTS audio
            line_audio_path = audio_dir / f"line_{i+1}_audio.mp3"
            tts_generator.audio_path = line_audio_path
            audio_path = tts_generator.generate_from_text(line)
            if not audio_path:
                continue
            audio_paths.append(audio_path)
            
            # Generate dynamic video using Runway AI, but only up to the configured limit
            if i < MAX_RUNWAY_VIDEOS_PER_SEGMENT:
                try:
                    # Use the generated image and line text to create a dynamic video
                    runway_video_path = video_generator.generate(
                        image_path=image_result,
                        prompt_text=line,
                        duration=5.0  # Default duration, will be adjusted to match audio
                    )
                    if runway_video_path:
                        runway_video_paths.append(runway_video_path)
                        last_runway_video_path = runway_video_path
                        logging.info(f"Generated Runway video for line {i+1}: {runway_video_path}")
                except Exception as e:
                    logging.error(f"Runway video generation failed for line {i+1}: {e}")
                    # If Runway video generation fails, we'll fall back to using the static image
            elif last_runway_video_path:
                # For lines beyond the limit, reuse the last successfully generated Runway video
                runway_video_paths.append(last_runway_video_path)
                logging.info(f"Reusing last Runway video for line {i+1} (limit reached): {last_runway_video_path}")
            else:
                # If no Runway videos were successfully generated, we'll fall back to static images
                logging.info(f"Using static image for line {i+1} (no Runway videos available)")
        
        # Video assembly with Runway videos or fallback to static images
        video_assembler = VideoAssembler(str(segment_dir))
        segment_videos = []
        
        # Create segment video for each line, using Runway videos when available
        for i in range(min(len(image_paths), len(audio_paths))):
            # If we have a Runway video for this line, use it instead of the static image
            if i < len(runway_video_paths) and os.path.exists(runway_video_paths[i]):
                segment_video = video_assembler.create_segment_video_with_runway(
                    video_path=runway_video_paths[i],
                    audio_path=audio_paths[i],
                    index=i
                )
                logging.info(f"Created segment video with Runway for line {i+1}")
            else:
                # Fallback to static image if Runway video generation failed or wasn't attempted
                segment_video = video_assembler.create_segment_video(
                    image_path=image_paths[i],
                    audio_path=audio_paths[i],
                    index=i
                )
                logging.info(f"Created segment video with static image for line {i+1}")
                
            if segment_video:
                segment_videos.append(segment_video)
        
        # Segment video concatenation
        if segment_videos:
            final_video = video_assembler.concatenate_segments(
                segment_videos, 
                final_video_name=f"segment_{segment_index}_video.mp4"
            )
        else:
            final_video = ""
            logging.error(f"Segment {segment_index} video creation failed")
        
        return {
            "segment_index": segment_index,
            "segment_text": segment,
            "image_paths": image_paths,
            "audio_paths": audio_paths,
            "runway_video_paths": runway_video_paths,
            "segment_videos": segment_videos,
            "final_video": final_video,
            "runway_videos_generated": min(len(lines), MAX_RUNWAY_VIDEOS_PER_SEGMENT),
            "runway_videos_reused": max(0, len(runway_video_paths) - min(len(lines), MAX_RUNWAY_VIDEOS_PER_SEGMENT))
        }
    except Exception as e:
        logging.error(f"Segment processing error: {e}")
        return {
            "segment_index": segment_index,
            "error": str(e)
        }


# === Public API ===

def run_youtube_transcript_pipeline(run_dir: str, youtube_url: str) -> dict[str, Any]:
    """YouTube transcript content creation pipeline execution.

    YouTube video transcript is fetched, split into short scripts, 
    and each segment's each line is used to generate images and TTS, 
    and then images and TTS are synchronized to create videos.

    Args:
        run_dir: Directory to save all generated files
        youtube_url: YouTube video URL to fetch transcript

    Returns:
        dict: Pipeline result dictionary:
            - success: Pipeline success
            - segments: Created script segments list
            - segment_results: Each segment processing result
            - final_video_paths: Final video paths list
            - error: Error message if success is False
    """
    logging.info("[YouTube Transcript Pipeline] YouTube transcript pipeline started")

    client = get_openai_client()

    try:
        # 1. Fetch transcript
        scraper = YouTubeTranscriptScraper()
        transcript = scraper.fetch_transcript(youtube_url)

        if not transcript:
            return {
                "success": False,
                "error": f"Failed to fetch transcript from YouTube URL: {youtube_url}"
            }
        
        # 2. Save transcript to disk
        _save_transcript(run_dir, transcript)

        # 3. Segment transcript
        script_segments = _segment_transcript(client, transcript)

        if not script_segments:
            return {
                "success": False,
                "error": "Failed to split transcript into short scripts"
            }
        
        # 4. Write segment files
        _write_segment_files(run_dir, script_segments)
        
        segment_results: list[dict[str, Any]] = []
        final_video_paths: list[str] = []
        
        for i, segment in enumerate(script_segments):
            logging.info(
                f"[YouTube Transcript Pipeline] Processing segment "
                f"{i+1}/{len(script_segments)}"
            )
            
            segment_dir = Path(run_dir) / f"segment_{i+1}"
            segment_dir.mkdir(exist_ok=True)
            
            with open(segment_dir / "story.txt", "w", encoding="utf-8") as f:
                f.write(segment)
            
            with open(segment_dir / "story_prompt.txt", "w", encoding="utf-8") as f:
                f.write(segment)
            
            result = process_segment_into_video(client, segment, segment_dir, i + 1)
            segment_results.append(result)

            if (fv := result.get("final_video")):
                src_path = Path(fv)
                main_final = Path(run_dir) / f"segment_{i+1}_video.mp4"
                _copy_segment_video(src_path, main_final)
                final_video_paths.append(str(main_final))
                # Also duplicate inside the segment dir for upload convenience
                _copy_segment_video(src_path, segment_dir / "final_story_video.mp4")
                logging.info(
                    "[YouTube Transcript Pipeline] Segment %d video creation completed",
                    i + 1
                )
        
        # 5. Write mapping file for human inspection
        _write_mapping_file(run_dir, youtube_url, script_segments, final_video_paths)
        
        logging.info(
            f"[YouTube Transcript Pipeline] {len(script_segments)} segments processed"
        )
        
        return _build_success_response(
            script_segments, segment_results, final_video_paths
        )
    except Exception as e:
        logging.exception(f"[YouTube Transcript Pipeline] Failed: {e}")
        return {"success": False, "error": str(e)}
