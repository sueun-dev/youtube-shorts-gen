"""Tests for the paragraph TTS syncer module."""

import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from youtube_shorts_gen.media.paragraph_tts_syncer import ParagraphTTSSyncer


class TestParagraphTTSSyncer(unittest.TestCase):
    """Test cases for the ParagraphTTSSyncer class."""

    def setUp(self):
        """Set up test environment."""
        self.temp_dir = tempfile.TemporaryDirectory()
        self.run_dir = self.temp_dir.name

        # Create necessary directories
        Path(self.run_dir, "audio").mkdir(exist_ok=True)
        Path(self.run_dir, "paragraph_videos").mkdir(exist_ok=True)
        Path(self.run_dir, "images").mkdir(exist_ok=True)

        # Create a test mapping file
        self._create_test_mapping_file()

        # Create test image files
        self._create_test_images()

        # Create the syncer instance
        self.syncer = ParagraphTTSSyncer(self.run_dir)

    def tearDown(self):
        """Clean up after tests."""
        self.temp_dir.cleanup()

    def _create_test_mapping_file(self):
        """Create a test paragraph-image mapping file."""
        mapping_content = (
            "Story: This is a test story with multiple paragraphs.\n\n"
            "Paragraph 1: This is the first paragraph of the test story.\n"
            f"Image: {os.path.join(self.run_dir, 'images', 'paragraph_1.png')}\n\n"
            "Paragraph 2: This is the second paragraph of the test story.\n"
            f"Image: {os.path.join(self.run_dir, 'images', 'paragraph_2.png')}\n\n"
        )

        mapping_path = Path(self.run_dir, "paragraph_image_mapping.txt")
        mapping_path.write_text(mapping_content)

    def _create_test_images(self):
        """Create test image files."""
        # Create simple test images (1x1 pixel)
        for i in range(1, 3):
            image_path = Path(self.run_dir, "images", f"paragraph_{i}.png")
            with open(image_path, "wb") as f:
                # Simple 1x1 PNG
                f.write(
                    b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15\xc4\x89\x00\x00\x00\nIDATx\x9cc\x00\x01\x00\x00\x05\x00\x01\r\n-\xb4\x00\x00\x00\x00IEND\xaeB`\x82"
                )

    @patch("youtube_shorts_gen.media.paragraph_tts_syncer.gTTS")
    def test_generate_tts_for_paragraph(self, mock_gtts):
        """Test generating TTS for a paragraph."""
        # Mock gTTS
        mock_tts = MagicMock()
        mock_gtts.return_value = mock_tts

        # Call the method
        result = self.syncer._generate_tts_for_paragraph("Test paragraph", 0)

        # Assertions
        expected_path = os.path.join(self.run_dir, "audio", "paragraph_1.mp3")
        self.assertEqual(result, expected_path)

        # Verify gTTS was called with the correct parameters
        mock_gtts.assert_called_once_with("Test paragraph", lang="ko")
        mock_tts.save.assert_called_once_with(expected_path)

    @patch("subprocess.run")
    def test_get_duration(self, mock_run):
        """Test getting the duration of a media file."""
        # Mock subprocess.run
        mock_process = MagicMock()
        mock_process.stdout = "10.5\n"
        mock_run.return_value = mock_process

        # Call the method
        result = self.syncer._get_duration(Path("test.mp3"))

        # Assertions
        self.assertEqual(result, 10.5)

        # Verify subprocess.run was called with the correct parameters
        mock_run.assert_called_once()
        args, kwargs = mock_run.call_args
        self.assertEqual(args[0][0], "ffprobe")
        self.assertIn("capture_output", kwargs)
        self.assertIn("text", kwargs)
        self.assertIn("check", kwargs)

    @patch("subprocess.run")
    def test_create_image_video(self, mock_run):
        """Test creating a video from an image."""
        # Mock subprocess.run
        mock_run.return_value = MagicMock()

        # Call the method
        output_path = Path(self.run_dir, "test_video.mp4")
        self.syncer._create_image_video("test.png", 5.0, output_path)

        # Verify subprocess.run was called with the correct parameters
        mock_run.assert_called_once()
        args, kwargs = mock_run.call_args
        self.assertEqual(args[0][0], "ffmpeg")
        self.assertEqual(args[0][1], "-y")
        self.assertEqual(args[0][3], "1")
        self.assertEqual(args[0][5], "test.png")
        self.assertIn("check", kwargs)

    @patch("subprocess.run")
    def test_merge_audio_and_video(self, mock_run):
        """Test merging audio and video."""
        # Mock subprocess.run
        mock_run.return_value = MagicMock()

        # Call the method
        video_path = Path(self.run_dir, "test_video.mp4")
        audio_path = "test_audio.mp3"
        output_path = Path(self.run_dir, "test_output.mp4")
        self.syncer._merge_audio_and_video(video_path, audio_path, output_path)

        # Verify subprocess.run was called with the correct parameters
        mock_run.assert_called_once()
        args, kwargs = mock_run.call_args
        self.assertEqual(args[0][0], "ffmpeg")
        self.assertEqual(args[0][1], "-y")
        self.assertEqual(args[0][3], str(video_path))
        self.assertEqual(args[0][5], audio_path)
        self.assertIn("check", kwargs)

    @patch("subprocess.run")
    def test_combine_paragraph_videos(self, mock_run):
        """Test combining paragraph videos."""
        # Mock subprocess.run
        mock_run.return_value = MagicMock()

        # Call the method
        video_paths = [
            os.path.join(self.run_dir, "paragraph_videos", "paragraph_1.mp4"),
            os.path.join(self.run_dir, "paragraph_videos", "paragraph_2.mp4"),
        ]
        self.syncer._combine_paragraph_videos(video_paths)

        # Verify a list file was created
        list_file_path = os.path.join(self.run_dir, "video_list.txt")
        self.assertTrue(os.path.exists(list_file_path))

        # Verify subprocess.run was called with the correct parameters
        mock_run.assert_called_once()
        args, kwargs = mock_run.call_args
        self.assertEqual(args[0][0], "ffmpeg")
        self.assertEqual(args[0][1], "-y")
        self.assertEqual(args[0][3], "concat")
        self.assertIn("check", kwargs)

    def test_parse_mapping_file(self):
        """Test parsing the paragraph-image mapping file."""
        # Call the method
        result = self.syncer._parse_mapping_file()

        # Assertions
        self.assertEqual(len(result), 2)
        self.assertEqual(
            result[0]["text"], "This is the first paragraph of the test story."
        )
        self.assertEqual(
            result[1]["text"], "This is the second paragraph of the test story."
        )
        self.assertTrue(result[0]["image"].endswith("paragraph_1.png"))
        self.assertTrue(result[1]["image"].endswith("paragraph_2.png"))

    @patch.object(ParagraphTTSSyncer, "_generate_tts_for_paragraph")
    @patch.object(ParagraphTTSSyncer, "_get_duration")
    @patch.object(ParagraphTTSSyncer, "_create_image_video")
    @patch.object(ParagraphTTSSyncer, "_merge_audio_and_video")
    @patch.object(ParagraphTTSSyncer, "_combine_paragraph_videos")
    def test_sync(
        self, mock_combine, mock_merge, mock_create, mock_duration, mock_generate_tts
    ):
        """Test the full sync method of the ParagraphTTSSyncer."""
        # Mock responses
        mock_generate_tts.side_effect = [
            os.path.join(self.run_dir, "audio", "paragraph_1.mp3"),
            os.path.join(self.run_dir, "audio", "paragraph_2.mp3"),
        ]
        mock_duration.return_value = 5.0

        # Call the method
        result = self.syncer.sync()

        # Assertions
        expected_path = os.path.join(self.run_dir, "final_story_video.mp4")
        self.assertEqual(result, expected_path)

        # Verify the methods were called the correct number of times
        self.assertEqual(mock_generate_tts.call_count, 2)
        self.assertEqual(mock_duration.call_count, 2)
        self.assertEqual(mock_create.call_count, 2)
        self.assertEqual(mock_merge.call_count, 2)
        self.assertEqual(mock_combine.call_count, 1)


if __name__ == "__main__":
    unittest.main()
