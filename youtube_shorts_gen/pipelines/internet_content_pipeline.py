import logging
from pathlib import Path
from typing import Any, Tuple

from mutagen.mp3 import MP3
from openai import OpenAI

from youtube_shorts_gen.content.script_and_image_from_internet import (
    ScriptAndImageFromInternet,
)
from youtube_shorts_gen.media.paragraph_tts import ParagraphTTS
from youtube_shorts_gen.media.runway import VideoGenerator
from youtube_shorts_gen.media.video_assembler import VideoAssembler
from youtube_shorts_gen.utils.openai_client import get_openai_client




def _generate_tts_and_get_durations(run_dir: str, sentences: list[str]) -> Tuple[list[str], list[float]]:
    """Generate TTS audio for each sentence and measure their durations.
    
    Args:
        run_dir: Directory to store generated audio files
        sentences: List of sentences to convert to speech
        
    Returns:
        Tuple containing:
            - List of paths to generated audio files
            - List of durations for each audio file in seconds
    """
    tts_generator = ParagraphTTS(run_dir)
    audio_paths = tts_generator.generate_for_paragraphs(sentences)
    
    # Measure duration of each audio file
    audio_durations = []
    for audio_path in audio_paths:
        try:
            # Use mutagen to get audio duration
            audio = MP3(audio_path)
            duration = audio.info.length
            audio_durations.append(duration)
            logging.info(f"Audio file {audio_path} has duration: {duration} seconds")
        except Exception as e:
            # Fallback to a default duration if we can't read the file
            logging.warning(f"Failed to get duration for {audio_path}: {e}. Using default.")
            audio_durations.append(5.0)  # Default 5 seconds
    
    return audio_paths, audio_durations


def _generate_synced_video_segments(
    run_dir: str,
    sentences: list[str],
    image_paths: list[str],
    audio_paths: list[str],
    audio_durations: list[float]
) -> list[str]:
    """Generate videos with Runway that match audio durations and merge them.
    
    Args:
        run_dir: Directory to store generated videos
        sentences: List of sentences (used as prompts for video generation)
        image_paths: List of paths to images for each sentence
        audio_paths: List of paths to audio files for each sentence
        audio_durations: List of durations for each audio file
        
    Returns:
        List of paths to the final synchronized video segments
    """
    video_generator = VideoGenerator(run_dir)
    video_assembler = VideoAssembler(run_dir)
    segment_paths = []
    
    # Create output directories
    segments_dir = Path(run_dir) / "segments"
    segments_dir.mkdir(exist_ok=True)
    looped_videos_dir = Path(run_dir) / "looped_videos"
    looped_videos_dir.mkdir(exist_ok=True)
    
    for i, (sentence, image_path, audio_path, duration) in enumerate(
        zip(sentences, image_paths, audio_paths, audio_durations)
    ):
        try:
            # Generate base silent video with Runway (will be fixed duration, e.g., 4-5 seconds)
            logging.info(f"Generating video for segment {i+1} with target duration {duration}s")
            base_video_path = video_generator.generate(
                image_path=image_path,
                prompt_text=sentence,
                duration=duration  # This is now just the target duration, Runway will generate a shorter video
            )
            
            # Create a looped video that matches the audio duration
            looped_video_path = str(looped_videos_dir / f"looped_segment_{i+1}.mp4")
            silent_video_path = video_assembler.create_looped_video(
                input_video_path=base_video_path,
                target_duration=duration,
                output_video_path=looped_video_path
            )
            
            # If looping failed, use the original video (it will be shorter than audio)
            if not silent_video_path:
                logging.warning(f"Failed to create looped video for segment {i+1}, using original short video instead")
                silent_video_path = base_video_path
            
            # Combine video with audio
            output_segment_path = str(segments_dir / f"segment_{i+1}.mp4")
            
            # Use VideoAssembler to merge audio and video
            # The -shortest flag in ffmpeg will ensure the final segment matches the audio duration
            merged_path = video_assembler.merge_audio_video(
                video_path=silent_video_path,
                audio_path=audio_path,
                output_path=output_segment_path
            )
            
            if merged_path:
                segment_paths.append(merged_path)
                logging.info(f"Created synchronized segment {i+1}: {merged_path}")
            else:
                logging.error(f"Failed to merge audio and video for segment {i+1}")
            
        except Exception as e:
            logging.error(f"Failed to create segment {i+1}: {e}")
    
    return segment_paths


def _concatenate_video_segments(run_dir: str, segment_paths: list[str]) -> str:
    """Concatenate all video segments into a final video.
    
    Args:
        run_dir: Directory to store the final video
        segment_paths: List of paths to video segments
        
    Returns:
        Path to the final concatenated video
    """
    video_assembler = VideoAssembler(run_dir)
    final_video_path = video_assembler.concatenate_segments(
        segment_paths, final_video_name="final_story_video.mp4"
    )
    
    logging.info(f"Successfully concatenated {len(segment_paths)} segments into final video: {final_video_path}")
    return final_video_path


def run_internet_content_pipeline(run_dir: str) -> dict[str, Any]:
    """Run the enhanced internet content generation pipeline with Runway videos.

    Fetches content from the internet, generates images, creates dynamic videos with Runway,
    adds TTS audio, and assembles a final video with perfect audio-video synchronization.

    Args:
        run_dir: Directory to store all generated files

    Returns:
        dict[str, Any]: Dictionary with pipeline results containing:
            - success (bool): Boolean indicating if the pipeline succeeded
            - script_result (dict): Results from the script generation
            - audio_paths (list[str]): Paths to generated audio files
            - segment_paths (list[str]): Paths to synchronized video segments
            - final_video_path (str): Path to the final video
            - error (str, optional): Error message if success is False
    """
    logging.info("[Internet Pipeline]")

    client = get_openai_client()

    try:
        # 1. Generate script and images from internet content
        script_runner = ScriptAndImageFromInternet(run_dir, client)
        script_result: dict[str, Any] = script_runner.run()
        logging.info(
            "Generated %d images for %d sentences",
            len(script_result["image_paths"]),
            len(script_result["sentences"]),
        )
        
        story_text = script_result["story"]
        sentences = script_result["sentences"]
        image_paths = script_result["image_paths"]
        
        if isinstance(story_text, list):
            story_text = " ".join(story_text)
        
        # 2. Generate TTS audio and get exact durations
        audio_paths, audio_durations = _generate_tts_and_get_durations(run_dir, sentences)
        
        # 3. Generate synchronized videos with Runway and merge with audio
        segment_paths = _generate_synced_video_segments(
            run_dir, sentences, image_paths, audio_paths, audio_durations
        )
        
        # 4. Concatenate all segments into final video
        final_video_path = _concatenate_video_segments(run_dir, segment_paths)
        
        logging.info("[Internet Pipeline] Successfully generated dynamic content and created video")
        
        return {
            "success": True,
            "script_result": script_result,
            "audio_paths": audio_paths,
            "segment_paths": segment_paths,
            "final_video_path": final_video_path,
        }
    except Exception as e:
        logging.exception("[Internet Pipeline] Unexpected error: %s", e)
        return {"success": False, "error": str(e)}
