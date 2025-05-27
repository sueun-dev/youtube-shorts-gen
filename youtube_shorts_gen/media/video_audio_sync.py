"""Module for synchronizing and merging video with audio."""

import logging
import subprocess
from pathlib import Path


class VideoAudioSyncer:
    """Synchronizes video with audio using ffmpeg.

    This class handles the process of adjusting video playback speed
    to match audio duration and merging them into a final output.
    """

    def __init__(self, run_dir: str):
        """Initialize the video-audio synchronizer.

        Args:
            run_dir: Directory containing input files and where output will be saved
        """
        self.run_dir = Path(run_dir)
        self.audio_path = self.run_dir / "story_audio.mp3"
        self.input_video = self.run_dir / "output_story_video.mp4"
        self.temp_video = self.run_dir / "temp_adjusted_video.mp4"
        self.final_video = self.run_dir / "final_story_video.mp4"

    def get_duration(self, path: Path) -> float:
        """Get the duration of a media file in seconds.

        Args:
            path: Path to the media file

        Returns:
            Duration in seconds as a float

        Raises:
            subprocess.CalledProcessError: If ffprobe command fails
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
        )
        return float(result.stdout.strip())

    def adjust_video_speed(self, speed: float) -> None:
        """Adjust video playback speed using ffmpeg.

        Args:
            speed: Speed factor to apply (e.g., 1.5 for 50% faster)

        Raises:
            subprocess.CalledProcessError: If ffmpeg command fails
        """
        logging.info("Adjusting video speed with factor: %.4f", speed)
        subprocess.run(
            [
                "ffmpeg",
                "-y",
                "-i",
                str(self.input_video),
                "-filter_complex",
                f"[0:v]setpts={1/speed}*PTS[v]",
                "-map",
                "[v]",
                "-an",
                str(self.temp_video),
            ],
            check=True,
        )

    def merge_audio_and_video(self) -> str:
        """Combine adjusted video and audio into final output.

        Returns:
            Path to the final video file

        Raises:
            subprocess.CalledProcessError: If ffmpeg command fails
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
            Path to the final synchronized video

        Raises:
            FileNotFoundError: If required files are missing
            subprocess.CalledProcessError: If any ffmpeg command fails
        """
        # Check if input files exist
        if not self.input_video.exists():
            raise FileNotFoundError(f"Input video not found: {self.input_video}")
        if not self.audio_path.exists():
            raise FileNotFoundError(f"Audio file not found: {self.audio_path}")

        logging.info("Measuring durations...")
        video_duration = self.get_duration(self.input_video)
        audio_duration = self.get_duration(self.audio_path)
        speed = video_duration / audio_duration

        logging.info("Computed speed ratio: %.4f", speed)
        self.adjust_video_speed(speed)

        logging.info("Merging video and audio...")
        return self.merge_audio_and_video()
