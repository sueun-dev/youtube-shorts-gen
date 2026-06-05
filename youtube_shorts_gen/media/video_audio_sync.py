"""Module for synchronizing and merging video with audio."""

import logging
import subprocess
from pathlib import Path

from youtube_shorts_gen.utils.config import (
    FFMPEG_CONCAT_TIMEOUT_SECONDS,
    FFPROBE_TIMEOUT_SECONDS,
    FINAL_VIDEO_FILENAME,
    OUTPUT_VIDEO_FILENAME,
    STORY_AUDIO_FILENAME,
)


class VideoAudioSyncer:
    """Synchronizes video with audio using ffmpeg.

    This class handles the process of adjusting video playback speed
    to match audio duration and merging them into a final output.
    """

    def __init__(self, run_dir: str):
        """Initialize the video-audio synchronizer.

        Args:
            run_dir: Directory containing input files and where output is saved
        """
        self.run_dir = Path(run_dir)
        self.audio_path = self.run_dir / STORY_AUDIO_FILENAME
        self.input_video = self.run_dir / OUTPUT_VIDEO_FILENAME
        self.temp_video = self.run_dir / "temp_adjusted_video.mp4"
        self.final_video = self.run_dir / FINAL_VIDEO_FILENAME

    def get_duration(self, path: Path) -> float:
        """Get the duration of a media file in seconds.

        Args:
            path: Path to the media file

        Returns:
            Duration in seconds as a float

        Raises:
            subprocess.CalledProcessError: If ffprobe command fails
            subprocess.TimeoutExpired: If ffprobe times out
        """
        result = subprocess.run(
            [
                "ffprobe",
                "-v",
                "error",
                "-show_entries",
                "format=duration",
                "-of",
                "default=noprint_wrappers=1:nokey=1",
                str(path),
            ],
            capture_output=True,
            text=True,
            check=True,
            timeout=FFPROBE_TIMEOUT_SECONDS,
        )
        return float(result.stdout.strip())

    def adjust_video_speed(self, speed: float) -> None:
        """Adjust video playback speed using ffmpeg.

        Args:
            speed: Speed factor to apply (e.g., 1.5 for 50% faster)

        Raises:
            subprocess.CalledProcessError: If ffmpeg command fails
            subprocess.TimeoutExpired: If ffmpeg times out
        """
        logging.info("Adjusting video speed with factor: %.4f", speed)
        subprocess.run(
            [
                "ffmpeg",
                "-y",
                "-i",
                str(self.input_video),
                "-filter_complex",
                f"[0:v]setpts={1 / speed}*PTS[v]",
                "-map",
                "[v]",
                "-an",
                str(self.temp_video),
            ],
            check=True,
            timeout=FFMPEG_CONCAT_TIMEOUT_SECONDS,
        )

    def merge_audio_and_video(self) -> str:
        """Combine adjusted video and audio into final output.

        Returns:
            Path to the final video file

        Raises:
            subprocess.CalledProcessError: If ffmpeg command fails
            subprocess.TimeoutExpired: If ffmpeg times out
        """
        subprocess.run(
            [
                "ffmpeg",
                "-y",
                "-i",
                str(self.temp_video),
                "-i",
                str(self.audio_path),
                "-c:v",
                "copy",
                "-c:a",
                "aac",
                "-shortest",
                str(self.final_video),
            ],
            check=True,
            timeout=FFMPEG_CONCAT_TIMEOUT_SECONDS,
        )
        logging.info("Final video saved: %s", self.final_video)
        return str(self.final_video)

    def sync(self) -> str:
        """Perform the full synchronization process.

        This method:
        1. Measures video and audio durations
        2. Adjusts video speed to match audio duration
        3. Merges the adjusted video with the audio

        Returns:
            Path to the final synchronized video, or an empty string if the
            audio duration is zero and synchronization cannot proceed

        Raises:
            FileNotFoundError: If required files are missing
            subprocess.CalledProcessError: If any ffmpeg command fails
            subprocess.TimeoutExpired: If any ffmpeg command times out
        """
        if not self.input_video.exists():
            raise FileNotFoundError(f"Input video not found: {self.input_video}")
        if not self.audio_path.exists():
            raise FileNotFoundError(f"Audio file not found: {self.audio_path}")

        logging.info("Measuring durations")
        try:
            video_duration = self.get_duration(self.input_video)
            audio_duration = self.get_duration(self.audio_path)
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired):
            logging.exception("Failed to probe media durations")
            return ""

        if audio_duration == 0:
            logging.error(
                "Audio duration is zero; skipping synchronization for %s",
                self.audio_path,
            )
            return ""

        speed = video_duration / audio_duration
        logging.info("Computed speed ratio: %.4f", speed)

        try:
            self.adjust_video_speed(speed)
            logging.info("Merging video and audio")
            return self.merge_audio_and_video()
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired):
            logging.exception("ffmpeg failed during synchronization")
            return ""
