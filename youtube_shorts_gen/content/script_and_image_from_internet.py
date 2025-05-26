"""Module for fetching stories from the internet for YouTube shorts."""

import base64
import logging
import random
import re
from pathlib import Path

from youtube_shorts_gen.scrapers.scraper_factory import ScraperFactory
from youtube_shorts_gen.utils.config import (
    IMAGE_PROMPT_TEMPLATE,
    OPENAI_IMAGE_MODEL,
    OPENAI_IMAGE_QUALITY,
    OPENAI_IMAGE_SIZE,
)
from youtube_shorts_gen.utils.openai_client import get_openai_client


class ScriptAndImageFromInternet:
    """Fetches short stories or content from the internet for YouTube shorts and generates images for each sentence."""

    def __init__(self, run_dir: str):
        """Initialize the internet script fetcher.

        Args:
            run_dir: Directory to save fetched content
        """
        self.run_dir = Path(run_dir)
        # Ensure run directory exists
        self.run_dir.mkdir(parents=True, exist_ok=True)
        self.prompt_path = self.run_dir / "story_prompt.txt"
        self.client = get_openai_client()

        # Create images directory
        self.images_dir = self.run_dir / "images"
        self.images_dir.mkdir(parents=True, exist_ok=True)

        # Default content source type
        self.source_type = "dogdrip"

    def _split_into_sentences(self, text: str) -> list[str]:
        """Split text into sentences.

        Args:
            text: Text to split

        Returns:
            List of sentences suitable for YouTube shorts
        """
        # Simple sentence splitting - handles basic punctuation
        sentences = re.split(r"(?<=[.!?]\s)", text)
        # Filter out empty sentences and very short ones
        sentences = [s.strip() for s in sentences if len(s.strip()) > 10]

        # Limit to a reasonable number of sentences for shorts
        if len(sentences) > 8:
            sentences = sentences[:8]
        elif len(sentences) < 2:
            # If only one sentence, try to split it further
            if len(text) > 100:
                midpoint = len(text) // 2
                # Find a space near the midpoint
                space_pos = text.find(" ", midpoint)
                if space_pos != -1:
                    sentences = [text[:space_pos].strip(), text[space_pos:].strip()]

        # Log the sentences
        for i, sentence in enumerate(sentences):
            logging.info(
                "Sentence %d: %s",
                i + 1,
                sentence[:50] + ("..." if len(sentence) > 50 else ""),
            )

        return sentences

    def _generate_image_for_sentence(self, sentence: str, index: int) -> str:
        """Generate an image for a sentence using DALL·E.

        Args:
            sentence: The sentence to illustrate
            index: The sentence index (for filename)

        Returns:
            Path to the generated image or empty string if generation fails
        """
        # Create a prompt for the image based on the sentence
        image_prompt = IMAGE_PROMPT_TEMPLATE.format(story=sentence)
        image_path = self.images_dir / f"sentence_{index + 1}.png"

        try:
            result = self.client.images.generate(
                model=OPENAI_IMAGE_MODEL,
                prompt=image_prompt,
                size=OPENAI_IMAGE_SIZE,
                quality=OPENAI_IMAGE_QUALITY,
                n=1,
            )

            if not result.data or not result.data[0].b64_json:
                raise ValueError(
                    "OpenAI API returned empty response for image generation"
                )

            image_data = result.data[0].b64_json

            with open(image_path, "wb") as f:
                f.write(base64.b64decode(image_data))

            logging.info("Generated image for sentence %d: %s", index + 1, image_path)
            return str(image_path)

        except ValueError as e:
            logging.error("Value error generating image %d: %s", index + 1, e)
        except OSError as e:
            logging.error("I/O error saving image %d: %s", index + 1, e)
        except Exception as e:
            logging.error("Unexpected error generating image %d: %s", index + 1, e)

        return ""

    def _save_mapping_file(
        self, story: str, sentences: list[str], image_paths: list[str]
    ) -> None:
        """Save a mapping file between sentences and their associated images.

        Args:
            story: The full story text
            sentences: List of sentences from the story
            image_paths: List of paths to generated images
        """
        mapping_path = self.run_dir / "sentence_image_mapping.txt"
        try:
            with open(mapping_path, "w", encoding="utf-8") as f:
                f.write(f"Story: {story}\n\n")
                for i, (sentence, image) in enumerate(zip(sentences, image_paths, strict=False)):
                    f.write(
                        f"Sentence {i + 1}: {sentence}\nImage: {image}\n\n"
                    )
            logging.info("Created sentence-image mapping file at %s", mapping_path)
        except OSError as e:
            logging.error("Failed to create mapping file: %s", e)

    def run(self, source_type: str = None) -> dict[str, list[str]]:
        """Fetch a story from the internet, split into sentences, and generate images.

        Args:
            source_type: Type of content source to use (defaults to self.source_type)

        Returns:
            Dictionary with story text and image paths
        """
        if source_type:
            self.source_type = source_type

        story = ""

        try:
            # Get appropriate scraper and fetch content
            scraper = ScraperFactory.get_scraper(self.source_type)
            stories = scraper.fetch_content()

            logging.info("Fetched %d stories from %s", len(stories), self.source_type)
            if stories:
                # Pick one complete story
                story = random.choice(stories)
        except Exception as e:
            logging.error("Failed to fetch stories from %s: %s", self.source_type, e)

        # Fallback if no story found
        if not story:
            story = (
                "A mysterious figure danced in the moonlight. Their shadow stretched "
                "impossibly long across the empty street. As they twirled, reality "
                "seemed to bend around them."
            )
            logging.info("Using fallback story as no stories were found")

        # Save complete story to file
        self.prompt_path.write_text(story, encoding="utf-8")
        logging.info("Saved internet story: %s", self.prompt_path)

        # Split story into sentences
        sentences = self._split_into_sentences(story)
        logging.info("Split story into %d sentences", len(sentences))

        # Generate an image for each sentence
        image_paths = []
        for i, sentence in enumerate(sentences):
            image_path = self._generate_image_for_sentence(sentence, i)
            if image_path:
                image_paths.append(image_path)

        # Create a mapping file between sentences and images
        self._save_mapping_file(story, sentences, image_paths)

        return {"story": story, "sentences": sentences, "image_paths": image_paths}
