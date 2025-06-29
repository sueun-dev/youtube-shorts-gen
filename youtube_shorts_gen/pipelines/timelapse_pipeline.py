"""Pipeline for generating time-lapse videos showing evolution over time.

This module provides functionality to create time-lapse videos that show the
evolution of a subject (e.g., a car model) over a range of years using
OpenAI's multi-turn image generation for natural transitions.
"""

import logging
import os
import shutil
import tempfile
from pathlib import Path
from typing import List, Tuple, Optional

from openai import OpenAI

from youtube_shorts_gen.media.video_assembler import VideoAssembler
from youtube_shorts_gen.utils.image_utils import overlay_text_on_images
from youtube_shorts_gen.utils.frame_interpolator import interpolate_between
from youtube_shorts_gen.utils.openai_image import generate_sequential_images
from youtube_shorts_gen.upload.upload_to_youtube import YouTubeUploader

# Constants
TIMELAPSE_IMAGES_DIR = "timelapse_images"
TIMELAPSE_VIDEO_FILENAME = "timelapse_video.mp4"
DEFAULT_FPS = 4  # Adjust to control speed of time-lapse
DEFAULT_TRANSITION_DURATION = 1.0  # Duration of transition between images in seconds (increased)
DEFAULT_FRAME_DURATION = 1.0  # Duration each frame is shown in seconds
DEFAULT_TRANSITION_TYPE = "dissolve"  # Transition effect: fade, dissolve, wiperight, etc.


def run_timelapse_pipeline(
    run_dir: str,
    client: OpenAI,
    subject_prompt: str,
    start_year: int,
    end_year: int,
    fps: int = DEFAULT_FPS,
    transition_duration: float = DEFAULT_TRANSITION_DURATION,
    frame_duration: float = DEFAULT_FRAME_DURATION,
    transition_type: str = DEFAULT_TRANSITION_TYPE,
    music_path: Optional[str] = None,
    upload_to_youtube: bool = True,
    video_title: Optional[str] = None,
    video_description: Optional[str] = None,
    num_inter_frames: int = 32,
    inter_frame_duration: float = 0.03,
    main_frame_duration: float = 1.0,
) -> str:

    """Run the time-lapse video generation pipeline.

    Args:
        run_dir: Directory to store generated files
        client: OpenAI client
        subject_prompt: Base prompt describing the subject (e.g., "Red Ferrari Car")
        start_year: Starting year for the time-lapse
        end_year: Ending year for the time-lapse
        fps: Frames per second for the output video
        upload_to_youtube: Whether to upload the final video to YouTube
        video_title: Title for the YouTube video (optional)
        video_description: Description for the YouTube video (optional)

    Returns:
        Path to the final video file
    """
    logging.info(
        "Starting time-lapse pipeline for '%s' from %d to %d",
        subject_prompt,
        start_year,
        end_year,
    )

    # Create run directory if it doesn't exist
    run_path = Path(run_dir)
    run_path.mkdir(parents=True, exist_ok=True)

    # Create images directory
    images_dir = run_path / TIMELAPSE_IMAGES_DIR
    images_dir.mkdir(exist_ok=True)

    # Generate prompts and paths for each year
    years = list(range(start_year, end_year + 1))
    prompts, output_paths = _generate_year_prompts(subject_prompt, years, images_dir)

    # Generate images with natural transitions
    logging.info("Generating %d sequential images...", len(prompts))
    image_paths = generate_sequential_images(client, prompts, output_paths)
    
    # Overlay year text on images
    overlay_dir = run_path / "timelapse_images_annotated"
    image_paths = overlay_text_on_images(image_paths, [str(y) for y in years], overlay_dir)

    # Insert interpolated frames between each consecutive pair for smoother motion
    enriched_image_paths: List[str] = []
    frame_durations: List[float] = []
    for idx in range(len(image_paths) - 1):
        # Original yearly image
        enriched_image_paths.append(image_paths[idx])
        frame_durations.append(main_frame_duration)
        # Interpolated frames
        inter_frames = interpolate_between(
            image_paths[idx],
            image_paths[idx + 1],
            num_inter_frames=num_inter_frames,
            output_dir=overlay_dir,
        )
        enriched_image_paths.extend(inter_frames)
        frame_durations.extend([inter_frame_duration] * len(inter_frames))
    # Append last original image
    enriched_image_paths.append(image_paths[-1])
    frame_durations.append(main_frame_duration)
    image_paths = enriched_image_paths

    # Check if all images were generated successfully
    if "" in image_paths:
        failed_count = image_paths.count("")
        logging.warning("%d images failed to generate", failed_count)
        # Filter out failed generations
        image_paths = [path for path in image_paths if path]
    
    if not image_paths:
        error_msg = "No images were successfully generated"
        logging.error(error_msg)
        raise RuntimeError(error_msg)




        # Create video from images with smooth transitions (custom durations)
    video_path = _create_timelapse_video(
        run_path,
        enriched_image_paths,
        fps,
        transition_duration,
        frame_duration,
        transition_type,
        music_path,
        frame_durations,
    )
    
    # Upload to YouTube if requested
    if upload_to_youtube and video_path:
        _upload_to_youtube(
            video_path, 
            title=video_title or f"Evolution of {subject_prompt} ({start_year}-{end_year})",
            description=video_description or f"Time-lapse showing the evolution of {subject_prompt} from {start_year} to {end_year}."
        )
    
    return video_path


def _generate_year_prompts(
    base_prompt: str, years: List[int], images_dir: Path
) -> Tuple[List[str], List[Path]]:
    """Generate prompts and output paths for each year.
    
    Args:
        base_prompt: Base prompt describing the subject
        years: List of years to generate images for
        images_dir: Directory to store the images
        
    Returns:
        Tuple of (prompts, output_paths)
    """
    prompts = []
    output_paths = []
    
    for year in years:
        # Create a prompt that includes the year
        prompt = (
            f"Generate a high-quality front view image of {base_prompt} as it appeared in {year}. "
            f"Include full details clearly visible from the front, such as design, style, and key features. "
            f"The image should capture the defining characteristics representative of the {year} version of {base_prompt}."
        )
        
        # Define the output path for this year's image
        output_path = images_dir / f"{year}.png"
        
        prompts.append(prompt)
        output_paths.append(output_path)
    
    return prompts, output_paths


def _create_timelapse_video(
    run_dir: Path,
    image_paths: List[str],
    fps: int,
    transition_duration: float,
    frame_duration: float,
    transition_type: str,
    music_path: Optional[str],
    frame_durations: Optional[List[float]] = None,
) -> str:
    """Create a time-lapse video from the generated images with smooth transitions.
    
    Args:
        run_dir: Directory to store the video
        image_paths: List of paths to the generated images
        fps: Frames per second for the output video
        transition_duration: Duration of transition between images in seconds
        frame_duration: Duration each frame is shown in seconds
        transition_type: Type of transition effect to use (fade, dissolve, wiperight, etc.)
        
    Returns:
        Path to the created video
    """
    logging.info("Creating time-lapse video with smooth transitions from %d images", len(image_paths))
    
    video_assembler = VideoAssembler(str(run_dir))
    
    # Use the new smooth timelapse method for better transitions
    video_path = video_assembler.create_smooth_timelapse(
        image_paths,
        output_filename=TIMELAPSE_VIDEO_FILENAME,
        transition_duration=transition_duration,
        frame_duration=frame_duration,
        transition_type=transition_type,
        music_path=music_path,
        frame_durations=frame_durations,
    )
    
    if not video_path:
        logging.error("Failed to create time-lapse video")
        return ""
    
    logging.info("Time-lapse video created: %s", video_path)
    return video_path


def _upload_to_youtube(
    video_path: str, 
    title: str, 
    description: str,
    tags: Optional[List[str]] = None
) -> bool:
    """Upload the video to YouTube.
    
    Args:
        video_path: Path to the video file
        title: Title for the YouTube video
        description: Description for the YouTube video
        tags: Tags for the YouTube video
        
    Returns:
        True if upload was successful, False otherwise
    """
    if not os.path.exists(video_path):
        logging.error("Video file does not exist: %s", video_path)
        return False
    
    try:
        # Create a temporary directory for the upload
        with tempfile.TemporaryDirectory() as temp_dir:
            # Copy the video to the temp directory with the expected name
            temp_video_path = os.path.join(temp_dir, "final_story_video.mp4")
            shutil.copy(video_path, temp_video_path)
            
            # Create a story prompt file with the title and description
            temp_prompt_path = os.path.join(temp_dir, "story_prompt.txt")
            with open(temp_prompt_path, "w", encoding="utf-8") as f:
                f.write(f"{title}\n\n{description}")
            
            # Initialize the uploader with the temp directory
            uploader = YouTubeUploader(
                run_dir=temp_dir,
                default_tags=tags or ["timelapse", "evolution", "ai-generated"]
            )
            
            # Upload the video
            video_url = uploader.upload()
            
            if video_url:
                logging.info("Video successfully uploaded to YouTube: %s", video_url)
                return True
            else:
                logging.error("Failed to upload video to YouTube")
                return False
            
    except Exception as e:
        logging.error("Error uploading to YouTube: %s", e)
        return False
