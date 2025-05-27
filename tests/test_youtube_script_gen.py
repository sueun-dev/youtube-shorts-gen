import logging
import os
import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

# Set up logging
log_format = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
logging.basicConfig(level=logging.INFO, format=log_format)

# Add the parent directory to the path to import the module
sys.path.append(str(Path(__file__).parent.parent))

from youtube_shorts_gen.content.script_and_image_gen import (  # noqa: E402
    ScriptAndImageGenerator,
)


@patch("youtube_shorts_gen.content.script_and_image_gen.get_openai_client")
class TestScriptAndImageGen(unittest.TestCase):
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

    def test_generate_story_and_image(self, mock_get_client):
        """Test the generate_story_and_image function with mocked dependencies."""
        # Configure mocks
        mock_client = MagicMock()
        mock_get_client.return_value = mock_client

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
        script_generator = ScriptAndImageGenerator(self.test_run_dir)
        script_generator.run()

        # Assertions
        mock_client.chat.completions.create.assert_called_once()
        mock_client.images.generate.assert_called_once()

        # The current implementation uses Path.write_text and Path.write_bytes directly
        # instead of using open(), so we don't need to check file operations

    def test_error_handling(self, mock_get_client):
        """Test error handling in the generate_story_and_image function."""
        # Configure mock to raise a specific exception
        mock_client = MagicMock()
        mock_get_client.return_value = mock_client
        # Using a more specific exception type for API issues
        error_msg = "API Connection Error"
        mock_client.chat.completions.create.side_effect = ConnectionError(error_msg)

        # Test that the function handles the exception with a specific exception type
        with self.assertRaises(ConnectionError):
            script_generator = ScriptAndImageGenerator(self.test_run_dir)
            script_generator.run()


if __name__ == "__main__":
    unittest.main()
