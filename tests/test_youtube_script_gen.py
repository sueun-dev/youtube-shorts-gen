import base64
import logging
import os
import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock, mock_open, patch

# Set up logging
log_format = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
logging.basicConfig(level=logging.INFO, format=log_format)

# Add the parent directory to the path to import the module
sys.path.append(str(Path(__file__).parent.parent))

# Import the module under test - must come after sys.path adjustment
from youtube_shorts_gen.youtube_script_gen import YouTubeScriptGenerator  # noqa: E402


class TestYoutubeScriptGen(unittest.TestCase):
    """Test suite for YouTube script generator functions."""

    def setUp(self):
        """Set up test fixtures before each test method."""
        # Create a temporary test directory path
        self.test_run_dir = "test_runs/temp_test_run"
        os.makedirs(self.test_run_dir, exist_ok=True)
        
        # Sample test data
        self.test_story = (
            "The moon glowed eerily over the abandoned carnival. "
            "Rusted rides creaked in the midnight breeze. "
            "A lone figure appeared, carrying an old music box."
        )
        # Simple base64 encoded 1x1 transparent PNG image
        self.test_image_b64 = (
            "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmM"
            "IQAAAABJRU5ErkJggg=="
        )
        
    def tearDown(self):
        """Clean up test fixtures after each test method."""
        # Clean up test directory if it exists
        if os.path.exists(self.test_run_dir):
            # In a real scenario, we would remove files, but just log it
            logging.info(f"Would remove test directory: {self.test_run_dir}")
    
    @patch('youtube_shorts_gen.youtube_script_gen.OpenAI')
    @patch('youtube_shorts_gen.youtube_script_gen.open', new_callable=mock_open)
    def test_generate_story_and_image(self, mock_file, mock_openai):
        """Test the generate_story_and_image function with mocked dependencies."""
        # Configure mocks
        mock_client = MagicMock()
        mock_openai.return_value = mock_client
        
        # Mock the chat completions response
        mock_chat_response = MagicMock()
        mock_chat_response.choices[0].message.content = self.test_story
        mock_client.chat.completions.create.return_value = mock_chat_response
        
        # Mock the image generation response
        mock_image_data = MagicMock()
        mock_image_data.b64_json = self.test_image_b64
        mock_image_response = MagicMock()
        mock_image_response.data = [mock_image_data]
        mock_client.images.generate.return_value = mock_image_response
        
        # Call the function
        script_generator = YouTubeScriptGenerator(self.test_run_dir)
        script_generator.run()
        
        # Assertions
        mock_client.chat.completions.create.assert_called_once()
        mock_client.images.generate.assert_called_once()
        
        # Check that the files were written correctly
        story_path = os.path.join(self.test_run_dir, "story_prompt.txt")
        image_path = os.path.join(self.test_run_dir, "story_image.png")
        mock_file.assert_any_call(story_path, "w", encoding="utf-8")
        mock_file.assert_any_call(image_path, "wb")
        
        # Check content that was written
        file_handle = mock_file()
        file_handle.write.assert_any_call(self.test_story)
        file_handle.write.assert_any_call(base64.b64decode(self.test_image_b64))
    
    @patch('youtube_shorts_gen.youtube_script_gen.OpenAI')
    def test_error_handling(self, mock_openai):
        """Test error handling in the generate_story_and_image function."""
        # Configure mock to raise a specific exception
        mock_client = MagicMock()
        mock_openai.return_value = mock_client
        # Using a more specific exception type for API issues
        error_msg = "API Connection Error"
        mock_client.chat.completions.create.side_effect = ConnectionError(error_msg)
        
        # Test that the function handles the exception with a specific exception type
        with self.assertRaises(ConnectionError):
            script_generator = YouTubeScriptGenerator(self.test_run_dir)
            script_generator.run()
            

if __name__ == '__main__':
    unittest.main()
