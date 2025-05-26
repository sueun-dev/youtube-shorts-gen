import logging
import re
from pathlib import Path

from openai import OpenAI  # Assuming OpenAI client is passed or initialized

from youtube_shorts_gen.utils.config import OPENAI_CHAT_MODEL


class TextProcessor:
    """Processes text by splitting, summarizing, and extracting sentences."""

    def __init__(self, run_dir: str, openai_client: OpenAI):
        """Initialize the text processor.

        Args:
            run_dir: Directory containing run-specific files (e.g., mapping files).
            openai_client: An instance of the OpenAI client for API calls.
        """
        self.run_dir = Path(run_dir)
        self.client = openai_client

    def _extract_sentences_from_mapping_file(self) -> list[str]:
        """Extract sentences from the sentence_image_mapping.txt file.

        Returns:
            List of sentences if found, empty list otherwise.
        """
        mapping_path = self.run_dir / "sentence_image_mapping.txt"

        if not mapping_path.exists():
            return []

        try:
            with open(mapping_path, encoding="utf-8") as f:
                content = f.read()
                # Regex to find sentences followed by an 'Image:' tag
                sentence_blocks = re.findall(
                    r"Sentence \d+:\s*(.+?)\nImage:", content, re.DOTALL
                )

            if sentence_blocks:
                logging.info(
                    "Found %d sentences in mapping file, using these directly",
                    len(sentence_blocks),
                )
                return [s.strip() for s in sentence_blocks]
        except Exception as e:
            logging.error("Error reading sentence mapping file: %s", e)

        return []

    def _split_text(self, text: str, strategy: str = "paragraphs") -> list[str]:
        """Split text into segments using the specified strategy.

        Args:
            text: The text to split.
            strategy: The splitting strategy ("paragraphs", "sentences", or "chunks").

        Returns:
            List of text segments.
        """
        if strategy == "paragraphs":
            split_text = text.split("\n\n")
            segments = [p.strip() for p in split_text if p.strip()]
            if len(segments) > 8:  # Limit for shorts
                logging.info("Limiting to 8 paragraphs for shorts.")
                segments = segments[:8]
            return segments

        elif strategy == "sentences":
            # Regex to split by sentence-ending punctuation followed by space or newline
            raw_sentences = re.split(r"(?<=[.!?])(?:\s+|\n)", text)
            segments = [s.strip() for s in raw_sentences if s.strip()]
            if len(segments) > 1:
                logging.info("Split text into %d sentences", len(segments))
                return segments
            logging.debug(
                "Could not split text into multiple sentences with current strategy."
            )
            return []

        elif strategy == "chunks":
            if len(text) <= 100:  # Arbitrary short text threshold
                return [text.strip()] if text.strip() else []

            segments = []
            # Aim for 2-4 chunks, with a max size to avoid overly long chunks
            num_chunks_target = max(2, min(4, len(text) // 150))
            chunk_size = (
                len(text) + num_chunks_target - 1
            ) // num_chunks_target  # ceiling division
            chunk_size = min(
                chunk_size, 300
            )  # Max chunk size to avoid API limits/long processing

            for i in range(0, len(text), chunk_size):
                chunk = text[i : i + chunk_size].strip()
                if chunk:
                    segments.append(chunk)
            logging.info("Created %d artificial chunks from text", len(segments))
            return segments
        else:
            logging.error(f"Unknown splitting strategy: {strategy}")
            raise ValueError(f"Unknown splitting strategy: {strategy}")

    def _summarize_paragraph(self, paragraph: str, index: int) -> str:
        """Summarize a single paragraph using OpenAI if it's too long.

        Args:
            paragraph: The paragraph to summarize.
            index: The index of the paragraph (for logging).

        Returns:
            Summarized paragraph or original if short enough/error.
        """
        # Threshold for summarization, e.g., characters
        # This could be configurable
        if len(paragraph) <= 300:
            return paragraph

        try:
            logging.info(
                f"Paragraph {index+1} is long ({len(paragraph)} chars), attempting summarization."
            )
            response = self.client.chat.completions.create(
                model=OPENAI_CHAT_MODEL,
                messages=[
                    {
                        "role": "system",
                        "content": "Summarize the following paragraph concisely in about 2-3 sentences while preserving the key points and emotional tone. Keep it engaging for a short video format.",
                    },
                    {"role": "user", "content": paragraph},
                ],
                max_tokens=150,  # Adjust as needed
                temperature=0.7,
            )
            summary = response.choices[0].message.content.strip()
            logging.info(
                "Summarized paragraph %d from %d to %d chars",
                index + 1,
                len(paragraph),
                len(summary),
            )
            return (
                summary if summary else paragraph
            )  # Return original if summary is empty
        except Exception as e:
            logging.error(
                "Error summarizing paragraph %d: %s. Using original (or truncated).",
                index + 1,
                e,
            )
            return paragraph[
                :500
            ]  # Fallback to truncated original if summarization fails

    def get_content_segments(
        self, text: str, summarize_long_paragraphs: bool = True
    ) -> list[str]:
        """Process text to get a list of content segments (paragraphs/sentences).

        This method tries to extract sentences from a mapping file first.
        If not found, it splits the text using various strategies.
        Optionally summarizes long paragraphs.

        Args:
            text: The original text to process.
            summarize_long_paragraphs: Whether to summarize paragraphs that exceed a certain length.

        Returns:
            List of processed content segments.
        """
        sentences_from_file = self._extract_sentences_from_mapping_file()
        if sentences_from_file:
            logging.info("Using sentences extracted from mapping file.")
            # If we use sentences from file, summarization might not be desired or applicable
            # in the same way, unless they are very long.
            # For now, we assume sentences from file are appropriately sized.
            return sentences_from_file

        logging.info(
            "No sentence mapping found. Proceeding to split and summarize text."
        )

        # Try splitting by paragraphs first as a primary strategy
        segments = self._split_text(text, strategy="paragraphs")

        # If paragraph splitting results in too few segments (e.g., one large block of text),
        # try splitting by sentences.
        if not segments or (
            len(segments) == 1 and len(segments[0]) > 500
        ):  # Arbitrary length indicating a large block
            logging.info(
                "Initial paragraph split resulted in one large segment or no segments. Trying sentence splitting."
            )
            sentence_segments = self._split_text(text, strategy="sentences")
            if (
                len(sentence_segments) > 1
            ):  # Prefer sentence split if it yields multiple meaningful segments
                segments = sentence_segments
            elif (
                not segments
            ):  # If paragraph split was empty and sentence split is also not great
                logging.info(
                    "Sentence splitting also didn't yield multiple segments. Resorting to chunking."
                )
                segments = self._split_text(text, strategy="chunks")

        if not segments:
            logging.warning(
                "Text processing resulted in no segments. Returning empty list."
            )
            return []

        if summarize_long_paragraphs:
            processed_segments = []
            for i, segment in enumerate(segments):
                processed_segments.append(self._summarize_paragraph(segment, i))
            return processed_segments
        else:
            return segments
