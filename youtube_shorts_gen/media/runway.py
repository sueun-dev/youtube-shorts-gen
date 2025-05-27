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
        """Create a specialized prompt for Runway following their guidelines.

        Args:
            story_text: The original story text

        Returns:
            A formatted prompt optimized for Runway's Gen-3 Alpha model
        """
        # Extract key subjects from the story
        words = story_text.split()
        # Take a few random words to use as potential subjects
        potential_subjects = [w for w in words if len(w) > 4 and w.isalpha()][:5]
        subject = (
            random.choice(potential_subjects) if potential_subjects else "surreal scene"
        )

        # Create a Runway-optimized prompt
        camera_movement = random.choice(RUNWAY_CAMERA_MOVEMENTS)
        movement_type = random.choice(RUNWAY_MOVEMENT_TYPES)

        # Format the prompt template
        runway_prompt = RUNWAY_PROMPT_TEMPLATE.format(subject=subject)

        # Replace the default camera movement and movement type with random ones
        runway_prompt = runway_prompt.replace("Tracking shot", camera_movement)
        runway_prompt = runway_prompt.replace("warps and undulates", movement_type)

        # Save the Runway prompt to a file
        runway_prompt_path = self.run_dir / "runway_prompt.txt"
        runway_prompt_path.write_text(runway_prompt, encoding="utf-8")
        logging.info("Created specialized Runway prompt: %s", runway_prompt_path)

        return runway_prompt

    def generate(self) -> None:
        """Generate a video from an image and prompt using RunwayML.

        The method reads the image and prompt from the run directory,
        sends a request to RunwayML, and saves the resulting video.

        Raises:
            FileNotFoundError: If image or prompt files are missing
            RuntimeError: If video generation fails
        """
        image_path = self.run_dir / "story_image.png"
        prompt_path = self.run_dir / "story_prompt.txt"

        if not image_path.exists():
            raise FileNotFoundError(f"Image file not found: {image_path}")
        if not prompt_path.exists():
            raise FileNotFoundError(f"Prompt file not found: {prompt_path}")

        # Read the original story prompt
        story_text = prompt_path.read_text(encoding="utf-8").strip()

        # Create a specialized Runway prompt
        runway_prompt = self._create_runway_prompt(story_text)

        # Convert image to data URI
        image_data_uri = self._image_to_data_uri(str(image_path))

        # Send request to RunwayML
        response = self.client.image_to_video.create(
            model="gen3a_turbo",
            prompt_image=image_data_uri,
            prompt_text=runway_prompt,
            ratio="768:1280",
            duration=5,
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
            self._download_video(video_url)
        else:
            raise RuntimeError(f"Video generation failed: status = {task.status}")

    def _download_video(self, video_url: str) -> None:
        """Download a video from URL and save it to the run directory.

        Args:
            video_url: URL of the video to download

        Raises:
            ConnectionError: If download fails
        """
        output_path = self.run_dir / "output_story_video.mp4"

        response = requests.get(video_url, stream=True)
        if response.status_code == 200:
            with open(output_path, "wb") as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)
            logging.info("Video download complete: %s", output_path)
        else:
            raise ConnectionError(
                f"Video download failed: status code = {response.status_code}"
            )
