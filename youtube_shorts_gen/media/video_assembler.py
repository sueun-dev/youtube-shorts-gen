import logging
import math
import os
import shutil
import subprocess
import tempfile
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
            logging.error(f"Image file not found: {image_path} for segment {index + 1}")
            return ""
        if not Path(audio_path).exists():
            logging.error(f"Audio file not found: {audio_path} for segment {index + 1}")
            return ""

        output_path = self.segments_dir / f"segment_{index + 1}.mp4"
        duration = self._get_audio_duration(audio_path)

        if duration <= 0:
            logging.error(
                f"Audio duration is invalid for {audio_path},"
                f"cannot create segment {index+1}."
            )
            return ""

        target_w, target_h = target_resolution

        # FFmpeg command to scale, pad, and combine image and audio
        # This command creates a 9:16 video. It scales the image to fit within 1080
        # width, then pads the height to 1920 if necessary, or scales to fit 1920
        # width.
        # It prioritizes fitting the width and then padding vertically (black bars
        # if landscape image).
        # For portrait images, it will fit height and pad horizontally (bars
        # left/right).
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
            (
                f"scale={target_w}:-2,split[blur][fg];"
                f"[blur]boxblur=10:1,scale={target_w}:{target_h}[bg];"
                f"[bg][fg]overlay=(W-w)/2:(H-h)/2"
            ),
            "-shortest",  # End encoding when shortest input stream ends
            "-t",
            str(duration),  # Set duration explicitly
            str(output_path),
        ]

        try:
            logging.info(
                f"Creating video segment {index + 1} with duration {duration}s:"
                f"{output_path}"
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
            # Fallback: if concatenation fails with only one valid segment, copy it.
            if len(valid_segment_paths) == 1:
                try:
                    shutil.copy(valid_segment_paths[0], final_video_path)
                    logging.info(
                        f"Fallback: Copied single segment {valid_segment_paths[0]}"
                        f"as final video {final_video_path}"
                    )
                    return str(final_video_path)
                except Exception as copy_err:
                    logging.error(f"Fallback copy failed: {copy_err}")
            return ""

    def merge_audio_video(self, video_path: str, audio_path: str, output_path: str) -> str:
        """Merge a video file with an audio file, replacing the original audio.

        Args:
            video_path: Path to the video file
            audio_path: Path to the audio file
            output_path: Path where the merged video will be saved

        Returns:
            Path to the merged video file, or empty string if failed
        """
        if not Path(video_path).exists():
            logging.error(f"Video file not found: {video_path}")
            return ""
        if not Path(audio_path).exists():
            logging.error(f"Audio file not found: {audio_path}")
            return ""

        # Get the duration of both video and audio
        video_duration = self._get_video_duration(video_path)
        audio_duration = self._get_audio_duration(audio_path)

        # Use the shorter of the two durations
        duration = min(video_duration, audio_duration)
        if duration <= 0:
            logging.error(f"Invalid duration for video or audio: {video_path}, {audio_path}")
            return ""

        # FFmpeg command to merge video and audio
        ffmpeg_command = [
            "ffmpeg",
            "-y",
            "-i", video_path,  # Input video
            "-i", audio_path,  # Input audio
            "-map", "0:v",     # Use video from first input
            "-map", "1:a",     # Use audio from second input
            "-c:v", "copy",    # Copy video codec
            "-c:a", "aac",     # Re-encode audio
            "-b:a", "192k",    # Audio bitrate
            "-shortest",       # End when the shortest input ends
            output_path
        ]

        try:
            subprocess.run(ffmpeg_command, check=True, capture_output=True, text=True, timeout=120)
            logging.info(f"Successfully merged video and audio into: {output_path}")
            return output_path
        except subprocess.TimeoutExpired:
            logging.error("ffmpeg merge command timed out.")
            return ""
        except subprocess.CalledProcessError as e:
            logging.error(f"Error merging video and audio: {e.stderr}")
            return ""

    def _get_video_duration(self, video_path: str) -> float:
        """Get the duration of a video file using ffprobe."""
        try:
            result = subprocess.run(
                [
                    "ffprobe",
                    "-v", "error",
                    "-show_entries",
                    "format=duration",
                    "-of",
                    "default=noprint_wrappers=1:nokey=1",
                    video_path,
                ],
                capture_output=True,
                text=True,
                check=True,
                timeout=30,
            )
            return float(result.stdout.strip())
        except (subprocess.TimeoutExpired, subprocess.CalledProcessError, ValueError) as e:
            logging.error(f"Error getting video duration for {video_path}: {e}")
            return 0.0
            
    def create_looped_video(self, input_video_path: str, target_duration: float, output_video_path: str) -> str:
        """Create a looped video that matches or exceeds the target duration.
        
        Args:
            input_video_path: Path to the input video file
            target_duration: Target duration in seconds for the output video
            output_video_path: Path where the looped video will be saved
            
        Returns:
            Path to the looped video file, or empty string if failed
        """
        if not Path(input_video_path).exists():
            logging.error(f"Input video file not found: {input_video_path}")
            return ""
            
        # Get the duration of the input video
        input_duration = self._get_video_duration(input_video_path)
        if input_duration <= 0:
            logging.error(f"Could not determine duration of input video: {input_video_path}")
            return ""
            
        # Calculate how many times we need to loop the video
        loop_count = math.ceil(target_duration / input_duration)
        logging.info(f"Creating looped video: input duration={input_duration}s, target={target_duration}s, loops={loop_count}")
        
        # Create a temporary file listing the input video multiple times
        concat_file_path = Path(output_video_path).parent / f"loop_list_{Path(output_video_path).stem}.txt"
        abs_input_path = Path(input_video_path).resolve()
        
        with open(concat_file_path, "w", encoding="utf-8") as f:
            for _ in range(loop_count):
                f.write(f"file '{abs_input_path}'\n")
                
        # Use ffmpeg to concatenate the video with itself multiple times
        ffmpeg_command = [
            "ffmpeg",
            "-y",
            "-f", "concat",
            "-safe", "0",
            "-i", str(concat_file_path),
            "-c", "copy",
            str(output_video_path)
        ]
        
        try:
            subprocess.run(ffmpeg_command, check=True, capture_output=True, text=True, timeout=120)
            logging.info(f"Successfully created looped video: {output_video_path} (duration ~{loop_count * input_duration:.2f}s)")
            # Clean up the temporary file
            concat_file_path.unlink(missing_ok=True)
            return output_video_path
        except subprocess.TimeoutExpired:
            logging.error("ffmpeg looping command timed out.")
            return ""
        except subprocess.CalledProcessError as e:
            logging.error(f"Error creating looped video: {e.stderr}")
            return ""

    def create_segment_video_with_runway(self, video_path: str, audio_path: str, index: int) -> str:
        """Create a video segment from a Runway-generated video and audio file.
        
        This method takes a video generated by Runway AI and synchronizes it with TTS audio.
        If the video is shorter than the audio, it will loop the video to match the audio duration.
        
        Args:
            video_path: Path to the Runway-generated video file.
            audio_path: Path to the TTS audio file.
            index: The segment index (for filename).
            
        Returns:
            Path to the created video segment, or empty string if failed.
        """
        if not Path(video_path).exists():
            logging.error(f"Runway video file not found: {video_path} for segment {index + 1}")
            return ""
        if not Path(audio_path).exists():
            logging.error(f"Audio file not found: {audio_path} for segment {index + 1}")
            return ""
        
        # Get durations of video and audio
        video_duration = self._get_video_duration(video_path)
        audio_duration = self._get_audio_duration(audio_path)
        
        if video_duration <= 0 or audio_duration <= 0:
            logging.error(
                f"Invalid durations for segment {index+1}: "
                f"video={video_duration}s, audio={audio_duration}s"
            )
            return ""
        
        output_path = self.segments_dir / f"segment_{index + 1}.mp4"
        
        # If video is shorter than audio, we need to loop the video
        if video_duration < audio_duration:
            logging.info(
                f"Video duration ({video_duration}s) is shorter than "
                f"audio duration ({audio_duration}s). Creating looped video."
            )
            looped_video_path = self.segments_dir / f"looped_video_{index + 1}.mp4"
            looped_result = self.create_looped_video(
                video_path, audio_duration, str(looped_video_path)
            )
            if not looped_result:
                logging.error(f"Failed to create looped video for segment {index + 1}")
                return ""
            video_path = looped_result
        
        # Merge the video with the audio, replacing the original audio track
        return self.merge_audio_video(video_path, audio_path, str(output_path))

    def create_video_from_images(
        self,
        image_paths: list[str],
        output_filename: str = "timelapse_video.mp4",
        fps: int = 4,
        target_resolution: tuple[int, int] = (1080, 1920),
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
                logging.error(f"Image file not found: {img_path} at position {i}")
                return ""

        # Create a temporary directory for processed images
        temp_dir = self.run_dir / "temp_images"
        temp_dir.mkdir(exist_ok=True)

        # Process images to ensure consistent resolution
        processed_images = []
        target_w, target_h = target_resolution

        for i, img_path in enumerate(image_paths):
            output_img = temp_dir / f"processed_{i:04d}.png"
            
            # Scale and pad the image to target resolution
            try:
                subprocess.run(
                    [
                        "ffmpeg",
                        "-y",
                        "-i", img_path,
                        "-vf", f"scale=w={target_w}:h={target_h}:force_original_aspect_ratio=decrease,"
                               f"pad={target_w}:{target_h}:(ow-iw)/2:(oh-ih)/2",
                        str(output_img)
                    ],
                    check=True,
                    capture_output=True,
                )
                processed_images.append(str(output_img))
            except subprocess.CalledProcessError as e:
                logging.error(f"Failed to process image {img_path}: {e.stderr}")
                return ""

        # Create the output video path
        output_path = self.run_dir / output_filename

        # Use FFmpeg to create a video from the processed images
        try:
            subprocess.run(
                [
                    "ffmpeg",
                    "-y",
                    "-framerate", str(fps),
                    "-i", f"{temp_dir}/processed_%04d.png",
                    "-c:v", "libx264",
                    "-pix_fmt", "yuv420p",
                    "-preset", "medium",  # Balance between encoding speed and compression
                    "-crf", "23",  # Constant Rate Factor for quality (lower is better)
                    str(output_path)
                ],
                check=True,
                capture_output=True,
            )
            logging.info(f"Successfully created video from {len(processed_images)} images: {output_path}")
            
            # Clean up temporary files
            shutil.rmtree(temp_dir, ignore_errors=True)
            
            return str(output_path)
        except subprocess.CalledProcessError as e:
            logging.error(f"Failed to create video from images: {e.stderr}")
            return ""

    def create_smooth_timelapse(
        self,
        image_paths: list[str],
        output_filename: str = "smooth_timelapse.mp4",
        transition_duration: float = 1.0,
        frame_duration: float = 1.0,
        target_resolution: tuple[int, int] = (1080, 1920),
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
            transition_duration: Duration of crossfade transition between images in seconds.
            frame_duration: Duration each frame is displayed in seconds.
            target_resolution: Target resolution (width, height) for the video.

        Returns:
            Path to the created video, or empty string if failed.
        """
        if not image_paths:
            logging.error("No image paths provided for smooth timelapse creation")
            return ""
            
        if len(image_paths) < 2:
            logging.warning("Only one image provided. Creating standard video without transitions.")
            return self.create_video_from_images([image_paths[0]], output_filename, 1, target_resolution)

        # Create a temporary directory for processed images and transition videos
        temp_dir = Path(tempfile.mkdtemp(dir=self.run_dir))
        processed_dir = temp_dir / "processed"
        processed_dir.mkdir(exist_ok=True)
        transitions_dir = temp_dir / "transitions"
        transitions_dir.mkdir(exist_ok=True)
        
        # Process each image to ensure consistent resolution
        processed_images = []
        target_w, target_h = target_resolution

        # If frame_durations provided, validate length else ignore
        if frame_durations and len(frame_durations) != len(image_paths):
            logging.warning("frame_durations length mismatch; ignoring custom durations")
            frame_durations = None

        # Step 1: Process all images to consistent resolution
        for i, img_path in enumerate(image_paths):
            if not os.path.exists(img_path):
                logging.error(f"Image file not found: {img_path}")
                continue

            output_img = processed_dir / f"processed_{i:04d}.png"
            try:
                subprocess.run(
                    [
                        "ffmpeg",
                        "-y",
                        "-i", img_path,
                        "-vf", f"scale=w={target_w}:h={target_h}:force_original_aspect_ratio=decrease,"
                               f"pad={target_w}:{target_h}:(ow-iw)/2:(oh-ih)/2",
                        str(output_img)
                    ],
                    check=True,
                    capture_output=True,
                )
                processed_images.append(str(output_img))
            except subprocess.CalledProcessError as e:
                logging.error(f"Failed to process image {img_path}: {e.stderr}")
                shutil.rmtree(temp_dir, ignore_errors=True)
                return ""

        # Step 2: Create individual clips for each image
        image_clips = []
        for i, img_path in enumerate(processed_images):
            # Create a static video clip from each image
            output_clip = transitions_dir / f"clip_{i:04d}.mp4"
            try:
                subprocess.run(
                    [
                        "ffmpeg",
                        "-y",
                        "-loop", "1",
                        "-i", img_path,
                        "-c:v", "libx264",
                        "-t", str(frame_durations[i] if frame_durations else frame_duration),
                        "-pix_fmt", "yuv420p",
                        "-r", "30",  # 30fps for smooth playback
                        str(output_clip)
                    ],
                    check=True,
                    capture_output=True,
                )
                image_clips.append(str(output_clip))
            except subprocess.CalledProcessError as e:
                logging.error(f"Failed to create image clip {i}: {e.stderr}")
                shutil.rmtree(temp_dir, ignore_errors=True)
                return ""

        # Step 3: Create crossfade transitions between consecutive images
        transition_clips = []
        for i in range(len(processed_images) - 1):
            output_transition = transitions_dir / f"transition_{i:04d}_{i+1:04d}.mp4"
            try:
                # Create crossfade transition between images
                subprocess.run(
                    [
                        "ffmpeg",
                        "-y",
                        "-i", processed_images[i],
                        "-i", processed_images[i+1],
                        "-filter_complex", f"xfade=transition={transition_type}:duration={transition_duration}:offset=0,fps=30",
                        "-pix_fmt", "yuv420p",
                        str(output_transition)
                    ],
                    check=True,
                    capture_output=True,
                )
                transition_clips.append(str(output_transition))
            except subprocess.CalledProcessError as e:
                logging.error(f"Failed to create transition between images {i} and {i+1}: {e.stderr}")
                shutil.rmtree(temp_dir, ignore_errors=True)
                return ""

        # Step 4: Create a file list for concatenation
        concat_file = temp_dir / "concat_list.txt"
        with open(concat_file, "w") as f:
            for i in range(len(image_clips)):
                # Add the image clip
                f.write(f"file '{image_clips[i]}'\n")
                # Add transition clip if not the last image
                if i < len(transition_clips):
                    f.write(f"file '{transition_clips[i]}'\n")

        # Step 5: Concatenate all clips into final video
        output_path = self.run_dir / output_filename
        try:
            subprocess.run(
                [
                    "ffmpeg",
                    "-y",
                    "-f", "concat",
                    "-safe", "0",
                    "-i", str(concat_file),
                    "-c:v", "libx264",
                    "-pix_fmt", "yuv420p",
                    "-preset", "medium",
                    "-crf", "23",
                    str(output_path)
                ],
                check=True,
                capture_output=True,
            )
            logging.info(f"Successfully created smooth timelapse video: {output_path}")
            
            # If background music provided, merge audio
            if music_path and Path(music_path).exists():
                video_with_audio = output_path.with_name(output_path.stem + "_audio.mp4")
                try:
                    subprocess.run(
                        [
                            "ffmpeg",
                            "-y",
                            "-i", str(output_path),
                            "-i", music_path,
                            "-c:v", "copy",
                            "-c:a", "aac",
                            "-shortest",
                            str(video_with_audio),
                        ],
                        check=True,
                        capture_output=True,
                    )
                    output_path = video_with_audio
                except subprocess.CalledProcessError as e:
                    logging.error("Failed to merge background music: %s", e.stderr)
            
            # Clean up temporary files
            shutil.rmtree(temp_dir, ignore_errors=True)
            
            return str(output_path)
        except subprocess.CalledProcessError as e:
            logging.error(f"Failed to concatenate clips into final video: {e.stderr}")
            shutil.rmtree(temp_dir, ignore_errors=True)
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
                f"Mismatch between number of images ({len(image_paths)})"
                f"and audio files ({len(audio_paths)})."
            )
            return ""

        segment_video_paths = []
        num_segments_to_create = min(len(image_paths), len(audio_paths))

        for i in range(num_segments_to_create):
            image_p = image_paths[i]
            audio_p = audio_paths[i]
            logging.info(
                f"Creating segment {i+1}/{num_segments_to_create}"
                f"with image '{Path(image_p).name}' and audio '{Path(audio_p).name}'"
            )
            segment_path = self.create_segment_video(
                image_p, audio_p, i, target_resolution
            )
            if segment_path:
                segment_video_paths.append(segment_path)
            else:
                logging.warning(
                    f"Failed to create video segment for image {i+1}"
                    f"and audio {i+1}. Skipping."
                )

        if not segment_video_paths:
            logging.error(
                "No video segments were successfully created."
                "Cannot assemble final video."
            )
            return ""

        return self.concatenate_segments(segment_video_paths, final_video_name)
