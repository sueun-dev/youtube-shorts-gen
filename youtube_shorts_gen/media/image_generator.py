import base64
import logging
from pathlib import Path

from openai import OpenAI  # Assuming OpenAI client is passed or initialized

from youtube_shorts_gen.utils.config import (
    OPENAI_IMAGE_MODEL,
    OPENAI_IMAGE_SIZE,
)


class ImageGenerator:
    """Generates images for text prompts using DALL·E."""

    def __init__(self, run_dir: str, openai_client: OpenAI):
        """Initialize the image generator.

        Args:
            run_dir: Directory to save generated images.
            openai_client: An instance of the OpenAI client.
        """
        self.run_dir = Path(run_dir)
        self.client = openai_client
        self.images_dir = (
            self.run_dir / "images"
        )  # Consistent with ParagraphProcessor's usage
        self.images_dir.mkdir(parents=True, exist_ok=True)

    def generate_image_for_prompt(
        self, prompt: str, filename_prefix: str, index: int
    ) -> str:
        """Generate an image for a given prompt using DALL·E.

        Args:
            prompt: The text prompt for image generation.
            filename_prefix: Prefix for the image filename (e.g., 'paragraph').
            index: Index for the image filename (e.g., for paragraph_1.png).

        Returns:
            Path to the generated image, or empty string if failed.
        """
        # Construct a detailed image prompt, can be further customized
        # The original prompt was very specific, retaining its structure for now
        detailed_prompt = f"Ultra-realistic cinematic photograph of {prompt}, captured with a full-frame DSLR camera, 85mm lens at f/1.4 aperture, golden hour lighting, shallow depth of field, high dynamic range, 8K resolution, natural color grading, film grain texture, --ar 16:9 --v 5"

        try:
            logging.info(
                f"Generating image for prompt (index {index+1}): {prompt[:100]}..."
            )
            result = self.client.images.generate(
                model=OPENAI_IMAGE_MODEL,
                prompt=detailed_prompt,
                size=OPENAI_IMAGE_SIZE,  # Ensure this is a valid size like "1024x1024"
                quality="standard",  # Using 'standard' instead of 'low' for potentially better results
                response_format="b64_json",  # Explicitly request b64_json
                n=1,
            )

            if not result.data or not result.data[0].b64_json:
                logging.error(
                    f"OpenAI API returned no image data for prompt (index {index+1})."
                )
                raise ValueError(
                    "OpenAI API returned empty response for image generation"
                )

            image_data_b64 = result.data[0].b64_json
            image_path = self.images_dir / f"{filename_prefix}_{index + 1}.png"

            with open(image_path, "wb") as f:
                f.write(base64.b64decode(image_data_b64))

            logging.info(
                "Successfully generated image %s for index %d.", image_path, index + 1
            )
            return str(image_path)

        except Exception as e:
            logging.error("Error generating image for index %d: %s", index + 1, e)
            return ""

    def generate_images_for_prompts(
        self, prompts: list[str], filename_prefix: str = "segment"
    ) -> list[str]:
        """Generate an image for each prompt in a list.

        Args:
            prompts: A list of text prompts.
            filename_prefix: Prefix for the image filenames.

        Returns:
            A list of paths to the generated images. Skips failures.
        """
        image_paths = []
        for i, prompt_text in enumerate(prompts):
            # Use a cleaned-up version of the prompt text if it's very long for logging/display
            short_prompt_for_logging = (
                (prompt_text[:70] + "...") if len(prompt_text) > 70 else prompt_text
            )
            logging.info(
                f"Processing prompt {i+1}/{len(prompts)}: '{short_prompt_for_logging}'"
            )

            image_path = self.generate_image_for_prompt(prompt_text, filename_prefix, i)
            if image_path:
                image_paths.append(image_path)
            else:
                logging.warning(f"Failed to generate image for prompt {i+1}. Skipping.")
        return image_paths
