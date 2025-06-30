"""Module for generating TTS audio for individual paragraphs."""

import logging
import os
from pathlib import Path

from elevenlabs.client import ElevenLabs


class ParagraphTTS:
    """Generates TTS audio for individual paragraphs using the ElevenLabs API."""

    def __init__(self, run_dir: str):
        """Initialize the paragraph TTS generator.

        Args:
            run_dir: Directory where audio will be saved
        """
        self.run_dir = Path(run_dir)
        self.audio_dir = self.run_dir / "paragraph_audio"
        self.audio_dir.mkdir(exist_ok=True)

        

    def _generate_tts_elevenlabs(self, text: str, index: int) -> str | None:
        """Generate TTS using ElevenLabs API.

        Args:
            text: Text to convert to speech
            index: Paragraph index for filename

        Returns:
            Path to the generated audio file or None if failed
        """
        api_key = os.getenv("ELEVENLABS_API_KEY")
        if not api_key:
            logging.error(
                "ELEVENLABS_API_KEY environment variable not set; skipping TTS"
            )
            return None

        audio_path = self.audio_dir / f"paragraph_{index+1}.mp3"

        try:
            client = ElevenLabs()
            audio_bytes = client.generate(text=text, voice="JBFqnCBsd6RMkjVDRZzb")
            with open(audio_path, "wb") as f:
                if isinstance(audio_bytes, bytes | bytearray):
                    f.write(audio_bytes)
                else:
                    for chunk in audio_bytes:
                        f.write(chunk)
            logging.info(
                "Generated ElevenLabs TTS audio for paragraph %d: %s",
                index + 1, audio_path
            )
            return str(audio_path)
        except Exception as e:
            logging.error(
                "Error generating ElevenLabs TTS audio for paragraph %d: %s",
                index + 1, e
            )
            return None

    def generate_for_paragraph(self, text: str, index: int) -> str | None:
        """Generate TTS for a single paragraph using ElevenLabs.

        Args:
            text: Text to convert to speech
            index: Paragraph index for filename

        Returns:
            Path to the generated audio file
        """
        return self._generate_tts_elevenlabs(text, index)

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
