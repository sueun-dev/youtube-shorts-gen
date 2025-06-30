import base64
import logging
import os
import random
import time
from pathlib import Path

import requests
from runwayml import RunwayML

from youtube_shorts_gen.utils.config import (
    RUNWAY_API_KEY,
    RUNWAY_CAMERA_MOVEMENTS,
    RUNWAY_MOVEMENT_TYPES,
    RUNWAY_PROMPT_TEMPLATE,
)

# Maximum duration supported by Runway API (in seconds)
RUNWAY_MAX_DURATION = 5  # Using 5 seconds to be safe (must be an integer)


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
        os.environ["RUNWAYML_API_SECRET"] = RUNWAY_API_KEY
        self.client = RunwayML()

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
            A formatted prompt optimized for Runway's Gen-3 Alpha model with realism
        """
        # Extract key subjects from the story
        words = story_text.split()
        
        # Extract meaningful nouns and descriptive words for the subject
        potential_subjects = [w for w in words if len(w) > 4 and w.isalpha()][:5]
        
        # Select a subject or use a default realistic subject
        subject = (
            random.choice(potential_subjects) if potential_subjects else "person in natural setting"
        )
        
        # Use descriptive, positive phrasing for the subject
        if len(subject) < 10:  # If subject is too short, make it more descriptive
            subject = f"detailed {subject} with realistic features"

        # Select camera movement and movement type from the updated lists
        camera_movement = random.choice(RUNWAY_CAMERA_MOVEMENTS)
        movement_type = random.choice(RUNWAY_MOVEMENT_TYPES)

        # Format the prompt template following the Gen-3 Alpha structure:
        # [camera movement]: [establishing scene]. [additional details].
        runway_prompt = RUNWAY_PROMPT_TEMPLATE.format(
            camera_movement=camera_movement,
            subject=subject,
            movement_type=movement_type
        )

        # Save the Runway prompt to a file
        runway_prompt_path = self.run_dir / "runway_prompt.txt"
        runway_prompt_path.write_text(runway_prompt, encoding="utf-8")
        logging.info("Created realistic Runway prompt: %s", runway_prompt_path)

        return runway_prompt

    def generate(self, image_path: str = None, prompt_text: str = None, duration: float = 5.0) -> str:
        """Generate a video from an image and prompt using RunwayML.

        Args:
            image_path: Path to the image file. If None, uses default path in run_dir.
            prompt_text: Text to use for the prompt. If None, reads from default file.
            duration: Target duration of the final video in seconds. Default is 5.0 seconds.
                Note: The actual generated video will be RUNWAY_MAX_DURATION seconds long,
                and will need to be looped externally to match this target duration.

        Returns:
            Path to the generated video file (of RUNWAY_MAX_DURATION length).

        Raises:
            FileNotFoundError: If image or prompt files are missing
            RuntimeError: If video generation fails
        """
        # Generate a unique identifier for this video
        self.current_video_id = int(time.time() * 1000) % 10000
        # Handle default paths for backward compatibility
        if image_path is None:
            image_path = self.run_dir / "story_image.png"
        else:
            image_path = Path(image_path)

        if not image_path.exists():
            raise FileNotFoundError(f"Image file not found: {image_path}")
            
        # Get prompt text either from parameter or default file
        if prompt_text is None:
            prompt_path = self.run_dir / "story_prompt.txt"
            if not prompt_path.exists():
                raise FileNotFoundError(f"Prompt file not found: {prompt_path}")
            story_text = prompt_path.read_text(encoding="utf-8").strip()
        else:
            story_text = prompt_text

        # Create a specialized Runway prompt
        runway_prompt = self._create_runway_prompt(story_text)

        # Convert image to data URI
        image_data_uri = self._image_to_data_uri(str(image_path))

        # Send request to RunwayML with fixed duration (Runway API limit)
        # The target duration parameter is stored but not used here
        # The caller will need to loop the video to match the target duration
        logging.info(f"Requesting Runway video with fixed duration: {RUNWAY_MAX_DURATION}s (target: {duration}s)")
        response = self.client.image_to_video.create(
            model="gen3a_turbo",
            prompt_image=image_data_uri,
            prompt_text=runway_prompt,
            ratio="768:1280",
            duration=RUNWAY_MAX_DURATION,
        )

        logging.info("RunwayML task started: Task ID = %s", response.id)
        time.sleep(20)

        while True:
            task = self.client.tasks.retrieve(response.id)
            if task.status in {"SUCCEEDED", "FAILED"}:
                break
            logging.info(
                "Current status: %s, checking again in 20 seconds...", task.status
            )
            time.sleep(20)

        if task.status == "SUCCEEDED" and task.output:
            video_url = task.output[0]
            output_path = self._download_video(video_url)
            return str(output_path)
        else:
            raise RuntimeError(f"Video generation failed: status = {task.status}")

    def _download_video(self, video_url: str) -> Path:
        """Download a video from URL and save it to the run directory.

        Args:
            video_url: URL of the video to download

        Returns:
            Path to the downloaded video file

        Raises:
            ConnectionError: If download fails
        """
        # Create videos directory if it doesn't exist
        videos_dir = self.run_dir / "videos"
        videos_dir.mkdir(exist_ok=True)
        
        # Use the current_video_id to create a unique filename
        output_path = videos_dir / f"runway_video_{self.current_video_id}.mp4"

        response = requests.get(video_url, stream=True)
        if response.status_code == 200:
            with open(output_path, "wb") as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)
            logging.info("Video download complete: %s", output_path)
            return output_path
        else:
            raise ConnectionError(
                f"Video download failed: status code = {response.status_code}"
            )
