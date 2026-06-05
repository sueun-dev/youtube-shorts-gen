import base64
import logging
import random
import time
from pathlib import Path
from typing import Any

import requests
from runwayml import RunwayML

from youtube_shorts_gen.utils.config import (
    RUNWAY_API_KEY,
    RUNWAY_ASPECT_RATIO,
    RUNWAY_CAMERA_MOVEMENTS,
    RUNWAY_DEFAULT_DURATION_SECONDS,
    RUNWAY_MAX_DURATION_SECONDS,
    RUNWAY_MAX_POLL_ATTEMPTS,
    RUNWAY_MODEL,
    RUNWAY_MOVEMENT_TYPES,
    RUNWAY_POLL_INTERVAL_SECONDS,
    RUNWAY_PROMPT_TEMPLATE,
    STORY_PROMPT_FILENAME,
)

# Download timeout for fetching the generated video (seconds).
_DOWNLOAD_TIMEOUT_SECONDS = 60


class VideoGenerator:
    def __init__(self, run_dir: str):
        """Initialize the video generator.

        Args:
            run_dir: Directory containing the image and prompt files and
                where the output video will be saved

        Raises:
            ValueError: If RUNWAY_API_KEY is not set
        """
        self.run_dir = Path(run_dir)
        if not RUNWAY_API_KEY:
            raise ValueError("RUNWAY_API_KEY is not set in environment variables")
        self.client = RunwayML(api_key=RUNWAY_API_KEY)

    def _image_to_data_uri(self, image_path: str) -> str:
        """Convert an image to a base64 data URI.

        Args:
            image_path: Path to the image file

        Returns:
            Data URI string with base64-encoded image data
        """
        ext = Path(image_path).suffix[1:].lower()
        mime = f"image/{'jpeg' if ext == 'jpg' else ext}"

        with open(image_path, "rb") as f:
            encoded = base64.b64encode(f.read()).decode("utf-8")

        return f"data:{mime};base64,{encoded}"

    def _create_runway_prompt(self, story_text: str) -> str:
        """Create a specialized prompt for Runway following Gen-3 Alpha guidelines.

        Args:
            story_text: The original story text

        Returns:
            A formatted prompt optimized for Runway's Gen-3 Alpha model.
        """
        # Extract key subjects from the story.
        words = story_text.split()

        # Extract meaningful nouns and descriptive words for the subject.
        potential_subjects = [w for w in words if len(w) > 4 and w.isalpha()][:5]

        # Select a subject or use a default realistic subject.
        subject = (
            random.choice(potential_subjects)
            if potential_subjects
            else "person in natural setting"
        )

        # If subject is too short, make it more descriptive.
        if len(subject) < 10:
            subject = f"detailed {subject} with realistic features"

        # Select camera movement and movement type from the configured lists.
        camera_movement = random.choice(RUNWAY_CAMERA_MOVEMENTS)
        movement_type = random.choice(RUNWAY_MOVEMENT_TYPES)

        # Format the prompt template following the Gen-3 Alpha structure:
        # [camera movement]: [establishing scene]. [additional details].
        runway_prompt = RUNWAY_PROMPT_TEMPLATE.format(
            camera_movement=camera_movement,
            subject=subject,
            movement_type=movement_type,
        )

        # Save the Runway prompt to a file.
        runway_prompt_path = self.run_dir / "runway_prompt.txt"
        runway_prompt_path.write_text(runway_prompt, encoding="utf-8")
        logging.info("Created realistic Runway prompt: %s", runway_prompt_path)

        return runway_prompt

    def generate(
        self,
        image_path: str | None = None,
        prompt_text: str | None = None,
        duration: float = RUNWAY_DEFAULT_DURATION_SECONDS,
    ) -> str:
        """Generate a video from an image and prompt using RunwayML.

        Args:
            image_path: Path to the image file. If None, uses default path
                in run_dir.
            prompt_text: Text to use for the prompt. If None, reads from
                default file.
            duration: Target duration of the final video in seconds. Note: the
                actual generated video will be RUNWAY_MAX_DURATION_SECONDS long,
                and must be looped externally to match this target duration.

        Returns:
            Path to the generated video file, or "" if generation does not
            complete.

        Raises:
            FileNotFoundError: If image or prompt files are missing
            RuntimeError: If video generation fails
        """
        # Generate a unique identifier for this video.
        self.current_video_id = int(time.time() * 1000) % 10000
        # Handle default paths for backward compatibility.
        if image_path is None:
            resolved_image_path = self.run_dir / "story_image.png"
        else:
            resolved_image_path = Path(image_path)

        if not resolved_image_path.exists():
            raise FileNotFoundError(f"Image file not found: {resolved_image_path}")

        # Get prompt text either from parameter or default file.
        if prompt_text is None:
            prompt_path = self.run_dir / STORY_PROMPT_FILENAME
            if not prompt_path.exists():
                raise FileNotFoundError(f"Prompt file not found: {prompt_path}")
            story_text = prompt_path.read_text(encoding="utf-8").strip()
        else:
            story_text = prompt_text

        # Create a specialized Runway prompt.
        runway_prompt = self._create_runway_prompt(story_text)

        # Convert image to data URI.
        image_data_uri = self._image_to_data_uri(str(resolved_image_path))

        # Send request to RunwayML with the fixed API duration limit. The target
        # duration is only logged here; the caller loops the video to match it.
        api_duration = int(RUNWAY_MAX_DURATION_SECONDS)
        logging.info(
            "Requesting Runway video with fixed duration: %ds (target: %ss)",
            api_duration,
            duration,
        )
        # Build kwargs as a plain dict so the model/ratio strings (which are
        # configurable) are not constrained by the SDK's Literal type hints.
        create_kwargs: dict[str, Any] = {
            "model": RUNWAY_MODEL,
            "prompt_image": image_data_uri,
            "prompt_text": runway_prompt,
            "ratio": RUNWAY_ASPECT_RATIO,
            "duration": api_duration,
        }
        response = self.client.image_to_video.create(**create_kwargs)

        task_id = getattr(response, "id", None)
        if not task_id:
            raise RuntimeError("RunwayML did not return a task id")

        logging.info("RunwayML task started: Task ID = %s", task_id)

        task = None
        for _ in range(RUNWAY_MAX_POLL_ATTEMPTS):
            time.sleep(RUNWAY_POLL_INTERVAL_SECONDS)
            task = self.client.tasks.retrieve(task_id)
            if task.status in {"SUCCEEDED", "FAILED"}:
                break
            logging.info(
                "Current status: %s, checking again in %d seconds...",
                task.status,
                RUNWAY_POLL_INTERVAL_SECONDS,
            )
        else:
            logging.warning(
                "RunwayML task %s did not finish within %d poll attempts",
                task_id,
                RUNWAY_MAX_POLL_ATTEMPTS,
            )
            return ""

        if task.status == "FAILED":
            raise RuntimeError(f"Video generation failed: status = {task.status}")

        output = getattr(task, "output", None)
        if not isinstance(output, list) or not output:
            raise RuntimeError("Video generation succeeded but returned no output")

        video_url = output[0]
        output_path = self._download_video(video_url)
        return str(output_path)

    def _download_video(self, video_url: str) -> Path:
        """Download a video from URL and save it to the run directory.

        Args:
            video_url: URL of the video to download

        Returns:
            Path to the downloaded video file

        Raises:
            ConnectionError: If download fails
        """
        # Create videos directory if it doesn't exist.
        videos_dir = self.run_dir / "videos"
        videos_dir.mkdir(exist_ok=True)

        # Use the current_video_id to create a unique filename.
        output_path = videos_dir / f"runway_video_{self.current_video_id}.mp4"

        response = requests.get(
            video_url, stream=True, timeout=_DOWNLOAD_TIMEOUT_SECONDS
        )
        if response.status_code == 200:
            with open(output_path, "wb") as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)
            logging.info("Video download complete: %s", output_path)
            return output_path
        raise ConnectionError(
            f"Video download failed: status code = {response.status_code}"
        )
