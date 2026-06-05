import logging
from pathlib import Path
from typing import Any

from openai import OpenAI

from youtube_shorts_gen.content.story_prompt_gen import generate_dynamic_prompt
from youtube_shorts_gen.utils.config import (
    CHAT_MAX_TOKENS_DEFAULT,
    CHAT_TEMPERATURE_DEFAULT,
    IMAGE_PROMPT_TEMPLATE,
    OPENAI_CHAT_MODEL,
    STORY_PROMPT_FILENAME,
)
from youtube_shorts_gen.utils.openai_image import (
    generate_image as generate_openai_image,
)


class ScriptAndImageGenerator:
    def __init__(
        self,
        run_dir: str,
        client: OpenAI,
        temperature: float = CHAT_TEMPERATURE_DEFAULT,
        max_tokens: int = CHAT_MAX_TOKENS_DEFAULT,
    ) -> None:
        """Initialize the script generator with configuration parameters.

        Args:
            run_dir: Directory to save generated content
            client: Configured OpenAI client used for API calls
            temperature: Creativity level for text generation (0.0-1.0)
            max_tokens: Maximum length of generated text
        """
        self.run_dir = Path(run_dir)
        self.client = client
        self.prompt_path = self.run_dir / STORY_PROMPT_FILENAME
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
            ValueError: If the image generation fails
        """
        image_prompt = IMAGE_PROMPT_TEMPLATE.format(story=story)

        saved_path = generate_openai_image(self.client, image_prompt, self.image_path)
        if not saved_path:
            raise ValueError("Image generation failed – see logs for details")

        logging.info("Saved image: %s", saved_path)

    def run(self) -> dict[str, Any]:
        """Execute the full generation pipeline: story then image.

        Returns:
            A dict with the generated ``story`` text and the ``image_paths``
            list (a single image for this generator).
        """
        story = self.generate_story()
        self.generate_image(story)
        return {"story": story, "image_paths": [str(self.image_path)]}
