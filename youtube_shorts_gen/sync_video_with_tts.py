import logging
import os
import subprocess

from gtts import gTTS


class VideoAudioSyncer:
    """Synchronize TTS-generated audio with video using ffmpeg."""

    def __init__(self, run_dir: str, lang: str = "en"):
        self.run_dir = run_dir
        self.lang = lang

        self.prompt_path = os.path.join(run_dir, "story_prompt.txt")
        self.audio_path = os.path.join(run_dir, "story_audio.mp3")
        self.input_video = os.path.join(run_dir, "output_story_video.mp4")
        self.temp_video = os.path.join(run_dir, "temp_adjusted_video.mp4")
        self.final_video = os.path.join(run_dir, "final_story_video.mp4")

    def _get_duration(self, path: str) -> float:
        """Return duration (in seconds) of a media file using ffprobe."""
        result = subprocess.run(
            [
                "ffprobe", "-v", "error",
                "-show_entries", "format=duration",
                "-of", "default=noprint_wrappers=1:nokey=1", path
            ],
            capture_output=True,
            text=True,
            check=True
        )
        return float(result.stdout.strip())

    def _generate_tts(self, text: str) -> None:
        """Generate and save TTS audio."""
        gTTS(text, lang=self.lang).save(self.audio_path)
        logging.info(f"TTS saved: {self.audio_path}")

    def _adjust_video_speed(self, speed: float) -> None:
        """Adjust video playback speed using ffmpeg."""
        logging.info(f"Adjusting video speed with factor: {speed:.4f}")
        subprocess.run([
            "ffmpeg", "-y", "-i", self.input_video,
            "-filter_complex", f"[0:v]setpts={1/speed}*PTS[v]",
            "-map", "[v]", "-an", self.temp_video
        ], check=True)

    def _merge_audio_and_video(self) -> None:
        """Combine adjusted video and TTS audio into final output."""
        subprocess.run([
            "ffmpeg", "-y", "-i", self.temp_video, "-i", self.audio_path,
            "-c:v", "copy", "-c:a", "aac", "-shortest", self.final_video
        ], check=True)
        logging.info(f"Final video saved: {self.final_video}")

    def sync(self) -> None:
        """Perform the full sync process."""
        logging.info(f"Loading story from: {self.prompt_path}")
        with open(self.prompt_path, encoding="utf-8") as file:
            story = file.read().strip()

        logging.info("Generating TTS...")
        self._generate_tts(story)

        logging.info("Measuring durations...")
        video_duration = self._get_duration(self.input_video)
        audio_duration = self._get_duration(self.audio_path)
        speed = video_duration / audio_duration

        logging.info(f"Computed speed ratio: {speed:.4f}")
        self._adjust_video_speed(speed)

        logging.info("Merging video and audio...")
        self._merge_audio_and_video()
