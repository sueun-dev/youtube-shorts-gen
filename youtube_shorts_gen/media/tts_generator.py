"""Module for generating text-to-speech audio from text."""

import logging
import os
from pathlib import Path

from elevenlabs.client import ElevenLabs


class TTSGenerator:
    """Generates text-to-speech audio from text using the ElevenLabs TTS API.

    This class handles the process of converting text to speech
    and saving the resulting audio to a file.
    """

    def __init__(self, run_dir: str, lang: str = "en"):
        """Initialize the TTS generator.

        Args:
            run_dir: Directory where the audio will be saved
            lang: Language code for text-to-speech generation
        """
        self.run_dir = Path(run_dir)
        self.lang = lang
        self.prompt_path = self.run_dir / "story_prompt.txt"
        self.audio_path = self.run_dir / "story_audio.mp3"

    def generate_from_file(self) -> str:
        """Generate TTS audio from the story file.

        Returns:
            Path to the generated audio file

        Raises:
            FileNotFoundError: If the story file is missing
        """
        logging.info("Loading story from: %s", self.prompt_path)

        if not self.prompt_path.exists():
            raise FileNotFoundError(f"Story file not found: {self.prompt_path}")

        story = self.prompt_path.read_text(encoding="utf-8").strip()
        return self.generate_from_text(story)

    def generate_from_text(self, text: str) -> str:
        """Generate TTS audio from the provided text.

        Args:
            text: Text content to convert to speech

        Returns:
            Path to the generated audio file
        """
        logging.info("Generating TTS with ElevenLabs...")
        api_key = os.getenv("ELEVENLABS_API_KEY")
        if not api_key:
            raise OSError("ELEVENLABS_API_KEY environment variable not set.")

        client = ElevenLabs()
        audio_bytes = client.generate(text=text, voice="JBFqnCBsd6RMkjVDRZzb")

        with open(self.audio_path, "wb") as f:
            if isinstance(audio_bytes, bytes | bytearray):
                f.write(audio_bytes)
            else:
                # If generate returns an iterator (stream), join chunks
                for chunk in audio_bytes:
                    f.write(chunk)
        logging.info("TTS saved: %s", self.audio_path)
        return str(self.audio_path)
