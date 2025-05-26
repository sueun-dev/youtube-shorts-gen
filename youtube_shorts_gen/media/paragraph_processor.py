"""Module for orchestrating paragraph-based content processing for video generation."""

import logging
from pathlib import Path
from typing import Any

from youtube_shorts_gen.utils.openai_client import get_openai_client

from .image_generator import (
    ImageGenerator,
)  # For potential future use if images aren't pre-existing
from .paragraph_tts import ParagraphTTS
from .text_processor import TextProcessor
from .video_assembler import VideoAssembler


class ParagraphProcessor:
    """Orchestrates the processing of text into paragraphs, pairing with images and TTS,
    and assembling them into a video.

    This class primarily expects images to be pre-generated and available in the 'images'
    subdirectory of the run_dir. It then generates text segments and TTS to match these images.
    """

    def __init__(self, run_dir: str):
        """Initialize the paragraph processor and its helper modules.

        Args:
            run_dir: Directory for the current run, used for inputs and outputs.
        """
        self.run_dir = Path(run_dir)
        self.mapping_path = self.run_dir / "paragraph_mapping.txt"
        self.images_dir = (
            self.run_dir / "images"
        )  # Expected location of pre-generated images

        # Initialize OpenAI client from the shared utility
        # This client can be passed to components that need it
        self.openai_client = get_openai_client()

        # Instantiate specialized processors
        self.text_processor = TextProcessor(run_dir, self.openai_client)
        # ImageGenerator is initialized but primarily we use existing images.
        # It could be used if, for instance, no images are found and story_text is available.
        self.image_generator = ImageGenerator(run_dir, self.openai_client)
        self.tts_generator = ParagraphTTS(
            run_dir
        )  # ParagraphTTS handles its own audio_dir
        self.video_assembler = VideoAssembler(
            run_dir
        )  # VideoAssembler handles its own segments_dir

    def _get_existing_image_paths(self) -> list[str]:
        """Retrieves and sorts paths of existing PNG images from the images directory."""
        if not self.images_dir.exists():
            logging.warning(f"Images directory not found: {self.images_dir}")
            return []

        image_paths = sorted([str(p) for p in self.images_dir.glob("*.png")])
        logging.info(f"Found {len(image_paths)} existing images in {self.images_dir}")
        return image_paths

    def _write_mapping_file(
        self,
        story_text: str,
        processed_paragraphs: list[str],
        used_image_paths: list[str],
        used_audio_paths: list[str],
        created_segment_paths: list[str],
    ) -> None:
        """Writes a mapping file detailing the processed content."""
        try:
            with open(self.mapping_path, "w", encoding="utf-8") as f:
                f.write(f"Original Story: {story_text}\n\n")
                num_entries = len(processed_paragraphs)
                for i in range(num_entries):
                    f.write(f"--- Segment {i + 1} ---\n")
                    f.write(f"Text: {processed_paragraphs[i]}\n")
                    if i < len(used_image_paths):
                        f.write(f"Image: {Path(used_image_paths[i]).name}\n")
                    if i < len(used_audio_paths):
                        f.write(f"Audio: {Path(used_audio_paths[i]).name}\n")
                    if i < len(created_segment_paths):
                        # Using relative path for cleaner mapping file
                        segment_rel_path = Path(created_segment_paths[i]).relative_to(
                            self.run_dir
                        )
                        f.write(f"Video Segment: {segment_rel_path}\n")
                    f.write("\n")
            logging.info(f"Successfully wrote mapping file to {self.mapping_path}")
        except Exception as e:
            logging.error(f"Error writing mapping file: {e}")

    def process(self, story_text: str) -> dict[str, Any]:
        """Processes story text by generating text segments, pairing with existing images,
        generating TTS, creating video segments, and concatenating them.

        Args:
            story_text: The original story text to process.

        Returns:
            A dictionary containing paths to generated assets and the final video.
        """
        logging.info(f"Starting paragraph processing for run_dir: {self.run_dir}")

        image_paths = self._get_existing_image_paths()
        if not image_paths:
            logging.warning(
                "No pre-existing images found. Cannot proceed with video generation."
            )
            # Future enhancement: Optionally generate images if story_text is available and no images exist.
            # For example:
            # initial_segments_for_images = self.text_processor.get_content_segments(story_text, summarize_long_paragraphs=False)
            # image_paths = self.image_generator.generate_images_for_prompts(initial_segments_for_images, "generated_image")
            # if not image_paths: return {"error": "No images found or could be generated."}
            return {"error": "No images found in images directory."}

        # Get text segments (paragraphs/sentences) based on the story_text
        # Summarization is handled within get_content_segments
        text_segments = self.text_processor.get_content_segments(
            story_text, summarize_long_paragraphs=True
        )
        logging.info(f"Processed story into {len(text_segments)} text segments.")

        if not text_segments:
            logging.error(
                "Text processing resulted in no segments. Cannot create TTS or video."
            )
            return {"error": "Text processing failed to produce segments."}

        # Adjust text_segments count to match available images if necessary
        num_images = len(image_paths)
        processed_paragraphs = list(text_segments)  # Make a mutable copy

        if len(processed_paragraphs) < num_images:
            logging.info(
                f"Number of text segments ({len(processed_paragraphs)}) is less than images ({num_images}). Duplicating segments."
            )
            # Simple duplication strategy: repeat segments to match image count
            original_segment_count = len(processed_paragraphs)
            if (
                original_segment_count == 0
            ):  # Should not happen if text_segments check above passed
                logging.error(
                    "Cannot duplicate segments as there are no original segments after processing"
                )
                return {
                    "error": "No text segments to align with images after initial processing."
                }
            while len(processed_paragraphs) < num_images:
                processed_paragraphs.append(
                    processed_paragraphs[
                        len(processed_paragraphs) % original_segment_count
                    ]
                )
        elif len(processed_paragraphs) > num_images:
            logging.info(
                f"Number of text segments ({len(processed_paragraphs)}) is greater than images ({num_images}). Truncating segments."
            )
            processed_paragraphs = processed_paragraphs[:num_images]

        # Ensure we only work with the number of available images
        # This also implies the number of audio files and video segments will match num_images
        num_final_segments = min(len(processed_paragraphs), num_images)
        final_text_segments = processed_paragraphs[:num_final_segments]
        final_image_paths = image_paths[:num_final_segments]

        # Generate TTS for the (potentially adjusted) text segments
        # ParagraphTTS expects a list of strings (our final_text_segments)
        audio_paths = self.tts_generator.generate_for_paragraphs(final_text_segments)
        if not audio_paths or len(audio_paths) != len(final_text_segments):
            logging.error(
                f"TTS generation failed or produced mismatched number of audio files. Expected {len(final_text_segments)}, got {len(audio_paths)}."
            )
            # Fallback or error handling: perhaps proceed without audio or with fewer segments
            # For now, consider it a critical failure for those segments.
            # We'll filter down to what we have successfully created audio for.
            # This might lead to fewer segments than images if some TTS failed.

            # Align all lists to the minimum successful outputs
            valid_audio_count = len(audio_paths)
            final_text_segments = final_text_segments[:valid_audio_count]
            final_image_paths = final_image_paths[:valid_audio_count]
            # audio_paths is already the correct list here.
            num_final_segments = valid_audio_count

            if num_final_segments == 0:
                return {"error": "TTS generation failed for all segments."}

        # Create individual video segments using VideoAssembler
        created_segment_video_paths = []
        for i in range(num_final_segments):
            segment_video_path = self.video_assembler.create_segment_video(
                image_path=final_image_paths[i], audio_path=audio_paths[i], index=i
            )
            if segment_video_path:
                created_segment_video_paths.append(segment_video_path)
            else:
                logging.warning(
                    f"Failed to create video segment {i+1}. It will be excluded."
                )

        if not created_segment_video_paths:
            logging.error("No video segments were successfully created.")
            return {"error": "Failed to create any video segments."}

        # Concatenate segments into a final video
        final_video_path = self.video_assembler.concatenate_segments(
            created_segment_video_paths, final_video_name="output_story_video.mp4"
        )

        if not final_video_path:
            logging.error("Failed to concatenate video segments into a final video.")
            # No final video, but segments might exist. The mapping file will reflect this.

        # Write mapping file
        self._write_mapping_file(
            story_text,
            final_text_segments,  # The actual text segments used for TTS and video
            final_image_paths,  # The actual image paths used
            audio_paths,  # The actual audio_paths used
            created_segment_video_paths,  # The actual segment video paths created
        )

        logging.info(f"Paragraph processing completed. Final video: {final_video_path}")
        return {
            "story": story_text,
            "processed_paragraphs": final_text_segments,
            "image_paths": final_image_paths,
            "audio_paths": audio_paths,
            "segment_paths": created_segment_video_paths,
            "final_video": final_video_path or "",  # Ensure empty string if None
        }
