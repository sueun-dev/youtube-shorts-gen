"""
Integration test for the video creation pipeline.

This module tests the integration between different components of the
video creation pipeline, focusing on the proper use of multiple images.
"""

import base64
import os
import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock, mock_open, patch

# Add the parent directory to the path to import the module
sys.path.append(str(Path(__file__).parent.parent))

# Import components to test
from youtube_shorts_gen.content.script_and_image_from_internet import (
    ScriptAndImageFromInternet,
)
from youtube_shorts_gen.media.paragraph_processor import ParagraphProcessor
from youtube_shorts_gen.media.text_processor import TextProcessor


class TestVideoCreationPipeline(unittest.TestCase):
    """Integration tests for the video creation pipeline."""

    def setUp(self):
        """Set up test fixtures before each test method."""
        # Create a temporary test directory
        self.test_run_dir = "test_runs/video_pipeline_test"
        os.makedirs(self.test_run_dir, exist_ok=True)

        # Create subdirectories
        Path(self.test_run_dir, "images").mkdir(exist_ok=True)
        Path(self.test_run_dir, "paragraph_audio").mkdir(exist_ok=True)
        Path(self.test_run_dir, "segments").mkdir(exist_ok=True)

        # Sample story
        self.test_story = (
            "The dragon snarled at the knight as she hid the princess behind her. "
            "Rearing her head back she let out a loud roar, 'FOR THE LAST TIME! "
            "I GOT FULL CUSTODY IN THE DIVORCE, THE KING GOT THE CASTLE AND THE GOLD!'"
        )

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

        # Create mapping file
        mapping_content = f"""Story: {self.test_story}

Sentence 1: The dragon snarled at the knight as she hid the princess behind her.
Image: {self.test_run_dir}/images/sentence_1.png

Sentence 2: Rearing her head back she let out a loud roar, 'FOR THE LAST TIME!'
Image: {self.test_run_dir}/images/sentence_2.png
"""
        with open(f"{self.test_run_dir}/sentence_image_mapping.txt", "w") as f:
            f.write(mapping_content)

    def tearDown(self):
        """Clean up test fixtures after each test method."""
        # In real tests you would clean up, but we'll leave it for safety
        pass

    @patch("youtube_shorts_gen.media.video_assembler.subprocess.run")
    @patch("youtube_shorts_gen.media.paragraph_processor.ParagraphTTS")
    @patch("openai.OpenAI")
    def test_pipeline_uses_all_images(self, mock_openai_class, mock_tts, mock_subprocess):
        """Test that the pipeline correctly uses all available images."""
        # Setup mocks
        mock_client = mock_openai_class.return_value
        
        mock_tts_instance = MagicMock()
        mock_tts.return_value = mock_tts_instance
        mock_tts_instance.generate_for_paragraphs.return_value = [
            f"{self.test_run_dir}/paragraph_audio/paragraph_1.mp3",
            f"{self.test_run_dir}/paragraph_audio/paragraph_2.mp3",
        ]

        # Create tracked segment creation calls
        segment_create_calls = []
        test_dir = self.test_run_dir  # Store reference to test_run_dir

        # Mock method to track calls with patching
        def mock_create_segment(*args, **kwargs):
            # Extract parameters from kwargs
            image_path = kwargs.get("image_path")
            audio_path = kwargs.get("audio_path")
            index = kwargs.get("index")
            segment_create_calls.append((image_path, audio_path, index))
            return f"{test_dir}/segments/segment_{index}.mp4"

        # Combine all mocks in a single with statement
        with (
            patch.object(
                ParagraphProcessor,
                "_get_existing_image_paths",
                return_value=[
                    f"{self.test_run_dir}/images/sentence_1.png",
                    f"{self.test_run_dir}/images/sentence_2.png",
                ],
            ),
            patch(
                "youtube_shorts_gen.media.video_assembler.VideoAssembler.create_segment_video",
                side_effect=mock_create_segment,
            ),
            patch(
                "youtube_shorts_gen.media.video_assembler.VideoAssembler.concatenate_segments",
                return_value=f"{self.test_run_dir}/final_story_video.mp4",
            ),
        ):
            # Create processor with mock client
            processor = ParagraphProcessor(self.test_run_dir, client=mock_client)

            # Mock text processor to return expected paragraphs
            with patch.object(
                processor.text_processor,
                "get_content_segments",
                return_value=[
                    "The dragon snarled at the knight as she hid the princess behind her.",
                    "Rearing her head back she let out a loud roar, 'FOR THE LAST TIME!'",
                ],
            ):
                # Run the process method
                result = processor.process(self.test_story)

                # Verify the result contains the right number of segments
                self.assertEqual(len(result["segment_paths"]), 2)

                # Verify the text segments were processed correctly
                self.assertEqual(len(result["processed_paragraphs"]), 2)
                self.assertTrue(
                    "dragon snarled" in result["processed_paragraphs"][0]
                )

                # Verify the segment creation calls used the correct images
                self.assertEqual(len(segment_create_calls), 2)
                self.assertEqual(
                    segment_create_calls[0][0], f"{self.test_run_dir}/images/sentence_1.png"
                )
                self.assertEqual(
                    segment_create_calls[1][0], f"{self.test_run_dir}/images/sentence_2.png"
                )

    @patch("youtube_shorts_gen.scrapers.dogdrip.fetch_dogdrip_content")
    @patch("youtube_shorts_gen.media.video_assembler.subprocess.run")
    @patch("youtube_shorts_gen.media.paragraph_processor.ParagraphTTS")
    @patch("openai.OpenAI")
    @patch("requests.get")
    def test_end_to_end_content_to_video_pipeline(
        self,
        mock_requests,
        mock_openai_class,
        mock_tts,
        mock_subprocess,
        mock_fetch_dogdrip_content,
    ):
        """Test the end-to-end pipeline from internet content to video creation."""
        # Mock requests for internet content
        main_page_response = MagicMock()
        main_page_response.text = (
            "<html><body><td class='title'>"
            "<a class='link-reset' data-document-srl='123' href='/doc/123'>"
            "<span class='ed title-link'>Sample Story</span></a></td></body></html>"
        )

        post_page_response = MagicMock()
        post_page_response.text = f"<html><body>{self.test_story}</body></html>"

        # Configure mock to return different responses for different URLs
        mock_requests.side_effect = [main_page_response, post_page_response]

        # Mock the fetch_dogdrip_content function to return our test story
        mock_fetch_dogdrip_content.return_value = [self.test_story]

        # Mock OpenAI responses for image generation
        mock_client = mock_openai_class.return_value

        mock_image_data = MagicMock()
        mock_image_data.b64_json = (
            "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmM"
            "IQAAAABJRU5ErkJggg=="
        )
        mock_image_response = MagicMock()
        mock_image_response.data = [mock_image_data]
        mock_client.images.generate.return_value = mock_image_response

        # Mock TTS generation
        mock_tts_instance = MagicMock()
        mock_tts.return_value = mock_tts_instance
        mock_tts_instance.generate_for_paragraphs.return_value = [
            f"{self.test_run_dir}/paragraph_audio/paragraph_1.mp3",
            f"{self.test_run_dir}/paragraph_audio/paragraph_2.mp3",
        ]

        # Mock ffmpeg subprocess calls
        mock_subprocess.return_value = MagicMock(returncode=0)

        # Integration test with mocked external dependencies
        # Combine all mocks in a single with statement
        with (
            patch("builtins.open", mock_open()),
            patch("pathlib.Path.write_text"),
            patch("pathlib.Path.exists", return_value=True),
            # Mock _get_existing_image_paths to return test image paths
            patch.object(
                ParagraphProcessor,
                "_get_existing_image_paths",
                return_value=[
                    f"{self.test_run_dir}/images/sentence_1.png",
                    f"{self.test_run_dir}/images/sentence_2.png",
                ],
            ),
            # Mock VideoAssembler methods
            patch(
                "youtube_shorts_gen.media.video_assembler.VideoAssembler.create_segment_video",
                return_value=f"{self.test_run_dir}/segments/segment_1.mp4",
            ),
            patch(
                "youtube_shorts_gen.media.video_assembler.VideoAssembler.concatenate_segments",
                return_value=f"{self.test_run_dir}/final_story_video.mp4",
            ),
        ):
            # First step: fetch script and images
            script_fetcher = ScriptAndImageFromInternet(self.test_run_dir, client=mock_client)
            script_result = script_fetcher.run()

            # Second step: process content into segments
            processor = ParagraphProcessor(self.test_run_dir, client=mock_client)
            # Ensure story_text is a string, not a list
            story_text = (
                script_result["story"]
                if isinstance(script_result["story"], str)
                else "\n".join(script_result["story"])
            )
            video_result = processor.process(story_text)

            # Assertions on the integration
            self.assertIn("story", script_result)
            self.assertIn("sentences", script_result)
            self.assertIn("image_paths", script_result)

            self.assertIn("image_paths", video_result)
            self.assertIn("segment_paths", video_result)
            self.assertIn("final_video", video_result)


if __name__ == "__main__":
    unittest.main()
