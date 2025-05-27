import base64
import logging
from pathlib import Path
from typing import Literal

from youtube_shorts_gen.content.story_prompt_gen import generate_dynamic_prompt
from youtube_shorts_gen.utils.config import (
    IMAGE_PROMPT_TEMPLATE,
    OPENAI_CHAT_MODEL,
    OPENAI_IMAGE_MODEL,
    OPENAI_IMAGE_SIZE,
)
from youtube_shorts_gen.utils.openai_client import get_openai_client


class ScriptAndImageGenerator:
    def __init__(self, run_dir: str, temperature: float = 0.9, max_tokens: int = 300):
        """Initialize the script generator with configuration parameters.

        Args:
            run_dir: Directory to save generated content
            temperature: Creativity level for text generation (0.0-1.0)
            max_tokens: Maximum length of generated text
        """
        self.run_dir = Path(run_dir)
        self.client = get_openai_client()
        self.prompt_path = self.run_dir / "story_prompt.txt"
        self.image_path = self.run_dir / "story_image.png"
        self.temperature = temperature
        self.max_tokens = max_tokens

    def generate_story(self) -> str:
        """Generate a story from OpenAI chat model and save to file.

        Returns:
            The generated story text

        Raises:
            ValueError: If the API response is invalid or empty
        """
        response = self.client.chat.completions.create(
            model=OPENAI_CHAT_MODEL,
            messages=[{"role": "user", "content": generate_dynamic_prompt()}],
            temperature=self.temperature,
            max_tokens=self.max_tokens,
        )

        # Validate API response
        if not response.choices:
            raise ValueError("OpenAI API returned empty choices list")

        if not response.choices[0].message:
            raise ValueError("OpenAI API returned empty message")

        content = response.choices[0].message.content
        if not content:
            raise ValueError("OpenAI API returned empty content")

        # Safe to call strip() as we've verified content is not None
        story = content.strip()

        # Save story to file
        self.prompt_path.write_text(story, encoding="utf-8")
        logging.info("Saved story: %s", self.prompt_path)

        return story

    def generate_image(self, story: str) -> None:
        """Generate an image from the story using DALL·E and save to file.

        Args:
            story: The story text to base the image on

        Raises:
            ValueError: If the API response is invalid or empty
        """
        image_prompt = IMAGE_PROMPT_TEMPLATE.format(story=story)

        # Convert string constants to literal types expected by the OpenAI API
        size_value: Literal["1024x1024", "1792x1024", "1024x1792"] = "1024x1024"
        if OPENAI_IMAGE_SIZE == "1024x1024":
            size_value = "1024x1024"
        elif OPENAI_IMAGE_SIZE == "1792x1024":
            size_value = "1792x1024"
        elif OPENAI_IMAGE_SIZE == "1024x1792":
            size_value = "1024x1792"

        quality_value: Literal["standard", "hd", "low"] = "low"

        result = self.client.images.generate(
            model=OPENAI_IMAGE_MODEL,
            prompt=image_prompt,
            size=size_value,
            quality=quality_value,
            n=1,
        )

        # Validate API response
        if not result.data or not result.data[0].b64_json:
            raise ValueError("OpenAI API returned empty response for image generation")

        image_data = result.data[0].b64_json

        # Save image to file
        self.image_path.write_bytes(base64.b64decode(image_data))
        logging.info("Saved image: %s", self.image_path)

    def run(self) -> None:
        """Execute the full generation pipeline: story and image."""
        story = self.generate_story()
        self.generate_image(story)
