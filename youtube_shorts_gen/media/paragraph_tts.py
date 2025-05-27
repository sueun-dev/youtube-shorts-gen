"""Module for generating TTS audio for individual paragraphs."""

import logging
from pathlib import Path

from youtube_shorts_gen.utils.openai_client import get_openai_client


class ParagraphTTS:
    """Generates TTS audio for individual paragraphs."""

    def __init__(self, run_dir: str):
        """Initialize the paragraph TTS generator.

        Args:
            run_dir: Directory where audio will be saved
        """
        self.run_dir = Path(run_dir)
        self.audio_dir = self.run_dir / "paragraph_audio"
        self.audio_dir.mkdir(exist_ok=True)

        self.client = get_openai_client()

    def generate_tts_openai(self, text: str, index: int) -> str | None:
        """Generate TTS using OpenAI's TTS API.

        Args:
            text: Text to convert to speech
            index: Paragraph index for filename

        Returns:
            Path to the generated audio file or None if failed
        """
        if not self.client:
            logging.warning("OpenAI client not available, skipping OpenAI TTS")
            return None

        audio_path = self.audio_dir / f"paragraph_{index+1}.mp3"

        try:
            response = self.client.audio.speech.create(
                model="tts-1", voice="alloy", input=text
            )

            response.stream_to_file(str(audio_path))
            logging.info(
                "Generated OpenAI TTS audio for paragraph %d: %s", index + 1, audio_path
            )
            return str(audio_path)
        except Exception as e:
            logging.error(
                "Error generating OpenAI TTS audio for paragraph %d: %s", index + 1, e
            )
            return None

    def generate_for_paragraph(self, text: str, index: int) -> str:
        """Generate TTS for a paragraph, trying OpenAI first then falling back to gTTS.

        Args:
            text: Text to convert to speech
            index: Paragraph index for filename

        Returns:
            Path to the generated audio file
        """
        return self.generate_tts_openai(text, index)

    def generate_for_paragraphs(self, paragraphs: list[str]) -> list[str]:
        """Generate TTS for multiple paragraphs.

        Args:
            paragraphs: List of paragraph texts

        Returns:
            List of paths to generated audio files
        """
        audio_paths = []

        for i, paragraph in enumerate(paragraphs):
            audio_path = self.generate_for_paragraph(paragraph, i)
            if audio_path:
                audio_paths.append(audio_path)

        return audio_paths
