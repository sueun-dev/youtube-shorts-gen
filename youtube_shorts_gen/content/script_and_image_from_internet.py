"""Module for fetching stories from the internet for YouTube shorts."""

import base64
import logging
import random
import re
from pathlib import Path
from typing import Literal

from youtube_shorts_gen.scrapers.scraper_factory import ScraperFactory
from youtube_shorts_gen.utils.config import (
    IMAGE_PROMPT_TEMPLATE,
    OPENAI_IMAGE_MODEL,
    OPENAI_IMAGE_QUALITY,
    OPENAI_IMAGE_SIZE,
)
from youtube_shorts_gen.utils.openai_client import get_openai_client

import nltk
from nltk.tokenize import sent_tokenize

nltk.download("punkt", quiet=True)

class ScriptAndImageFromInternet:
    """Fetches short stories or content from the internet for YouTube shorts
    and generates images for each sentence.
    """

    def __init__(self, run_dir: str):
        """Initialize the internet script fetcher.

        Args:
            run_dir: Directory to save fetched content
        """
        self.run_dir = Path(run_dir)
        # self.run_dir is expected to be created by the caller.
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
        # Use NLTK's Punkt tokenizer for accurate sentence splitting
        sentences = sent_tokenize(text)
        # Filter out empty and too-short sentences
        sentences = [s.strip() for s in sentences if len(s.strip()) > 10]

        # Limit to a reasonable number of sentences for shorts
        if len(sentences) > 8:
            sentences = sentences[:8]
        elif len(sentences) < 2 and len(text) > 100:
            # If only one sentence, try to split it further
            midpoint = len(text) // 2
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
            size_value: Literal["1024x1024", "1792x1024", "1024x1792"] = OPENAI_IMAGE_SIZE
            quality_value: Literal["standard", "hd", "low"] = OPENAI_IMAGE_QUALITY

            result = self.client.images.generate(
                model=OPENAI_IMAGE_MODEL,
                prompt=image_prompt,
                size=size_value,
                quality=quality_value,
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
                for i, (sentence, image) in enumerate(
                    zip(sentences, image_paths, strict=False)
                ):
                    image_path = image if image is not None else ""
                    f.write(f"Sentence {i + 1}: {sentence}\nImage: {image_path}\n\n")
            logging.info("Created sentence-image mapping file at %s", mapping_path)
        except OSError as e:
            logging.error("Failed to create mapping file: %s", e)

    def run(self) -> dict[str, list[str] | str]:
        """Fetch a story from the internet, split into sentences, and generate images.

        Returns:
            Dictionary with story text and image paths
        """
        story = ""

        try:
            scraper = ScraperFactory.get_scraper(self.source_type)
            stories = scraper.fetch_content()
            logging.info("Fetched %d stories from %s", len(stories), self.source_type)

            if not stories:
                error_msg = f"No stories found from {self.source_type}"
                logging.error(error_msg)
                raise ValueError(error_msg)

            story = random.choice(stories)
        except Exception as e:
            logging.error("Failed to fetch stories from %s: %s", self.source_type, e)
            raise

        self.prompt_path.write_text(story, encoding="utf-8")
        logging.info("Saved internet story: %s", self.prompt_path)

        sentences = self._split_into_sentences(story)
        logging.info("Split story into %d sentences", len(sentences))

        image_paths = []
        for i, sentence in enumerate(sentences):
            image_path = self._generate_image_for_sentence(sentence, i)
            if image_path:
                image_paths.append(image_path)

        self._save_mapping_file(story, sentences, image_paths)

        return {
            "story": story,
            "sentences": sentences,
            "image_paths": image_paths,
        }
