import logging
import random
from pathlib import Path
from typing import Any

import nltk
from nltk.tokenize import sent_tokenize
from openai import OpenAI

from youtube_shorts_gen.scrapers.dogdrip import fetch_dogdrip_content
from youtube_shorts_gen.utils.config import (
    IMAGE_PROMPT_TEMPLATE,
    MAX_STORY_SENTENCES,
    MIN_SENTENCE_CHARS,
)
from youtube_shorts_gen.utils.openai_image import generate_sequential_images

IMAGES_DIR_NAME: str = "images"
SENTENCE_IMAGE_FILENAME_TEMPLATE: str = "sentence_{index}.png"


def _ensure_nltk_resources() -> None:
    """Ensure required NLTK tokenizer resources are available.

    Both ``punkt`` and ``punkt_tab`` are needed by ``sent_tokenize`` across
    NLTK versions. A download failure logs a warning but never crashes import.
    """
    resources = (("tokenizers/punkt", "punkt"), ("tokenizers/punkt_tab", "punkt_tab"))
    for find_path, package in resources:
        try:
            nltk.data.find(find_path)
        except LookupError:
            try:
                nltk.download(package, quiet=True)
            except Exception:
                logging.exception("Failed to download NLTK resource %s", package)


_ensure_nltk_resources()


class ScriptAndImageFromInternet:
    """Fetches short stories or content from the internet for YouTube shorts
    and generates images for each sentence.
    """

    def __init__(self, run_dir: str, client: OpenAI):
        """Initialize the internet script fetcher.

        Args:
            run_dir: Directory to save fetched content
            client: OpenAI client used to generate images
        """
        self.run_dir = Path(run_dir)
        self.prompt_path = self.run_dir / "story_prompt.txt"
        self.client = client

        self.images_dir = self.run_dir / IMAGES_DIR_NAME
        self.images_dir.mkdir(parents=True, exist_ok=True)

    def tokenize_and_clean(self, text: str) -> list[str]:
        """Tokenize text with NLTK and drop very short sentences."""
        return [s.strip() for s in sent_tokenize(text) if len(s.strip()) > 10]

    def normalise_sentence_count(
        self,
        sentences: list[str],
        *,
        max_len: int = MAX_STORY_SENTENCES,
        fallback_min_chars: int = MIN_SENTENCE_CHARS,
        original_text: str = "",
    ) -> list[str]:
        """Cap sentence count and split into two when too few are produced."""
        if len(sentences) > max_len:
            return sentences[:max_len]
        if len(sentences) < 2 and len(original_text) > fallback_min_chars:
            midpoint = original_text.find(" ", len(original_text) // 2)
            if midpoint != -1:
                return [
                    original_text[:midpoint].strip(),
                    original_text[midpoint:].strip(),
                ]
        return sentences

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
                    f.write(f"Sentence {i + 1}: {sentence}\nImage: {image}\n\n")
            logging.info("Created sentence-image mapping file at %s", mapping_path)
        except OSError as e:
            logging.error("Failed to create mapping file: %s", e)

    def run(self) -> dict[str, Any]:
        """Fetch a story, split it into sentences, and generate images.

        Returns:
            Dictionary with the ``story`` text, the ``sentences`` list, and the
            ``image_paths`` list.
        """
        try:
            stories = fetch_dogdrip_content()
        except (OSError, ValueError) as e:
            logging.error("Failed to fetch stories from Dogdrip: %s", e)
            raise

        logging.info("Fetched %d stories from Dogdrip", len(stories))
        if not stories:
            raise RuntimeError("No stories returned from Dogdrip")

        story = random.choice(stories)

        self.prompt_path.write_text(story, encoding="utf-8")
        logging.info("Saved internet story: %s", self.prompt_path)

        # Split the story into sentences and normalize the count.
        sentences = self.tokenize_and_clean(story)
        sentences = self.normalise_sentence_count(sentences, original_text=story)
        logging.info("Split story into %d sentences", len(sentences))

        # Build image prompts and output paths for all sentences.
        image_prompts: list[str] = []
        output_paths: list[Path] = []
        for i, sentence in enumerate(sentences):
            image_prompts.append(IMAGE_PROMPT_TEMPLATE.format(story=sentence))
            output_paths.append(
                self.images_dir / SENTENCE_IMAGE_FILENAME_TEMPLATE.format(index=i + 1)
            )

        # Generate images with natural flow between scenes.
        image_paths = generate_sequential_images(
            self.client, image_prompts, output_paths
        )
        logging.info("Generated %d sequential images", len(image_paths))

        self._save_mapping_file(story, sentences, image_paths)

        return {
            "story": story,
            "sentences": sentences,
            "image_paths": image_paths,
        }
