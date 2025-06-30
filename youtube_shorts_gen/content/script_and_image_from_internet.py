import logging
import random
from pathlib import Path

import nltk
from nltk.tokenize import sent_tokenize
from openai import OpenAI

from youtube_shorts_gen.scrapers.dogdrip import fetch_dogdrip_content
from youtube_shorts_gen.utils.config import IMAGE_PROMPT_TEMPLATE
from youtube_shorts_gen.utils.openai_image import (
    generate_image as generate_openai_image,
    generate_sequential_images,
)

nltk.download("punkt", quiet=True)

MAX_SENTENCES: int = 8  # Upper limit to keep shorts within ~60s
MIN_CHARS_SPLIT: int = 100  # If text > this and only 1 sentence, force split
IMAGES_DIR_NAME: str = "images"
SENTENCE_IMAGE_FILENAME_TEMPLATE: str = "sentence_{index}.png"

class ScriptAndImageFromInternet:
    """Fetches short stories or content from the internet for YouTube shorts
    and generates images for each sentence.
    """

    def __init__(self, run_dir: str, client: OpenAI):
        """Initialize the internet script fetcher.

        Args:
            run_dir: Directory to save fetched content
        """
        self.run_dir = Path(run_dir)
        self.prompt_path = self.run_dir / "story_prompt.txt"
        self.client = client

        self.images_dir = self.run_dir / IMAGES_DIR_NAME
        self.images_dir.mkdir(parents=True, exist_ok=True)

    def tokenize_and_clean(self, text: str) -> list[str]:
        """NLTK 토큰화 + 짧은 문장 제거."""
        return [s.strip() for s in sent_tokenize(text) if len(s.strip()) > 10]

    def normalise_sentence_count(
        self,
        sentences: list[str],
        *,
        max_len: int = MAX_SENTENCES,
        fallback_min_chars: int = MIN_CHARS_SPLIT,
        original_text: str = "",
    ) -> list[str]:
        """MAX_SENTENCES 문장 제한 및 2문장 fallback 로직."""
        if len(sentences) > max_len:
            return sentences[:max_len]
        if len(sentences) < 2 and len(original_text) > fallback_min_chars:
            midpoint = original_text.find(" ", len(original_text) // 2)
            if midpoint != -1:
                return [original_text[:midpoint].strip(),
                        original_text[midpoint:].strip()]
        return sentences

    def _generate_image_for_sentence(self, sentence: str, index: int) -> str:
        """Generate an image for a sentence using DALL·E.

        Args:
            sentence: The sentence to illustrate
            index: The sentence index (for filename)

        Returns:
            Path to the generated image or empty string if generation fails
        """
        image_prompt = IMAGE_PROMPT_TEMPLATE.format(story=sentence)
        image_path = self.images_dir / SENTENCE_IMAGE_FILENAME_TEMPLATE.format(
            index=index + 1
        )

        return generate_openai_image(self.client, image_prompt, image_path)

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

    def run(self) -> dict[str, list[str] | str]:
        """Fetch a story from the internet, split into sentences, and generate images.

        Returns:
            Dictionary with story text and image paths
        """
        story = ""

        try:
            stories = fetch_dogdrip_content()
            logging.info("Fetched %d stories from Dogdrip", len(stories))

            if not stories:
                raise RuntimeError("No stories returned from Dogdrip")

            story = random.choice(stories)
        except Exception as e:
            logging.error("Failed to fetch stories from Dogdrip: %s", e)
            raise

        self.prompt_path.write_text(story, encoding="utf-8")
        logging.info("Saved internet story: %s", self.prompt_path)

        # Split the story into sentences and normalize the count
        sentences = self.tokenize_and_clean(story)
        sentences = self.normalise_sentence_count(sentences, original_text=story)
        logging.info("Split story into %d sentences", len(sentences))
 
        # Generate image prompts for all sentences
        image_prompts = []
        output_paths = []
        for i, sentence in enumerate(sentences):
            image_prompt = IMAGE_PROMPT_TEMPLATE.format(story=sentence)
            image_path = self.images_dir / SENTENCE_IMAGE_FILENAME_TEMPLATE.format(index=i + 1)
            image_prompts.append(image_prompt)
            output_paths.append(image_path)
        
        # Generate images with natural flow between scenes
        image_paths = generate_sequential_images(self.client, image_prompts, output_paths)
        logging.info("Generated %d sequential images", len(image_paths))
        
        self._save_mapping_file(story, sentences, image_paths)

        return {
            "story": story,
            "sentences": sentences,
            "image_paths": image_paths,
        }
