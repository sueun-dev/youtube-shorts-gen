"""Pipeline for generating time-lapse videos showing evolution over time.

Creates a vertical Short that shows how a subject (e.g. a car model) evolves
across a range of years, using OpenAI image generation for each year and frame
interpolation for smooth transitions.
"""

import logging
import shutil
import tempfile
from pathlib import Path

from openai import OpenAI

from youtube_shorts_gen.media.video_assembler import VideoAssembler
from youtube_shorts_gen.upload.upload_to_youtube import YouTubeUploader
from youtube_shorts_gen.utils.config import (
    FINAL_VIDEO_FILENAME,
    STORY_PROMPT_FILENAME,
)
from youtube_shorts_gen.utils.frame_interpolator import interpolate_between
from youtube_shorts_gen.utils.image_utils import overlay_text_on_images
from youtube_shorts_gen.utils.openai_image import generate_sequential_images

# Output locations.
TIMELAPSE_IMAGES_DIR = "timelapse_images"
TIMELAPSE_ANNOTATED_DIR = "timelapse_images_annotated"
TIMELAPSE_VIDEO_FILENAME = "timelapse_video.mp4"

# Playback defaults.
DEFAULT_FPS = 4
DEFAULT_TRANSITION_DURATION = 1.0
DEFAULT_FRAME_DURATION = 1.0
DEFAULT_TRANSITION_TYPE = "dissolve"
DEFAULT_NUM_INTER_FRAMES = 3
DEFAULT_INTER_FRAME_DURATION = 0.033  # ~30 fps for the interpolated frames
DEFAULT_MAIN_FRAME_DURATION = 0.5

_TIMELAPSE_DEFAULT_TAGS = ["timelapse", "evolution", "ai-generated"]

_YEAR_PROMPT_TEMPLATE = (
    "Generate a high-quality front view image of {subject} as it appeared in "
    "{year}. Include full details clearly visible from the front, such as design, "
    "style, and key features. The image should capture the defining "
    "characteristics representative of the {year} version of {subject}."
)


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
    music_path: str | None = None,
    upload_to_youtube: bool = True,
    video_title: str | None = None,
    video_description: str | None = None,
    num_inter_frames: int = DEFAULT_NUM_INTER_FRAMES,
    inter_frame_duration: float = DEFAULT_INTER_FRAME_DURATION,
    main_frame_duration: float = DEFAULT_MAIN_FRAME_DURATION,
) -> str:
    """Run the time-lapse video generation pipeline.

    Args:
        run_dir: Directory to store generated files.
        client: An initialised OpenAI client.
        subject_prompt: Subject to depict (e.g. "Red Ferrari Car").
        start_year: First year in the time-lapse.
        end_year: Last year in the time-lapse.
        fps: Frames per second for the output video.
        transition_duration: Cross-fade duration between frames (seconds).
        frame_duration: Default time each frame is shown (seconds).
        transition_type: FFmpeg xfade transition name.
        music_path: Optional background music file.
        upload_to_youtube: Whether to upload the final video.
        video_title: Optional YouTube title.
        video_description: Optional YouTube description.
        num_inter_frames: Interpolated frames inserted between yearly images.
        inter_frame_duration: Display time for each interpolated frame (seconds).
        main_frame_duration: Display time for each yearly image (seconds).

    Returns:
        Path to the final video file, or ``""`` on failure.
    """
    logging.info(
        "Starting time-lapse pipeline for '%s' from %d to %d",
        subject_prompt,
        start_year,
        end_year,
    )

    run_path = Path(run_dir)
    images_dir = run_path / TIMELAPSE_IMAGES_DIR
    images_dir.mkdir(parents=True, exist_ok=True)
    overlay_dir = run_path / TIMELAPSE_ANNOTATED_DIR

    years = list(range(start_year, end_year + 1))
    prompts, output_paths = _generate_year_prompts(subject_prompt, years, images_dir)

    logging.info("Generating %d sequential images...", len(prompts))
    image_paths = generate_sequential_images(client, prompts, output_paths)
    image_paths = overlay_text_on_images(
        image_paths, [str(y) for y in years], overlay_dir
    )

    enriched_paths, frame_durations = _build_enriched_frames(
        image_paths,
        overlay_dir,
        num_inter_frames=num_inter_frames,
        inter_frame_duration=inter_frame_duration,
        main_frame_duration=main_frame_duration,
    )

    if not enriched_paths:
        raise RuntimeError("No images were successfully generated")

    video_path = _create_timelapse_video(
        run_path,
        enriched_paths,
        fps,
        transition_duration,
        frame_duration,
        transition_type,
        music_path,
        frame_durations,
    )

    if upload_to_youtube and video_path:
        title = video_title or (
            f"Evolution of {subject_prompt} ({start_year}-{end_year})"
        )
        description = video_description or (
            f"Time-lapse showing the evolution of {subject_prompt} "
            f"from {start_year} to {end_year}."
        )
        _upload_to_youtube(video_path, title=title, description=description)

    return video_path


def _generate_year_prompts(
    base_prompt: str, years: list[int], images_dir: Path
) -> tuple[list[str], list[Path]]:
    """Build the per-year image prompts and their output paths."""
    prompts = [
        _YEAR_PROMPT_TEMPLATE.format(subject=base_prompt, year=year) for year in years
    ]
    output_paths = [images_dir / f"{year}.png" for year in years]
    return prompts, output_paths


def _build_enriched_frames(
    image_paths: list[str],
    overlay_dir: Path,
    *,
    num_inter_frames: int,
    inter_frame_duration: float,
    main_frame_duration: float,
) -> tuple[list[str], list[float]]:
    """Insert interpolated frames between consecutive yearly images.

    Returns aligned lists of frame paths and per-frame display durations, with
    any failed (empty-string) image paths removed.
    """
    enriched_paths: list[str] = []
    frame_durations: list[float] = []

    for idx in range(len(image_paths) - 1):
        enriched_paths.append(image_paths[idx])
        frame_durations.append(main_frame_duration)
        inter_frames = interpolate_between(
            image_paths[idx],
            image_paths[idx + 1],
            num_inter_frames=num_inter_frames,
            output_dir=overlay_dir,
        )
        enriched_paths.extend(inter_frames)
        frame_durations.extend([inter_frame_duration] * len(inter_frames))

    if image_paths:
        enriched_paths.append(image_paths[-1])
        frame_durations.append(main_frame_duration)

    # Drop any frames whose generation failed, keeping durations aligned.
    pairs = zip(enriched_paths, frame_durations, strict=True)
    cleaned = [(p, d) for p, d in pairs if p]
    failed = len(enriched_paths) - len(cleaned)
    if failed:
        logging.warning("%d frames failed to generate and were skipped", failed)
    if not cleaned:
        return [], []

    paths, durations = zip(*cleaned, strict=True)
    return list(paths), list(durations)


def _create_timelapse_video(
    run_dir: Path,
    image_paths: list[str],
    fps: int,
    transition_duration: float,
    frame_duration: float,
    transition_type: str,
    music_path: str | None,
    frame_durations: list[float] | None = None,
) -> str:
    """Render the time-lapse video from the enriched frame list."""
    logging.info(
        "Creating time-lapse video with smooth transitions from %d images",
        len(image_paths),
    )
    video_assembler = VideoAssembler(str(run_dir))
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
    tags: list[str] | None = None,
) -> bool:
    """Upload the time-lapse video to YouTube. Returns ``True`` on success."""
    if not Path(video_path).exists():
        logging.error("Video file does not exist: %s", video_path)
        return False

    try:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            shutil.copy(video_path, temp_path / FINAL_VIDEO_FILENAME)
            (temp_path / STORY_PROMPT_FILENAME).write_text(
                f"{title}\n\n{description}", encoding="utf-8"
            )
            uploader = YouTubeUploader(
                run_dir=temp_dir, default_tags=tags or _TIMELAPSE_DEFAULT_TAGS
            )
            video_url = uploader.upload()

        if video_url:
            logging.info("Video successfully uploaded to YouTube: %s", video_url)
            return True
        logging.error("Failed to upload video to YouTube")
        return False
    except (OSError, shutil.Error):
        logging.exception("Error uploading to YouTube")
        return False
