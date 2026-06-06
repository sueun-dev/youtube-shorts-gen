import logging
import math
import os
import shutil
import subprocess
import tempfile
from pathlib import Path

from youtube_shorts_gen.utils.config import (
    FFMPEG_AUDIO_BITRATE,
    FFMPEG_AUDIO_CODEC,
    FFMPEG_CONCAT_TIMEOUT_SECONDS,
    FFMPEG_CRF,
    FFMPEG_PRESET,
    FFMPEG_SEGMENT_TIMEOUT_SECONDS,
    FFMPEG_VIDEO_CODEC,
    FFPROBE_TIMEOUT_SECONDS,
    OUTPUT_VIDEO_FILENAME,
    VIDEO_FPS,
    VIDEO_RESOLUTION,
)


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
                timeout=FFPROBE_TIMEOUT_SECONDS,
            )
            return float(result.stdout.strip())
        except subprocess.TimeoutExpired:
            logging.error("ffprobe timed out getting duration for %s", audio_path)
            return 0.0
        except subprocess.CalledProcessError as e:
            logging.error("ffprobe error for %s: %s", audio_path, e.stderr)
            return 0.0
        except ValueError:
            logging.error(
                "Could not parse duration from ffprobe output for %s", audio_path
            )
            return 0.0

    def _get_video_duration(self, video_path: str) -> float:
        """Get the duration of a video file using ffprobe."""
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
                    video_path,
                ],
                capture_output=True,
                text=True,
                check=True,
                timeout=FFPROBE_TIMEOUT_SECONDS,
            )
            return float(result.stdout.strip())
        except (
            subprocess.TimeoutExpired,
            subprocess.CalledProcessError,
            ValueError,
        ) as e:
            logging.error("Error getting video duration for %s: %s", video_path, e)
            return 0.0

    def create_segment_video(
        self,
        image_path: str,
        audio_path: str,
        index: int,
        target_resolution: tuple[int, int] = VIDEO_RESOLUTION,
    ) -> str:
        """Create a video segment from an image and audio file, scaled and padded
        for shorts.

        Args:
            image_path: Path to the image file.
            audio_path: Path to the audio file.
            index: The segment index (for filename).
            target_resolution: Target video resolution (width, height) for
                YouTube Shorts.

        Returns:
            Path to the created video segment, or empty string if failed.
        """
        if not Path(image_path).exists():
            logging.error(
                "Image file not found: %s for segment %d", image_path, index + 1
            )
            return ""
        if not Path(audio_path).exists():
            logging.error(
                "Audio file not found: %s for segment %d", audio_path, index + 1
            )
            return ""

        output_path = self.segments_dir / f"segment_{index + 1}.mp4"
        duration = self._get_audio_duration(audio_path)

        if duration <= 0:
            logging.error(
                "Audio duration is invalid for %s, cannot create segment %d.",
                audio_path,
                index + 1,
            )
            return ""

        target_w, target_h = target_resolution

        # FFmpeg command to scale, pad, and combine image and audio.
        # Scales the image to the target width, blurs a background copy to fill
        # the frame, then overlays the foreground centered (9:16 shorts layout).
        ffmpeg_command = [
            "ffmpeg",
            "-y",
            "-loop",
            "1",
            "-i",
            image_path,
            "-i",
            audio_path,
            "-c:v",
            FFMPEG_VIDEO_CODEC,
            "-tune",
            "stillimage",
            "-c:a",
            FFMPEG_AUDIO_CODEC,
            "-b:a",
            FFMPEG_AUDIO_BITRATE,
            "-pix_fmt",
            "yuv420p",
            "-vf",
            (
                f"scale={target_w}:-2,split[blur][fg];"
                f"[blur]boxblur=10:1,scale={target_w}:{target_h}[bg];"
                f"[bg][fg]overlay=(W-w)/2:(H-h)/2"
            ),
            "-shortest",
            "-t",
            str(duration),
            str(output_path),
        ]

        try:
            logging.info(
                "Creating video segment %d with duration %ss: %s",
                index + 1,
                duration,
                output_path,
            )
            subprocess.run(
                ffmpeg_command,
                check=True,
                capture_output=True,
                text=True,
                timeout=FFMPEG_SEGMENT_TIMEOUT_SECONDS,
            )
            logging.info(
                "Successfully created video segment %d: %s", index + 1, output_path
            )
            return str(output_path)
        except subprocess.TimeoutExpired:
            logging.error("ffmpeg command timed out for segment %d.", index + 1)
            return ""
        except subprocess.CalledProcessError as e:
            logging.error("Error creating video segment %d: %s", index + 1, e.stderr)
            return ""

    def concatenate_segments(
        self,
        segment_paths: list[str],
        final_video_name: str = OUTPUT_VIDEO_FILENAME,
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

        logging.info("Concatenating %d video segments.", len(valid_segment_paths))

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
            "0",
            "-i",
            str(concat_file_path),
            "-c",
            "copy",
            str(final_video_path),
        ]

        try:
            subprocess.run(
                ffmpeg_command,
                check=True,
                capture_output=True,
                text=True,
                timeout=FFMPEG_CONCAT_TIMEOUT_SECONDS,
            )
            logging.info(
                "Successfully concatenated segments into: %s", final_video_path
            )
            return str(final_video_path)
        except subprocess.TimeoutExpired:
            logging.error("ffmpeg concatenation command timed out.")
            return ""
        except subprocess.CalledProcessError as e:
            logging.error("Error concatenating video segments: %s", e.stderr)
            # Fallback: if concatenation fails with only one valid segment, copy it.
            if len(valid_segment_paths) == 1:
                try:
                    shutil.copy(valid_segment_paths[0], final_video_path)
                    logging.info(
                        "Fallback: copied single segment %s as final video %s",
                        valid_segment_paths[0],
                        final_video_path,
                    )
                    return str(final_video_path)
                except OSError as copy_err:
                    logging.error("Fallback copy failed: %s", copy_err)
            return ""

    def merge_audio_video(
        self, video_path: str, audio_path: str, output_path: str
    ) -> str:
        """Merge a video file with an audio file, replacing the original audio.

        Args:
            video_path: Path to the video file
            audio_path: Path to the audio file
            output_path: Path where the merged video will be saved

        Returns:
            Path to the merged video file, or empty string if failed
        """
        if not Path(video_path).exists():
            logging.error("Video file not found: %s", video_path)
            return ""
        if not Path(audio_path).exists():
            logging.error("Audio file not found: %s", audio_path)
            return ""

        # Use the shorter of the two durations
        video_duration = self._get_video_duration(video_path)
        audio_duration = self._get_audio_duration(audio_path)
        duration = min(video_duration, audio_duration)
        if duration <= 0:
            logging.error(
                "Invalid duration for video or audio: %s, %s",
                video_path,
                audio_path,
            )
            return ""

        ffmpeg_command = [
            "ffmpeg",
            "-y",
            "-i",
            video_path,
            "-i",
            audio_path,
            "-map",
            "0:v",
            "-map",
            "1:a",
            "-c:v",
            "copy",
            "-c:a",
            FFMPEG_AUDIO_CODEC,
            "-b:a",
            FFMPEG_AUDIO_BITRATE,
            "-shortest",
            output_path,
        ]

        try:
            subprocess.run(
                ffmpeg_command,
                check=True,
                capture_output=True,
                text=True,
                timeout=FFMPEG_CONCAT_TIMEOUT_SECONDS,
            )
            logging.info("Successfully merged video and audio into: %s", output_path)
            return output_path
        except subprocess.TimeoutExpired:
            logging.error("ffmpeg merge command timed out.")
            return ""
        except subprocess.CalledProcessError as e:
            logging.error("Error merging video and audio: %s", e.stderr)
            return ""

    def create_looped_video(
        self,
        input_video_path: str,
        target_duration: float,
        output_video_path: str,
    ) -> str:
        """Create a looped video that matches or exceeds the target duration.

        Args:
            input_video_path: Path to the input video file
            target_duration: Target duration in seconds for the output video
            output_video_path: Path where the looped video will be saved

        Returns:
            Path to the looped video file, or empty string if failed
        """
        if not Path(input_video_path).exists():
            logging.error("Input video file not found: %s", input_video_path)
            return ""

        input_duration = self._get_video_duration(input_video_path)
        if input_duration <= 0:
            logging.error(
                "Could not determine duration of input video: %s", input_video_path
            )
            return ""

        # Calculate how many times we need to loop the video
        loop_count = math.ceil(target_duration / input_duration)
        logging.info(
            "Creating looped video: input duration=%ss, target=%ss, loops=%d",
            input_duration,
            target_duration,
            loop_count,
        )

        # Create a temporary file listing the input video multiple times
        output_video = Path(output_video_path)
        concat_file_path = output_video.parent / f"loop_list_{output_video.stem}.txt"
        abs_input_path = Path(input_video_path).resolve()

        with open(concat_file_path, "w", encoding="utf-8") as f:
            for _ in range(loop_count):
                f.write(f"file '{abs_input_path}'\n")

        ffmpeg_command = [
            "ffmpeg",
            "-y",
            "-f",
            "concat",
            "-safe",
            "0",
            "-i",
            str(concat_file_path),
            "-c",
            "copy",
            str(output_video_path),
        ]

        try:
            subprocess.run(
                ffmpeg_command,
                check=True,
                capture_output=True,
                text=True,
                timeout=FFMPEG_CONCAT_TIMEOUT_SECONDS,
            )
            logging.info(
                "Successfully created looped video: %s (duration ~%.2fs)",
                output_video_path,
                loop_count * input_duration,
            )
            return output_video_path
        except subprocess.TimeoutExpired:
            logging.error("ffmpeg looping command timed out.")
            return ""
        except subprocess.CalledProcessError as e:
            logging.error("Error creating looped video: %s", e.stderr)
            return ""
        finally:
            concat_file_path.unlink(missing_ok=True)

    def create_segment_video_with_runway(
        self, video_path: str, audio_path: str, index: int
    ) -> str:
        """Create a video segment from a Runway-generated video and audio file.

        This method takes a video generated by Runway AI and synchronizes it with
        TTS audio. If the video is shorter than the audio, it loops the video to
        match the audio duration.

        Args:
            video_path: Path to the Runway-generated video file.
            audio_path: Path to the TTS audio file.
            index: The segment index (for filename).

        Returns:
            Path to the created video segment, or empty string if failed.
        """
        if not Path(video_path).exists():
            logging.error(
                "Runway video file not found: %s for segment %d",
                video_path,
                index + 1,
            )
            return ""
        if not Path(audio_path).exists():
            logging.error(
                "Audio file not found: %s for segment %d", audio_path, index + 1
            )
            return ""

        video_duration = self._get_video_duration(video_path)
        audio_duration = self._get_audio_duration(audio_path)

        if video_duration <= 0 or audio_duration <= 0:
            logging.error(
                "Invalid durations for segment %d: video=%ss, audio=%ss",
                index + 1,
                video_duration,
                audio_duration,
            )
            return ""

        output_path = self.segments_dir / f"segment_{index + 1}.mp4"

        # If video is shorter than audio, loop the video to fill the audio.
        if video_duration < audio_duration:
            logging.info(
                "Video duration (%ss) is shorter than audio duration (%ss). "
                "Creating looped video.",
                video_duration,
                audio_duration,
            )
            looped_video_path = self.segments_dir / f"looped_video_{index + 1}.mp4"
            looped_result = self.create_looped_video(
                video_path, audio_duration, str(looped_video_path)
            )
            if not looped_result:
                logging.error("Failed to create looped video for segment %d", index + 1)
                return ""
            video_path = looped_result

        # Merge the video with the audio, replacing the original audio track
        return self.merge_audio_video(video_path, audio_path, str(output_path))

    def create_video_from_images(
        self,
        image_paths: list[str],
        output_filename: str = "timelapse_video.mp4",
        fps: int = 4,
        target_resolution: tuple[int, int] = VIDEO_RESOLUTION,
    ) -> str:
        """Creates a video from a sequence of images without audio.

        Args:
            image_paths: List of paths to image files in sequence order.
            output_filename: The name of the output video file.
            fps: Frames per second for the output video.
            target_resolution: Target resolution for the video (width, height).

        Returns:
            Path to the created video, or empty string if failed.
        """
        if not image_paths:
            logging.error("No image paths provided for video creation.")
            return ""

        # Ensure all images exist
        for i, img_path in enumerate(image_paths):
            if not Path(img_path).exists():
                logging.error("Image file not found: %s at position %d", img_path, i)
                return ""

        # Create a temporary directory for processed images
        temp_dir = self.run_dir / "temp_images"
        temp_dir.mkdir(exist_ok=True)

        try:
            target_w, target_h = target_resolution
            processed_images: list[str] = []

            for i, img_path in enumerate(image_paths):
                output_img = temp_dir / f"processed_{i:04d}.png"
                try:
                    subprocess.run(
                        [
                            "ffmpeg",
                            "-y",
                            "-i",
                            img_path,
                            "-vf",
                            (
                                f"scale=w={target_w}:h={target_h}:"
                                "force_original_aspect_ratio=decrease,"
                                f"pad={target_w}:{target_h}:(ow-iw)/2:(oh-ih)/2"
                            ),
                            str(output_img),
                        ],
                        check=True,
                        capture_output=True,
                    )
                    processed_images.append(str(output_img))
                except subprocess.CalledProcessError as e:
                    logging.error("Failed to process image %s: %s", img_path, e.stderr)
                    return ""

            output_path = self.run_dir / output_filename

            try:
                subprocess.run(
                    [
                        "ffmpeg",
                        "-y",
                        "-framerate",
                        str(fps),
                        "-i",
                        f"{temp_dir}/processed_%04d.png",
                        "-c:v",
                        FFMPEG_VIDEO_CODEC,
                        "-pix_fmt",
                        "yuv420p",
                        "-preset",
                        FFMPEG_PRESET,
                        "-crf",
                        FFMPEG_CRF,
                        str(output_path),
                    ],
                    check=True,
                    capture_output=True,
                )
                logging.info(
                    "Successfully created video from %d images: %s",
                    len(processed_images),
                    output_path,
                )
                return str(output_path)
            except subprocess.CalledProcessError as e:
                logging.error("Failed to create video from images: %s", e.stderr)
                return ""
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)

    def _normalise_images(
        self,
        image_paths: list[str],
        processed_dir: Path,
        target_resolution: tuple[int, int],
    ) -> tuple[list[str], list[int]] | None:
        """Scale and pad images to a consistent resolution.

        Returns ``(processed_image_paths, kept_indices)`` — where
        ``kept_indices`` are the original positions that produced an image (a
        missing source is skipped) so callers can keep per-frame durations
        aligned — or ``None`` on a processing failure.
        """
        target_w, target_h = target_resolution
        processed_images: list[str] = []
        kept_indices: list[int] = []
        for i, img_path in enumerate(image_paths):
            if not os.path.exists(img_path):
                logging.error("Image file not found: %s", img_path)
                continue

            output_img = processed_dir / f"processed_{i:04d}.png"
            try:
                subprocess.run(
                    [
                        "ffmpeg",
                        "-y",
                        "-i",
                        img_path,
                        "-vf",
                        (
                            f"scale=w={target_w}:h={target_h}:"
                            "force_original_aspect_ratio=decrease,"
                            f"pad={target_w}:{target_h}:(ow-iw)/2:(oh-ih)/2"
                        ),
                        str(output_img),
                    ],
                    check=True,
                    capture_output=True,
                )
                processed_images.append(str(output_img))
                kept_indices.append(i)
            except subprocess.CalledProcessError as e:
                logging.error("Failed to process image %s: %s", img_path, e.stderr)
                return None
        return processed_images, kept_indices

    def _build_image_clips(
        self,
        processed_images: list[str],
        transitions_dir: Path,
        frame_duration: float,
        frame_durations: list[float] | None,
    ) -> list[str] | None:
        """Create a static video clip for each processed image.

        Returns the list of clip paths, or None on failure.
        """
        image_clips: list[str] = []
        for i, img_path in enumerate(processed_images):
            output_clip = transitions_dir / f"clip_{i:04d}.mp4"
            clip_duration = frame_durations[i] if frame_durations else frame_duration
            try:
                subprocess.run(
                    [
                        "ffmpeg",
                        "-y",
                        "-loop",
                        "1",
                        "-i",
                        img_path,
                        "-c:v",
                        FFMPEG_VIDEO_CODEC,
                        "-t",
                        str(clip_duration),
                        "-pix_fmt",
                        "yuv420p",
                        "-r",
                        str(VIDEO_FPS),
                        str(output_clip),
                    ],
                    check=True,
                    capture_output=True,
                )
                image_clips.append(str(output_clip))
            except subprocess.CalledProcessError as e:
                logging.error("Failed to create image clip %d: %s", i, e.stderr)
                return None
        return image_clips

    def _build_xfade_filter(
        self,
        processed_images: list[str],
        transitions_dir: Path,
        transition_type: str,
        transition_duration: float,
    ) -> list[str] | None:
        """Create crossfade transition clips between consecutive images.

        Returns the list of transition clip paths, or None on failure.
        """
        transition_clips: list[str] = []
        for i in range(len(processed_images) - 1):
            output_transition = transitions_dir / f"transition_{i:04d}_{i + 1:04d}.mp4"
            try:
                # Loop each still image for the transition's length so xfade has
                # real-duration streams to blend; without -loop/-t each PNG is a
                # single frame and the crossfade collapses to one frame.
                subprocess.run(
                    [
                        "ffmpeg",
                        "-y",
                        "-loop",
                        "1",
                        "-t",
                        str(transition_duration),
                        "-i",
                        processed_images[i],
                        "-loop",
                        "1",
                        "-t",
                        str(transition_duration),
                        "-i",
                        processed_images[i + 1],
                        "-filter_complex",
                        (
                            f"xfade=transition={transition_type}:"
                            f"duration={transition_duration}:offset=0,"
                            f"fps={VIDEO_FPS}"
                        ),
                        "-pix_fmt",
                        "yuv420p",
                        str(output_transition),
                    ],
                    check=True,
                    capture_output=True,
                )
                transition_clips.append(str(output_transition))
            except subprocess.CalledProcessError as e:
                logging.error(
                    "Failed to create transition between images %d and %d: %s",
                    i,
                    i + 1,
                    e.stderr,
                )
                return None
        return transition_clips

    def _encode_with_music(self, video_path: Path, music_path: str | None) -> Path:
        """Merge background music onto a video, returning the resulting path.

        On failure the original video path is returned unchanged.
        """
        if not (music_path and Path(music_path).exists()):
            return video_path

        video_with_audio = video_path.with_name(video_path.stem + "_audio.mp4")
        try:
            subprocess.run(
                [
                    "ffmpeg",
                    "-y",
                    "-i",
                    str(video_path),
                    "-i",
                    music_path,
                    "-c:v",
                    "copy",
                    "-c:a",
                    FFMPEG_AUDIO_CODEC,
                    "-shortest",
                    str(video_with_audio),
                ],
                check=True,
                capture_output=True,
            )
            return video_with_audio
        except subprocess.CalledProcessError as e:
            logging.error("Failed to merge background music: %s", e.stderr)
            return video_path

    def create_smooth_timelapse(
        self,
        image_paths: list[str],
        output_filename: str = "smooth_timelapse.mp4",
        transition_duration: float = 1.0,
        frame_duration: float = 1.0,
        target_resolution: tuple[int, int] = VIDEO_RESOLUTION,
        transition_type: str = "fade",
        music_path: str | None = None,
        frame_durations: list[float] | None = None,
    ) -> str:
        """Creates a time-lapse video with smooth transitions between images.

        This method uses crossfade transitions between images to create a more
        fluid visual experience compared to standard frame-by-frame transitions.

        Args:
            image_paths: List of paths to image files in sequence order.
            output_filename: The name of the output video file.
            transition_duration: Duration of crossfade transition in seconds.
            frame_duration: Duration each frame is displayed in seconds.
            target_resolution: Target resolution (width, height) for the video.
            transition_type: ffmpeg xfade transition name.
            music_path: Optional background music file to merge in.
            frame_durations: Optional per-frame durations matching image_paths.

        Returns:
            Path to the created video, or empty string if failed.
        """
        if not image_paths:
            logging.error("No image paths provided for smooth timelapse creation")
            return ""

        if len(image_paths) < 2:
            logging.warning(
                "Only one image provided. Creating standard video without transitions."
            )
            return self.create_video_from_images(
                [image_paths[0]], output_filename, 1, target_resolution
            )

        # If frame_durations provided, validate length else ignore
        if frame_durations and len(frame_durations) != len(image_paths):
            logging.warning(
                "frame_durations length mismatch; ignoring custom durations"
            )
            frame_durations = None

        temp_dir = Path(tempfile.mkdtemp(dir=self.run_dir))
        try:
            processed_dir = temp_dir / "processed"
            processed_dir.mkdir(exist_ok=True)
            transitions_dir = temp_dir / "transitions"
            transitions_dir.mkdir(exist_ok=True)

            # Step 1: Process all images to a consistent resolution.
            normalised = self._normalise_images(
                image_paths, processed_dir, target_resolution
            )
            if normalised is None:
                return ""
            processed_images, kept_indices = normalised
            # Keep per-frame durations aligned if any source image was skipped.
            if frame_durations is not None:
                frame_durations = [frame_durations[i] for i in kept_indices]

            # Step 2: Create individual clips for each image.
            image_clips = self._build_image_clips(
                processed_images, transitions_dir, frame_duration, frame_durations
            )
            if image_clips is None:
                return ""

            # Step 3: Create crossfade transitions between consecutive images.
            transition_clips = self._build_xfade_filter(
                processed_images,
                transitions_dir,
                transition_type,
                transition_duration,
            )
            if transition_clips is None:
                return ""

            # Step 4: Create a file list for concatenation.
            concat_file = temp_dir / "concat_list.txt"
            with open(concat_file, "w", encoding="utf-8") as f:
                for i, clip in enumerate(image_clips):
                    f.write(f"file '{clip}'\n")
                    if i < len(transition_clips):
                        f.write(f"file '{transition_clips[i]}'\n")

            # Step 5: Concatenate all clips into the final video.
            output_path = self.run_dir / output_filename
            try:
                subprocess.run(
                    [
                        "ffmpeg",
                        "-y",
                        "-f",
                        "concat",
                        "-safe",
                        "0",
                        "-i",
                        str(concat_file),
                        "-c:v",
                        FFMPEG_VIDEO_CODEC,
                        "-pix_fmt",
                        "yuv420p",
                        "-preset",
                        FFMPEG_PRESET,
                        "-crf",
                        FFMPEG_CRF,
                        str(output_path),
                    ],
                    check=True,
                    capture_output=True,
                )
                logging.info(
                    "Successfully created smooth timelapse video: %s", output_path
                )
            except subprocess.CalledProcessError as e:
                logging.error(
                    "Failed to concatenate clips into final video: %s", e.stderr
                )
                return ""

            # Step 6: Optionally merge background music.
            output_path = self._encode_with_music(output_path, music_path)
            return str(output_path)
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)

    def create_slideshow_video(
        self,
        image_paths: list[str],
        audio_paths: list[str],
        final_video_name: str = "final_slideshow.mp4",
        target_resolution: tuple[int, int] = VIDEO_RESOLUTION,
    ) -> str:
        """Creates a slideshow video from images and corresponding audio files.

        Args:
            image_paths: List of paths to image files.
            audio_paths: List of audio paths. Must match length of image_paths.
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
                "Mismatch between number of images (%d) and audio files (%d).",
                len(image_paths),
                len(audio_paths),
            )
            return ""

        segment_video_paths: list[str] = []
        num_segments_to_create = min(len(image_paths), len(audio_paths))

        for i in range(num_segments_to_create):
            image_p = image_paths[i]
            audio_p = audio_paths[i]
            logging.info(
                "Creating segment %d/%d with image '%s' and audio '%s'",
                i + 1,
                num_segments_to_create,
                Path(image_p).name,
                Path(audio_p).name,
            )
            segment_path = self.create_segment_video(
                image_p, audio_p, i, target_resolution
            )
            if segment_path:
                segment_video_paths.append(segment_path)
            else:
                logging.warning(
                    "Failed to create video segment for image %d and audio %d. "
                    "Skipping.",
                    i + 1,
                    i + 1,
                )

        if not segment_video_paths:
            logging.error(
                "No video segments were successfully created. "
                "Cannot assemble final video."
            )
            return ""

        return self.concatenate_segments(segment_video_paths, final_video_name)
