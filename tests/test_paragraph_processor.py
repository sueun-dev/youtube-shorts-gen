"""
Test suite for the paragraph processor module.

This module tests the ParagraphProcessor class which orchestrates text processing,
TTS generation, and video assembly.
"""

import base64
import os
import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

# Add the parent directory to the path to import the module
sys.path.append(str(Path(__file__).parent.parent))

# Import the module under test
from youtube_shorts_gen.media.paragraph_processor import ParagraphProcessor


class TestParagraphProcessor(unittest.TestCase):
    """Test suite for the ParagraphProcessor class."""

    def setUp(self):
        """Set up test fixtures before each test method."""
        # Create a temporary test directory
        self.test_run_dir = "test_runs/paragraph_processor_test"
        os.makedirs(self.test_run_dir, exist_ok=True)

        # Test data
        self.test_story = (
            "The dragon snarled at the knight as she hid the princess behind her. "
            "Rearing her head back she let out a loud roar, 'FOR THE LAST TIME! "
            "I GOT FULL CUSTODY IN THE DIVORCE, THE KING GOT THE CASTLE AND THE GOLD!'"
        )

        # Create test directories that would normally be created
        Path(self.test_run_dir, "images").mkdir(exist_ok=True)
        Path(self.test_run_dir, "paragraph_audio").mkdir(exist_ok=True)
        Path(self.test_run_dir, "segments").mkdir(exist_ok=True)

        # Create sample test image files
        for i in range(1, 3):
            with open(f"{self.test_run_dir}/images/sentence_{i}.png", "wb") as f:
                # Write a minimal PNG file (1x1 transparent pixel)
                f.write(
                    base64.b64decode(
                        "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmM"
                        "IQAAAABJRU5ErkJggg=="
                    )
                )

        # Test mapping file content
        self.test_mapping_content = f"""Story: {self.test_story}

Sentence 1: The dragon snarled at the knight as she hid the princess behind her.
Image: {self.test_run_dir}/images/sentence_1.png

Sentence 2: Rearing her head back she let out a loud roar, 'FOR THE LAST TIME! 
I GOT FULL CUSTODY IN THE DIVORCE!'
Image: {self.test_run_dir}/images/sentence_2.png
"""

    def tearDown(self):
        """Clean up test fixtures after each test method."""
        # In real tests you would delete files, but we'll leave that out for safety
        pass

    @patch("youtube_shorts_gen.media.paragraph_processor.get_openai_client")
    @patch("youtube_shorts_gen.media.paragraph_processor.ParagraphTTS")
    @patch(
        "youtube_shorts_gen.media.text_processor.TextProcessor._extract_sentences_from_mapping_file"
    )
    def test_summarize_paragraphs_with_mapping_file(
        self, mock_extract_sentences, mock_tts, mock_get_client
    ):
        """Test that the TextProcessor correctly processes text segments from
        mapping file."""

        # Mock the OpenAI client
        mock_client = MagicMock()
        mock_get_client.return_value = mock_client

        # Setup mock to return sentences from mapping file
        expected_sentences = [
            "The dragon snarled at the knight as she hid the princess behind her.",
            "Rearing her head back she let out a loud roar, 'FOR THE LAST TIME! "
            "I GOT FULL CUSTODY IN THE DIVORCE!'",
        ]
        mock_extract_sentences.return_value = expected_sentences

        # Mock the TTS generator to return audio paths
        mock_tts_instance = MagicMock()
        mock_tts.return_value = mock_tts_instance
        mock_tts_instance.generate_for_paragraphs.return_value = [
            f"{self.test_run_dir}/paragraph_audio/paragraph_1.mp3",
            f"{self.test_run_dir}/paragraph_audio/paragraph_2.mp3",
        ]

        # Create processor and test
        processor = ParagraphProcessor(self.test_run_dir)

        # Mock _get_existing_image_paths to return test image paths
        with (
            patch.object(
                processor,
                "_get_existing_image_paths",
                return_value=[
                    f"{self.test_run_dir}/images/sentence_1.png",
                    f"{self.test_run_dir}/images/sentence_2.png",
                ],
            ),
            patch.object(
                processor.text_processor,
                "get_content_segments",
                return_value=expected_sentences,
            ) as mock_get_segments,
            patch.object(
                processor.video_assembler,
                "create_segment_video",
                side_effect=[
                    f"{self.test_run_dir}/segments/segment_0.mp4",
                    f"{self.test_run_dir}/segments/segment_1.mp4",
                ],
            ),
            patch.object(
                processor.video_assembler,
                "concatenate_segments",
                return_value=f"{self.test_run_dir}/output_story_video.mp4",
            ),
        ):
            # Call process method which will use text_processor
            result = processor.process(self.test_story)

            # Verify the text processor was called with the story text
            mock_get_segments.assert_called_once_with(
                self.test_story, summarize_long_paragraphs=True
            )

            # Verify we got the expected paragraphs in the result
            self.assertEqual(len(result["processed_paragraphs"]), 2)
            self.assertTrue("dragon snarled" in result["processed_paragraphs"][0])

    @patch("youtube_shorts_gen.media.paragraph_processor.get_openai_client")
    @patch("youtube_shorts_gen.media.paragraph_processor.ParagraphTTS")
    @patch(
        "youtube_shorts_gen.media.text_processor.TextProcessor._extract_sentences_from_mapping_file"
    )
    def test_summarize_paragraphs_without_mapping_file(
        self, mock_extract_sentences, mock_tts, mock_get_client
    ):
        """Test that TextProcessor correctly splits text when no mapping file exists."""
        # Mock the OpenAI client
        mock_client = MagicMock()
        mock_get_client.return_value = mock_client

        # Setup mock to return empty list (no mapping file)
        mock_extract_sentences.return_value = []

        # Expected paragraphs after text processing
        expected_paragraphs = [
            "The dragon snarled at the knight as she hid the princess behind her.",
            "Rearing her head back she let out a loud roar, 'FOR THE LAST TIME! "
            "I GOT FULL "
            "CUSTODY!'",
        ]

        # Mock the TTS generator to return audio paths
        mock_tts_instance = MagicMock()
        mock_tts.return_value = mock_tts_instance
        mock_tts_instance.generate_for_paragraphs.return_value = [
            f"{self.test_run_dir}/paragraph_audio/paragraph_1.mp3",
            f"{self.test_run_dir}/paragraph_audio/paragraph_2.mp3",
        ]

        # Create processor and test
        processor = ParagraphProcessor(self.test_run_dir)

        # Mock _get_existing_image_paths to return test image paths
        with (
            patch.object(
                processor,
                "_get_existing_image_paths",
                return_value=[
                    f"{self.test_run_dir}/images/sentence_1.png",
                    f"{self.test_run_dir}/images/sentence_2.png",
                ],
            ),
            patch.object(
                processor.text_processor,
                "get_content_segments",
                return_value=expected_paragraphs,
            ) as mock_get_segments,
            patch.object(
                processor.video_assembler,
                "create_segment_video",
                side_effect=[
                    f"{self.test_run_dir}/segments/segment_0.mp4",
                    f"{self.test_run_dir}/segments/segment_1.mp4",
                ],
            ),
            patch.object(
                processor.video_assembler,
                "concatenate_segments",
                return_value=f"{self.test_run_dir}/output_story_video.mp4",
            ),
        ):
            # Call process method which will use text_processor
            result = processor.process(self.test_story)

            # Verify the text processor was called with the story text
            mock_get_segments.assert_called_once_with(
                self.test_story, summarize_long_paragraphs=True
            )

            # Verify we got the expected paragraphs in the result
            self.assertEqual(len(result["processed_paragraphs"]), 2)
            self.assertTrue("dragon snarled" in result["processed_paragraphs"][0])
            self.assertTrue("FOR THE LAST TIME" in result["processed_paragraphs"][1])

    @patch("youtube_shorts_gen.media.paragraph_processor.get_openai_client")
    @patch("youtube_shorts_gen.media.paragraph_processor.ParagraphTTS")
    @patch("youtube_shorts_gen.media.video_assembler.subprocess.run")
    def test_process_uses_all_images(self, mock_subprocess, mock_tts, mock_get_client):
        """Test that the process method uses all available images."""
        # Mock the OpenAI client
        mock_client = MagicMock()
        mock_get_client.return_value = mock_client

        # Mock the TTS generator
        mock_tts_instance = MagicMock()
        mock_tts.return_value = mock_tts_instance
        mock_tts_instance.generate_for_paragraphs.return_value = [
            f"{self.test_run_dir}/paragraph_audio/paragraph_1.mp3",
            f"{self.test_run_dir}/paragraph_audio/paragraph_2.mp3",
        ]

        # Expected paragraphs after text processing
        expected_paragraphs = [
            "The dragon snarled at the knight as she hid the princess behind her.",
            "Rearing her head back she let out a loud roar.",
        ]

        # Mock file operations to find existing images
        with patch.object(
            ParagraphProcessor, "_get_existing_image_paths"
        ) as mock_get_images:
            # Set up the mock to return test image paths
            mock_get_images.return_value = [
                f"{self.test_run_dir}/images/sentence_1.png",
                f"{self.test_run_dir}/images/sentence_2.png",
            ]

            # Mock subprocess calls to ffmpeg
            mock_subprocess.return_value = MagicMock(returncode=0, stdout="1.5")

            # Create processor
            processor = ParagraphProcessor(self.test_run_dir)

            # Mock text processor to return expected paragraphs
            with (
                patch.object(
                    processor.text_processor,
                    "get_content_segments",
                    return_value=expected_paragraphs,
                ),
                patch.object(
                    processor.text_processor,
                    "get_content_segments",
                    return_value=expected_paragraphs,
                ),
                patch.object(
                    processor.video_assembler, "create_segment_video"
                ) as mock_create_segment,
            ):
                mock_create_segment.side_effect = [
                    f"{self.test_run_dir}/segments/segment_0.mp4",
                    f"{self.test_run_dir}/segments/segment_1.mp4",
                ]

                # Mock concatenate_segments to return final video path
                with patch.object(
                    processor.video_assembler,
                    "concatenate_segments",
                    return_value=f"{self.test_run_dir}/output_story_video.mp4",
                ):
                    # Run the process method
                    result = processor.process(self.test_story)

                    # Check that create_segment_video was called for each image
                    self.assertEqual(mock_create_segment.call_count, 2)

                    # Verify the result contains the right number of segments
                    self.assertEqual(len(result["segment_paths"]), 2)

                    # Verify the text segments were processed correctly
                    self.assertEqual(len(result["processed_paragraphs"]), 2)
                    self.assertTrue(
                        "dragon snarled" in result["processed_paragraphs"][0]
                    )

    @patch("youtube_shorts_gen.media.paragraph_processor.get_openai_client")
    @patch("youtube_shorts_gen.media.paragraph_processor.ParagraphTTS")
    @patch("youtube_shorts_gen.media.video_assembler.subprocess.run")
    def test_process_handles_mismatched_paragraph_image_counts(
        self, mock_subprocess, mock_tts, mock_get_client
    ):
        """Test that the process method handles when paragraph and image counts
        don't match."""

        # Mock the OpenAI client
        mock_client = MagicMock()
        mock_get_client.return_value = mock_client

        # Expected paragraphs after text processing (more than images)
        expected_paragraphs = [
            "The dragon snarled at the knight as she hid the princess behind her.",
            "Rearing her head back she let out a loud roar.",
            "'FOR THE LAST TIME! I GOT FULL CUSTODY!'",
        ]

        # Mock the TTS generator - return audio files matching paragraphs
        mock_tts_instance = MagicMock()
        mock_tts.return_value = mock_tts_instance
        mock_tts_instance.generate_for_paragraphs.return_value = [
            f"{self.test_run_dir}/paragraph_audio/paragraph_1.mp3",
            f"{self.test_run_dir}/paragraph_audio/paragraph_2.mp3",
        ]

        # Mock file operations to find existing images
        with patch.object(
            ParagraphProcessor, "_get_existing_image_paths"
        ) as mock_get_images:
            # Set up the mock to return fewer images than paragraphs
            mock_get_images.return_value = [
                f"{self.test_run_dir}/images/sentence_1.png",
                f"{self.test_run_dir}/images/sentence_2.png",
            ]

            # Mock subprocess calls to ffmpeg
            mock_subprocess.return_value = MagicMock(returncode=0)

            # Create processor
            processor = ParagraphProcessor(self.test_run_dir)

            # Mock text processor to return expected paragraphs (more than images)
            with (
                patch.object(
                    processor.text_processor,
                    "get_content_segments",
                    return_value=expected_paragraphs,
                ),
                patch.object(
                    processor.video_assembler, "create_segment_video"
                ) as mock_create_segment,
            ):
                mock_create_segment.side_effect = [
                    f"{self.test_run_dir}/segments/segment_0.mp4",
                    f"{self.test_run_dir}/segments/segment_1.mp4",
                ]

                # Mock concatenate_segments to return final video path
                with patch.object(
                    processor.video_assembler,
                    "concatenate_segments",
                    return_value=f"{self.test_run_dir}/output_story_video.mp4",
                ):
                    # Run the process method
                    result = processor.process(self.test_story)

                    # We should only create as many segments as we have images
                    self.assertEqual(mock_create_segment.call_count, 2)

                    # Verify the result contains the right number of segments
                    # (limited by image count)
                    self.assertEqual(len(result["segment_paths"]), 2)

                    # Verify we only used as many paragraphs as we had images
                    self.assertEqual(len(result["processed_paragraphs"]), 2)


if __name__ == "__main__":
    unittest.main()
