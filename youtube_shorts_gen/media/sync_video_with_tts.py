"""Compatibility module for the original sync_video_with_tts functionality.

This module maintains backward compatibility with code that imports from
the original sync_video_with_tts module, while using the new split modules
under the hood.
"""

import logging
from pathlib import Path

# Import the new modules
from youtube_shorts_gen.media.tts_generator import TTSGenerator
from youtube_shorts_gen.media.video_audio_sync import (
    VideoAudioSyncer as NewVideoAudioSyncer,
)


class VideoAudioSyncer:
    """Synchronizes TTS-generated audio with video using ffmpeg.

    This class handles the process of generating text-to-speech audio
    from a story, adjusting video playback speed to match audio duration,
    and merging the audio and video into a final output.

    Note: This is a compatibility wrapper that uses the new split modules.
    """

    def __init__(self, run_dir: str, lang: str = "en"):
        """Initialize the video-audio synchronizer.

        Args:
            run_dir: Directory containing input files and where output will be saved
            lang: Language code for text-to-speech generation
        """
        self.run_dir = Path(run_dir)
        self.lang = lang

        # Initialize the new modules
        self.tts_generator = TTSGenerator(run_dir, lang)
        self.video_syncer = NewVideoAudioSyncer(run_dir)

        # For backward compatibility
        self.prompt_path = self.run_dir / "story_prompt.txt"
        self.audio_path = self.run_dir / "story_audio.mp3"
        self.input_video = self.run_dir / "output_story_video.mp4"
        self.temp_video = self.run_dir / "temp_adjusted_video.mp4"
        self.final_video = self.run_dir / "final_story_video.mp4"

    def _get_duration(self, path: Path) -> float:
        """Get the duration of a media file in seconds.

        Args:
            path: Path to the media file

        Returns:
            Duration in seconds as a float

        Raises:
            subprocess.CalledProcessError: If ffprobe command fails
        """
        return self.video_syncer.get_duration(path)

    def _generate_tts(self, text: str) -> None:
        """Generate text-to-speech audio and save to file.

        Args:
            text: Text content to convert to speech
        """
        self.tts_generator.generate_from_text(text)

    def _adjust_video_speed(self, speed: float) -> None:
        """Adjust video playback speed using ffmpeg.

        Args:
            speed: Speed factor to apply (e.g., 1.5 for 50% faster)

        Raises:
            subprocess.CalledProcessError: If ffmpeg command fails
        """
        self.video_syncer.adjust_video_speed(speed)

    def _merge_audio_and_video(self) -> None:
        """Combine adjusted video and TTS audio into final output.

        Raises:
            subprocess.CalledProcessError: If ffmpeg command fails
        """
        self.video_syncer.merge_audio_and_video()

    def sync(self) -> None:
        """Perform the full synchronization process.

        This method:
        1. Loads the story text from file
        2. Generates TTS audio from the story
        3. Measures video and audio durations
        4. Adjusts video speed to match audio duration
        5. Merges the adjusted video with the audio

        Raises:
            FileNotFoundError: If required files are missing
            subprocess.CalledProcessError: If any ffmpeg command fails
        """
        logging.info("Loading story from: %s", self.prompt_path)
        story = self.prompt_path.read_text(encoding="utf-8").strip()

        logging.info("Generating TTS...")
        self._generate_tts(story)

        logging.info("Measuring durations...")
        video_duration = self._get_duration(self.input_video)
        audio_duration = self._get_duration(self.audio_path)
        speed = video_duration / audio_duration

        logging.info("Computed speed ratio: %.4f", speed)
        self._adjust_video_speed(speed)

        logging.info("Merging video and audio...")
        self._merge_audio_and_video()
