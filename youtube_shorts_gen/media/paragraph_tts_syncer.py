"""Module for generating TTS audio for each paragraph and syncing with images."""

import logging
import os
import subprocess
from pathlib import Path

# Use built-in type annotations
from gtts import gTTS


class ParagraphTTSSyncer:
    """Generates TTS audio for each paragraph and creates a synced video for each."""

    def __init__(self, run_dir: str, lang: str = "ko"):
        """Initialize the paragraph TTS syncer.

        Args:
            run_dir: Directory containing input files and where output will be saved
            lang: Language code for text-to-speech generation
        """
        self.run_dir = Path(run_dir)
        self.lang = lang

        # Directory for paragraph audio files
        self.audio_dir = self.run_dir / "audio"
        self.audio_dir.mkdir(exist_ok=True)

        # Directory for paragraph videos
        self.video_dir = self.run_dir / "paragraph_videos"
        self.video_dir.mkdir(exist_ok=True)

        # Path to the mapping file
        self.mapping_path = self.run_dir / "paragraph_image_mapping.txt"

        # Final combined video
        self.final_video = self.run_dir / "final_story_video.mp4"

    def _generate_tts_for_paragraph(self, paragraph: str, index: int) -> str:
        """Generate TTS audio for a paragraph.

        Args:
            paragraph: The paragraph text
            index: Paragraph index for filename

        Returns:
            Path to the generated audio file
        """
        audio_path = self.audio_dir / f"paragraph_{index+1}.mp3"

        try:
            tts = gTTS(paragraph, lang=self.lang)
            tts.save(str(audio_path))
            logging.info("Generated TTS for paragraph %d: %s", index + 1, audio_path)
            return str(audio_path)
        except Exception as e:
            logging.error("Error generating TTS for paragraph %d: %s", index + 1, e)
            return ""

    def _get_duration(self, media_path: Path) -> float:
        """Get the duration of a media file in seconds.

        Args:
            media_path: Path to the media file

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
                str(media_path),
            ],
            capture_output=True,
            text=True,
            check=True,
        )
        return float(result.stdout.strip())

    def _create_image_video(
        self, image_path: str, duration: float, output_path: Path
    ) -> None:
        """Create a video from an image with the specified duration.

        Args:
            image_path: Path to the image
            duration: Duration in seconds
            output_path: Path to save the output video

        Raises:
            subprocess.CalledProcessError: If ffmpeg command fails
        """
        subprocess.run(
            [
                "ffmpeg",
                "-y",
                "-loop",
                "1",
                "-i",
                image_path,
                "-c:v",
                "libx264",
                "-t",
                str(duration),
                "-pix_fmt",
                "yuv420p",
                "-vf",
                (
                    "scale=1080:1920:force_original_aspect_ratio=decrease,"
                    "pad=1080:1920:(ow-iw)/2:(oh-ih)/2"
                ),
                str(output_path),
            ],
            check=True,
        )

        logging.info("Created image video: %s", output_path)

    def _merge_audio_and_video(
        self, video_path: Path, audio_path: str, output_path: Path
    ) -> None:
        """Combine video and audio into a single file.

        Args:
            video_path: Path to the video file
            audio_path: Path to the audio file
            output_path: Path to save the output video

        Raises:
            subprocess.CalledProcessError: If ffmpeg command fails
        """
        subprocess.run(
            [
                "ffmpeg",
                "-y",
                "-i",
                str(video_path),
                "-i",
                audio_path,
                "-c:v",
                "copy",
                "-c:a",
                "aac",
                "-shortest",
                str(output_path),
            ],
            check=True,
        )

        logging.info("Merged audio and video: %s", output_path)

    def _combine_paragraph_videos(self, video_paths: list) -> None:
        """Combine multiple paragraph videos into a single final video.

        Args:
            video_paths: List of paths to paragraph videos

        Raises:
            subprocess.CalledProcessError: If ffmpeg command fails
        """
        # Create a file list for ffmpeg
        list_file_path = self.run_dir / "video_list.txt"
        with open(list_file_path, "w", encoding="utf-8") as f:
            for video_path in video_paths:
                f.write(f"file '{os.path.abspath(video_path)}'\n")

        # Combine videos using ffmpeg
        subprocess.run(
            [
                "ffmpeg",
                "-y",
                "-f",
                "concat",
                "-safe",
                "0",
                "-i",
                str(list_file_path),
                "-c",
                "copy",
                str(self.final_video),
            ],
            check=True,
        )

        logging.info("Combined paragraph videos into final video: %s", self.final_video)

    def _parse_mapping_file(self) -> list:
        """Parse the paragraph-image mapping file.

        Returns:
            List of dictionaries with paragraph text and image path
        """
        if not self.mapping_path.exists():
            logging.error("Mapping file not found: %s", self.mapping_path)
            return []

        content = self.mapping_path.read_text(encoding="utf-8")
        sections = content.split("\n\n")

        paragraphs = []
        for section in sections[1:]:  # Skip the first section (story overview)
            lines = section.strip().split("\n")
            if len(lines) >= 2:
                # Extract paragraph text and image path
                paragraph_text = lines[0].split(": ", 1)[1] if ": " in lines[0] else ""
                image_path = lines[1].split(": ", 1)[1] if ": " in lines[1] else ""

                if paragraph_text and image_path:
                    paragraphs.append({"text": paragraph_text, "image": image_path})

        return paragraphs

    def sync(self) -> str:
        """Generate TTS audio for each paragraph and create synced videos.

        Returns:
            Path to the final combined video

        Raises:
            FileNotFoundError: If required files are missing
            subprocess.CalledProcessError: If any ffmpeg command fails
        """
        # Parse the mapping file to get paragraphs and images
        paragraph_data = self._parse_mapping_file()

        if not paragraph_data:
            logging.error("No paragraph data found in mapping file")
            raise ValueError("No paragraph data found in mapping file")

        paragraph_videos = []

        # Process each paragraph
        for i, data in enumerate(paragraph_data):
            paragraph_text = data["text"]
            image_path = data["image"]

            # Generate TTS audio for the paragraph
            audio_path = self._generate_tts_for_paragraph(paragraph_text, i)
            if not audio_path:
                continue

            # Get audio duration
            audio_duration = self._get_duration(Path(audio_path))

            # Create a video from the image with the same duration as the audio
            temp_video_path = self.video_dir / f"temp_paragraph_{i+1}.mp4"
            self._create_image_video(image_path, audio_duration, temp_video_path)

            # Merge the audio and video
            output_video_path = self.video_dir / f"paragraph_{i+1}.mp4"
            self._merge_audio_and_video(temp_video_path, audio_path, output_video_path)

            paragraph_videos.append(str(output_video_path))

        # Combine all paragraph videos into a single video
        if paragraph_videos:
            self._combine_paragraph_videos(paragraph_videos)
            return str(self.final_video)

        logging.error("No paragraph videos were created")
        raise ValueError("No paragraph videos were created")
