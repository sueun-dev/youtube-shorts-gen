import logging
import shutil
import subprocess
from pathlib import Path


class VideoAssembler:
    """Assembles video segments from images and audio, and concatenates them."""

    def __init__(self, run_dir: str):
        """Initialize the video assembler.

        Args:
            run_dir: Directory to store temporary and final video files.
        """
        self.run_dir = Path(run_dir)
        self.segments_dir = self.run_dir / "segments"
        self.segments_dir.mkdir(parents=True, exist_ok=True)

    def _get_audio_duration(self, audio_path: str) -> float:
        """Get the duration of an audio file using ffprobe."""
        try:
            result = subprocess.run(
                [
                    "ffprobe",
                    "-v",
                    "error",
                    "-show_entries",
                    "format=duration",
                    "-of",
                    "default=noprint_wrappers=1:nokey=1",
                    audio_path,
                ],
                capture_output=True,
                text=True,
                check=True,
                timeout=30,
            )
            return float(result.stdout.strip())
        except subprocess.TimeoutExpired:
            logging.error(f"ffprobe timed out while getting duration for {audio_path}")
            return 0.0  # Return a default or raise an error
        except subprocess.CalledProcessError as e:
            logging.error(f"ffprobe error for {audio_path}: {e.stderr}")
            return 0.0
        except ValueError:
            logging.error(
                f"Could not parse duration from ffprobe output for {audio_path}"
            )
            return 0.0

    def create_segment_video(
        self,
        image_path: str,
        audio_path: str,
        index: int,
        target_resolution: tuple[int, int] = (1080, 1920),
    ) -> str:
        """Create a video segment from an image and audio file, scaled and padded for shorts.

        Args:
            image_path: Path to the image file.
            audio_path: Path to the audio file.
            index: The segment index (for filename).
            target_resolution: Target video resolution (width, height) for YouTube Shorts.

        Returns:
            Path to the created video segment, or empty string if failed.
        """
        if not Path(image_path).exists():
            logging.error(f"Image file not found: {image_path} for segment {index + 1}")
            return ""
        if not Path(audio_path).exists():
            logging.error(f"Audio file not found: {audio_path} for segment {index + 1}")
            return ""

        output_path = self.segments_dir / f"segment_{index + 1}.mp4"
        duration = self._get_audio_duration(audio_path)

        if duration <= 0:
            logging.error(
                f"Audio duration is invalid for {audio_path}, cannot create segment {index+1}."
            )
            return ""

        target_w, target_h = target_resolution

        # FFmpeg command to scale, pad, and combine image and audio
        # This command creates a 9:16 video. It scales the image to fit within 1080 width,
        # then pads the height to 1920 if necessary, or scales to fit 1920 height and pads width.
        # It prioritizes fitting the width and then padding vertically (black bars top/bottom if landscape image).
        # For portrait images, it will fit height and pad horizontally (black bars left/right).
        ffmpeg_command = [
            "ffmpeg",
            "-y",
            "-loop",
            "1",  # Loop the image
            "-i",
            image_path,  # Input image
            "-i",
            audio_path,  # Input audio
            "-c:v",
            "libx264",
            "-tune",
            "stillimage",
            "-c:a",
            "aac",
            "-b:a",
            "192k",
            "-pix_fmt",
            "yuv420p",
            "-vf",
            f"scale=w='min(iw*min(1,min({target_w}/iw,{target_h}/ih)),{target_w})':h='min(ih*min(1,min({target_w}/iw,{target_h}/ih)),{target_h})':force_original_aspect_ratio=decrease,pad=w={target_w}:h={target_h}:x=({target_w}-iw)/2:y=({target_h}-ih)/2:color=black",
            "-shortest",  # Finish encoding when the shortest input stream ends (the audio)
            "-t",
            str(duration),  # Set duration explicitly
            str(output_path),
        ]

        try:
            logging.info(
                f"Creating video segment {index + 1} with duration {duration}s: {output_path}"
            )
            subprocess.run(
                ffmpeg_command, check=True, capture_output=True, text=True, timeout=60
            )
            logging.info(
                "Successfully created video segment %d: %s", index + 1, output_path
            )
            return str(output_path)
        except subprocess.TimeoutExpired:
            logging.error(f"ffmpeg command timed out for segment {index+1}.")
            return ""
        except subprocess.CalledProcessError as e:
            logging.error(f"Error creating video segment {index + 1}: {e.stderr}")
            return ""

    def concatenate_segments(
        self, segment_paths: list[str], final_video_name: str = "output_story_video.mp4"
    ) -> str:
        """Concatenate video segments into a final video.

        Args:
            segment_paths: List of paths to video segments.
            final_video_name: Name for the final output video file.

        Returns:
            Path to the final concatenated video, or empty string if failed.
        """
        if not segment_paths:
            logging.error("No video segments provided to concatenate.")
            return ""

        # Filter out any empty or non-existent paths
        valid_segment_paths = [
            p
            for p in segment_paths
            if p and Path(p).exists() and Path(p).stat().st_size > 0
        ]
        if not valid_segment_paths:
            logging.error("No valid video segments found to concatenate.")
            return ""

        logging.info(f"Concatenating {len(valid_segment_paths)} video segments.")

        final_video_path = self.run_dir / final_video_name
        concat_file_path = self.run_dir / "concat_list.txt"

        with open(concat_file_path, "w", encoding="utf-8") as f:
            for segment_path_str in valid_segment_paths:
                # Ensure paths are absolute and correctly formatted for ffmpeg
                abs_path = Path(segment_path_str).resolve()
                f.write(f"file '{abs_path}'\n")

        ffmpeg_command = [
            "ffmpeg",
            "-y",
            "-f",
            "concat",
            "-safe",
            "0",  # Allow unsafe file paths (though we resolved them)
            "-i",
            str(concat_file_path),
            "-c",
            "copy",  # Re-encode if formats differ, copy if compatible.
            # For robustness, consider specific re-encoding if segments vary wildly.
            # e.g. -c:v libx264 -c:a aac
            str(final_video_path),
        ]

        try:
            subprocess.run(
                ffmpeg_command, check=True, capture_output=True, text=True, timeout=120
            )
            logging.info(
                "Successfully concatenated segments into: %s", final_video_path
            )
            # Clean up concat list file
            # concat_file_path.unlink(missing_ok=True)
            return str(final_video_path)
        except subprocess.TimeoutExpired:
            logging.error("ffmpeg concatenation command timed out.")
            return ""
        except subprocess.CalledProcessError as e:
            logging.error(f"Error concatenating video segments: {e.stderr}")
            # Fallback: if concatenation fails, and there's only one valid segment, copy it.
            if len(valid_segment_paths) == 1:
                try:
                    shutil.copy(valid_segment_paths[0], final_video_path)
                    logging.info(
                        f"Fallback: Copied single segment {valid_segment_paths[0]} as final video {final_video_path}"
                    )
                    return str(final_video_path)
                except Exception as copy_err:
                    logging.error(f"Fallback copy failed: {copy_err}")
            return ""

    def create_slideshow_video(
        self,
        image_paths: list[str],
        audio_paths: list[str],
        final_video_name: str = "final_slideshow.mp4",
        target_resolution: tuple[int, int] = (1080, 1920),
    ) -> str:
        """Creates a slideshow video from lists of images and corresponding audio files.

        Args:
            image_paths: List of paths to image files.
            audio_paths: List of paths to audio files. Must match length of image_paths.
            final_video_name: The name of the output final video.
            target_resolution: Target resolution for the video (width, height).

        Returns:
            Path to the final slideshow video, or empty string if failed.
        """
        if not image_paths or not audio_paths:
            logging.error("Image paths or audio paths list is empty.")
            return ""
        if len(image_paths) != len(audio_paths):
            logging.error(
                f"Mismatch between number of images ({len(image_paths)}) and audio files ({len(audio_paths)})."
            )
            return ""

        segment_video_paths = []
        num_segments_to_create = min(len(image_paths), len(audio_paths))

        for i in range(num_segments_to_create):
            image_p = image_paths[i]
            audio_p = audio_paths[i]
            logging.info(
                f"Creating segment {i+1}/{num_segments_to_create} with image '{Path(image_p).name}' and audio '{Path(audio_p).name}'"
            )
            segment_path = self.create_segment_video(
                image_p, audio_p, i, target_resolution
            )
            if segment_path:
                segment_video_paths.append(segment_path)
            else:
                logging.warning(
                    f"Failed to create video segment for image {i+1} and audio {i+1}. Skipping."
                )

        if not segment_video_paths:
            logging.error(
                "No video segments were successfully created. Cannot assemble final video."
            )
            return ""

        return self.concatenate_segments(segment_video_paths, final_video_name)
