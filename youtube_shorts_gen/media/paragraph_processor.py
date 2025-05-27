"""Module for orchestrating paragraph-based content processing for video generation."""

import logging
from pathlib import Path
from typing import Any

from youtube_shorts_gen.utils.openai_client import get_openai_client

from .paragraph_tts import ParagraphTTS
from .text_processor import TextProcessor
from .video_assembler import VideoAssembler


class ParagraphProcessor:
    """Orchestrates the processing of text into paragraphs, pairing with images and TTS,
    and assembling them into a video.

    This class primarily expects images to be pre-generated and available in the
    'images'
    subdirectory of the run_dir. It then generates text segments and TTS to match
    these images.
    """

    def __init__(self, run_dir: str):
        """Initialize the paragraph processor and its helper modules.

        Args:
            run_dir: Directory for the current run, used for inputs and outputs.
        """
        self.run_dir = Path(run_dir)
        self.mapping_path = self.run_dir / "paragraph_mapping.txt"
        self.images_dir = self.run_dir / "images"

        self.openai_client = get_openai_client()

        self.text_processor = TextProcessor(run_dir, self.openai_client)
        self.tts_generator = ParagraphTTS(run_dir)
        self.video_assembler = VideoAssembler(run_dir)

    def _get_existing_image_paths(self) -> list[str]:
        """Get and sort image paths (png, jpg, jpeg, webp) from the images directory."""
        if not self.images_dir.exists():
            logging.warning(f"Images directory not found: {self.images_dir}")
            return []

        exts = ["*.png", "*.jpg", "*.jpeg", "*.webp", "*.PNG", "*.JPG", "*.JPEG", "*.WEBP"]
        image_paths = []
        for ext in exts:
            image_paths.extend(self.images_dir.glob(ext))

        image_paths = sorted(set(str(p) for p in image_paths))
        logging.info(f"Found {len(image_paths)} existing images in {self.images_dir} (png, jpg, jpeg, webp)")
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
                        segment_rel_path = Path(created_segment_paths[i]).relative_to(
                            self.run_dir
                        )
                        f.write(f"Video Segment: {segment_rel_path}\n")
                    f.write("\n")
            logging.info(f"Successfully wrote mapping file to {self.mapping_path}")
        except Exception as e:
            logging.error(f"Error writing mapping file: {e}")

    def process(self, story_text: str) -> dict[str, Any]:
        """Processes story text by generating text segments, pairing with existing
        images, generating TTS, creating video segments, and concatenating them.

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
            return {"error": "No images found in images directory."}

        text_segments = self.text_processor.get_content_segments(
            story_text, summarize_long_paragraphs=True
        )
        logging.info(f"Processed story into {len(text_segments)} text segments.")

        if not text_segments:
            logging.error(
                "Text processing resulted in no segments. Cannot create TTS or video."
            )
            return {"error": "Text processing failed to produce segments."}

        num_images = len(image_paths)
        processed_paragraphs = list(text_segments)

        if len(processed_paragraphs) < num_images:
            logging.info(
                f"Number of text segments ({len(processed_paragraphs)}) is less than"
                f"images ({num_images}). Duplicating segments."
            )
            original_segment_count = len(processed_paragraphs)
            if original_segment_count == 0:
                logging.error(
                    "Cannot duplicate segments as there are no original segments"
                    "after processing"
                )
                return {
                    "error": "No text segments to align with images after"
                    "initial processing."
                }
            while len(processed_paragraphs) < num_images:
                processed_paragraphs.append(
                    processed_paragraphs[
                        len(processed_paragraphs) % original_segment_count
                    ]
                )
        elif len(processed_paragraphs) > num_images:
            logging.info(
                f"Number of text segments ({len(processed_paragraphs)}) is greater"
                f"than images ({num_images}). Truncating segments."
            )
            processed_paragraphs = processed_paragraphs[:num_images]

        num_final_segments = min(len(processed_paragraphs), num_images)
        final_text_segments = processed_paragraphs[:num_final_segments]
        final_image_paths = image_paths[:num_final_segments]

        audio_paths = self.tts_generator.generate_for_paragraphs(final_text_segments)
        if not audio_paths or len(audio_paths) != len(final_text_segments):
            logging.error(
                f"TTS generation failed or produced mismatched number of audio files."
                f"Expected {len(final_text_segments)}, got {len(audio_paths)}."
            )
            valid_audio_count = len(audio_paths)
            final_text_segments = final_text_segments[:valid_audio_count]
            final_image_paths = final_image_paths[:valid_audio_count]
            num_final_segments = valid_audio_count

            if num_final_segments == 0:
                return {"error": "TTS generation failed for all segments."}

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

        final_video_path = self.video_assembler.concatenate_segments(
            created_segment_video_paths, final_video_name="output_story_video.mp4"
        )

        if not final_video_path:
            logging.error("Failed to concatenate video segments into a final video.")

        self._write_mapping_file(
            story_text,
            final_text_segments,
            final_image_paths,
            audio_paths,
            created_segment_video_paths,
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
