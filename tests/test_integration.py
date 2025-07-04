import inspect
import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

import main
from youtube_shorts_gen.content.script_and_image_from_internet import (
    ScriptAndImageFromInternet,
)
from youtube_shorts_gen.media.paragraph_processor import ParagraphProcessor

# Add the parent directory to the path to import the module
sys.path.append(str(Path(__file__).parent.parent))


class TestIntegration(unittest.TestCase):
    """Integration tests for the complete YouTube Shorts generation pipeline."""

    def test_pipeline_structure(self):
        """Test the basic structure of the pipeline without executing actual code."""
        # Import main module for inspection

        # Verify that the main module has the expected functions
        self.assertTrue(
            hasattr(main, "run_pipeline_once"),
            "main module should have run_pipeline_once function",
        )
        self.assertTrue(
            hasattr(main, "setup_logging"),
            "main module should have setup_logging function",
        )

        # Verify the imports in the main module
        source = inspect.getsource(main)

        # Check for imports of key pipeline modules
        self.assertIn(
            "from youtube_shorts_gen.pipelines.ai_content_pipeline import "
            "run_ai_content_pipeline",
            source,
        )
        self.assertIn(
            "from youtube_shorts_gen.pipelines.internet_content_pipeline import (",
            source,
        )
        self.assertIn(
            "run_internet_content_pipeline,",
            source,
        )
        self.assertIn(
            "from youtube_shorts_gen.pipelines.upload_pipeline import "
            "run_upload_pipeline",
            source,
        )

        # Verify the pipeline structure by checking for key components in the
        # main module source (not just run_pipeline_once)
        main_source = inspect.getsource(main)

        # Check for references/imports of pipeline modules
        self.assertIn("run_ai_content_pipeline", main_source)
        self.assertIn(
            "run_internet_content_pipeline",
            main_source,
        )
        self.assertIn("run_upload_pipeline", main_source)

        # Check for key pipeline flow elements
        run_pipeline_source = inspect.getsource(main.run_pipeline_once)
        self.assertIn("content_result", run_pipeline_source)
        self.assertIn("_get_content_source_choice()", run_pipeline_source)

        # Check for helper function calls which handle the pipeline logic
        self.assertIn(
            "_process_pipeline_output(content_result, run_dir)", run_pipeline_source
        )

        # Check success handling in the process pipeline output function
        process_pipeline_source = inspect.getsource(main._process_pipeline_output)
        self.assertIn(
            "content_result.get(\"success\", False)", process_pipeline_source
        )
        self.assertIn(
            "upload_result.get(\"success\", False)", process_pipeline_source
        )
        self.assertIn("final_video_path", process_pipeline_source)

        # Verify the main loop structure
        main_source = inspect.getsource(main)
        self.assertIn('if __name__ == "__main__":', main_source)
        self.assertIn("while True:", main_source)
        self.assertIn("run_pipeline_once()", main_source)
        self.assertIn("time.sleep(SLEEP_SECONDS)", main_source)

    @patch("builtins.input", return_value="2")
    @patch.object(ScriptAndImageFromInternet, "run")
    @patch.object(ParagraphProcessor, "process")
    @patch("youtube_shorts_gen.upload.upload_to_youtube.YouTubeUploader.upload")
    @patch("youtube_shorts_gen.utils.openai_client.get_openai_client")
    def test_internet_content_pipeline(
        self, mock_get_client, mock_upload, mock_processor, mock_script, mock_input
    ):
        """Test the internet content pipeline (option 2)."""
        # Setup mocks
        mock_client = MagicMock()
        mock_get_client.return_value = mock_client
        
        mock_script.return_value = {
            "story": "Test story from internet",
            "sentences": ["Sentence 1", "Sentence 2"],
            "image_paths": ["image1.png", "image2.png"],
        }
        mock_processor.return_value = {
            "story": "Test story from internet",
            "processed_paragraphs": ["Paragraph 1", "Paragraph 2"],
            "image_paths": ["image1.png", "image2.png"],
            "segment_paths": ["segment_1.mp4", "segment_2.mp4"],
            "final_video": "output_story_video.mp4",
        }
        mock_upload.return_value = "https://youtube.com/watch?v=test"

        # Run the pipeline
        with (
            patch("pathlib.Path.exists", return_value=True),
            patch("shutil.copy") as mock_copy,
        ):
            from main import run_pipeline_once

            run_pipeline_once()

            # Assertions
            mock_input.assert_called_once()
            mock_script.assert_called_once()
            mock_processor.assert_called_once()
            mock_upload.assert_called_once()
            mock_copy.assert_called_once()


if __name__ == "__main__":
    unittest.main()
