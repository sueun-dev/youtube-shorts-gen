import logging
import os
import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

# Set up logging
log_format = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
logging.basicConfig(level=logging.INFO, format=log_format)

# Add the parent directory to the path to import the module
sys.path.append(str(Path(__file__).parent.parent))


class TestIntegration(unittest.TestCase):
    """Integration tests for the complete YouTube Shorts generation pipeline."""

    def setUp(self):
        """Set up test environment before each test."""
        # Create a temporary test directory
        self.test_dir = "test_runs/integration_test"
        os.makedirs(self.test_dir, exist_ok=True)
        
    def tearDown(self):
        """Clean up after each test."""
        # In a real scenario we would delete test files, but for safety we just log
        logging.info(f"Would remove test directory: {self.test_dir}")
    
    @patch('os.makedirs')
    @patch('os.path.join')
    def test_pipeline_structure(self, mock_join, mock_makedirs):
        """Test the basic structure and flow without executing actual code."""
        # Setup mocks
        mock_join.return_value = "runs/2025-05-02_15-13-43"
        
        # Create the main module mockup
        with patch.dict('sys.modules', {
            'youtube_shorts_gen.youtube_script_gen': MagicMock(),
            'youtube_shorts_gen.runway': MagicMock(),
            'youtube_shorts_gen.sync_video_with_tts': MagicMock(),
            'youtube_shorts_gen.upload_to_youtube': MagicMock(),
            'runwayml': MagicMock()
        }):
            # Now mock the specific functions
            # Use variable names to separate long import paths
            base_path = 'youtube_shorts_gen'
            script_gen_path = f'{base_path}.youtube_script_gen.generate_story_and_image'
            runway_path = f'{base_path}.runway.generate_video'
            sync_path = f'{base_path}.sync_video_with_tts.sync_video_with_tts'
            upload_path = f'{base_path}.upload_to_youtube.upload_video'
            
            # Using patch decorators to avoid excessive nesting
            with patch(script_gen_path) as mock_gen_story, \
                 patch(runway_path) as mock_gen_video, \
                 patch(sync_path) as mock_sync, \
                 patch(upload_path) as mock_upload:
                            
                            # Import the function only after all mocks are in place
                            from youtube_shorts_gen.main import run_pipeline_once
                            
                            # Run the pipeline
                            run_pipeline_once()
            
                            # Verify directory was created
                            mock_makedirs.assert_called()
                            
                            # Verify the pipeline components in order
                            mock_gen_story.assert_called()
                            mock_gen_video.assert_called()
                            mock_sync.assert_called()
                            mock_upload.assert_called()


if __name__ == '__main__':
    unittest.main()
