"""
Test suite for the script_and_image_from_internet module.

This module tests the ScriptAndImageFromInternet class which handles
fetching content from the internet and generating images for it.
"""

import os
import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

# Add the parent directory to the path to import the module
sys.path.append(str(Path(__file__).parent.parent))

# Import the module under test
from youtube_shorts_gen.content.script_and_image_from_internet import (
    ScriptAndImageFromInternet,
)


class TestScriptAndImageFromInternet(unittest.TestCase):
    """Test suite for the ScriptAndImageFromInternet class."""

    def setUp(self):
        """Set up test fixtures before each test method."""
        # Create a temporary test directory
        self.test_run_dir = "test_runs/internet_content_test"
        os.makedirs(self.test_run_dir, exist_ok=True)

        # Create images directory that would normally be created
        Path(self.test_run_dir, "images").mkdir(exist_ok=True)

        # Sample reddit API response
        self.sample_reddit_response = {
            "data": {
                "children": [
                    {
                        "data": {
                            "title": "The dragon's custody battle",
                            "selftext": "The dragon snarled at the knight as she hid the princess behind her. Rearing her head back she let out a loud roar, 'FOR THE LAST TIME! I GOT FULL CUSTODY IN THE DIVORCE, THE KING GOT THE CASTLE AND THE GOLD!'",
                        }
                    },
                    {
                        "data": {
                            "title": "Another story title",
                            "selftext": "This is another sample story text.",
                        }
                    },
                ]
            }
        }

        # Sample image data
        self.test_image_b64 = (
            "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmM"
            "IQAAAABJRU5ErkJggg=="
        )

    def tearDown(self):
        """Clean up test fixtures after each test method."""
        # In real tests you would delete files, but we'll leave that out for safety
        pass

    @patch("youtube_shorts_gen.content.script_and_image_from_internet.OpenAI")
    @patch("youtube_shorts_gen.content.script_and_image_from_internet.requests.get")
    def test_fetch_from_dogdrip(self, mock_requests_get, mock_openai):
        """Test that _fetch_from_dogdrip method correctly fetches and processes content."""
        # Mock the requests.get response
        mock_response = MagicMock()
        mock_response.text = "<html><body><td class='title'><a class='link-reset' data-document-srl='123' href='/doc/123'><span class='ed title-link'>Test Title</span></a></td><div class='document_123_0'>Test content</div></body></html>"
        mock_requests_get.return_value = mock_response

        # Create the ScriptAndImageFromInternet instance
        fetcher = ScriptAndImageFromInternet(self.test_run_dir)

        # Call the method
        result = fetcher._fetch_from_dogdrip("http://example.com/test.html")

        # Assertions
        self.assertEqual(len(result), 1)
        self.assertIn("Test Title", result[0])
        self.assertIn("Test content", result[0])

        # Verify the requests were made correctly
        # The method makes multiple calls - one for the main page and one for each post
        self.assertEqual(mock_requests_get.call_count, 2)
        # First call is to the main URL
        self.assertEqual(
            mock_requests_get.call_args_list[0][0][0], "http://example.com/test.html"
        )
        # Second call is to the post URL
        self.assertEqual(
            mock_requests_get.call_args_list[1][0][0], "http://example.com/doc/123"
        )

    @patch("youtube_shorts_gen.content.script_and_image_from_internet.OpenAI")
    def test_split_into_sentences(self, mock_openai):
        """Test that _split_into_sentences correctly splits text into sentences."""
        # Test story
        test_story = (
            "The dragon snarled. The knight stepped back. The princess was afraid."
        )

        # Create the ScriptAndImageFromInternet instance
        fetcher = ScriptAndImageFromInternet(self.test_run_dir)

        # Call the method
        result = fetcher._split_into_sentences(test_story)

        # Assertions
        self.assertEqual(len(result), 3)
        self.assertEqual(result[0], "The dragon snarled.")
        self.assertEqual(result[1], "The knight stepped back.")
        self.assertEqual(result[2], "The princess was afraid.")

    @patch("youtube_shorts_gen.content.script_and_image_from_internet.OpenAI")
    def test_split_into_sentences_handles_short_text(self, mock_openai):
        """Test that _split_into_sentences handles short text correctly."""
        # Short test text with no clear sentence breaks
        test_story = "Dragon and knight"

        # Create the ScriptAndImageFromInternet instance
        fetcher = ScriptAndImageFromInternet(self.test_run_dir)

        # Call the method
        result = fetcher._split_into_sentences(test_story)

        # Even though it's short, it should be returned as is if over 10 chars
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0], "Dragon and knight")

    @patch("youtube_shorts_gen.content.script_and_image_from_internet.OpenAI")
    def test_generate_image_for_sentence(self, mock_openai):
        """Test that _generate_image_for_sentence creates and saves an image."""
        # Mock the OpenAI client
        mock_client = MagicMock()
        mock_openai.return_value = mock_client

        # Mock the image generation response
        mock_image_data = MagicMock()
        mock_image_data.b64_json = self.test_image_b64
        mock_image_response = MagicMock()
        mock_image_response.data = [mock_image_data]
        mock_client.images.generate.return_value = mock_image_response

        # Create the ScriptAndImageFromInternet instance
        fetcher = ScriptAndImageFromInternet(self.test_run_dir)

        # Test sentence
        test_sentence = "The dragon snarled at the knight."

        # Use patch to avoid actually writing to the file system
        with patch("builtins.open", unittest.mock.mock_open()) as mock_file:
            # Call the method
            result = fetcher._generate_image_for_sentence(test_sentence, 1)

            # Assertions
            self.assertTrue(result.endswith("sentence_2.png"))

            # Verify image.generate was called with correct parameters
            mock_client.images.generate.assert_called_once()
            # Check that the sentence is in the prompt
            self.assertIn(
                test_sentence, mock_client.images.generate.call_args[1]["prompt"]
            )

            # Verify file was opened for writing
            mock_file.assert_called_once()

    @patch("youtube_shorts_gen.content.script_and_image_from_internet.OpenAI")
    @patch("youtube_shorts_gen.content.script_and_image_from_internet.requests.get")
    @patch("youtube_shorts_gen.content.script_and_image_from_internet.random.choice")
    def test_run_full_process(self, mock_random_choice, mock_requests_get, mock_openai):
        """Test the full run method that fetches content and generates images."""
        # Mock the requests.get response for both the main page and post page
        main_page_response = MagicMock()
        main_page_response.text = "<html><body><td class='title'><a class='link-reset' data-document-srl='123' href='/doc/123'><span class='ed title-link'>Test Title</span></a></td></body></html>"

        post_page_response = MagicMock()
        post_page_response.text = (
            "<html><body><div class='document_123_0'>Test content</div></body></html>"
        )

        # Configure mock to return different responses for different URLs
        mock_requests_get.side_effect = [main_page_response, post_page_response]

        # Mock random.choice to return the first story consistently
        mock_random_choice.return_value = "The dragon snarled at the knight as she hid the princess behind her. Rearing her head back she let out a loud roar, 'FOR THE LAST TIME! I GOT FULL CUSTODY IN THE DIVORCE, THE KING GOT THE CASTLE AND THE GOLD!'"

        # Mock the OpenAI client
        mock_client = MagicMock()
        mock_openai.return_value = mock_client

        # Mock the image generation response
        mock_image_data = MagicMock()
        mock_image_data.b64_json = self.test_image_b64
        mock_image_response = MagicMock()
        mock_image_response.data = [mock_image_data]
        mock_client.images.generate.return_value = mock_image_response

        # Create the ScriptAndImageFromInternet instance
        with patch("pathlib.Path.write_text") as mock_write_text:
            with patch("builtins.open", unittest.mock.mock_open()) as mock_file:
                fetcher = ScriptAndImageFromInternet(self.test_run_dir)

                # Call the run method
                result = fetcher.run()

                # Assertions
                self.assertIn("story", result)
                self.assertIn("sentences", result)
                self.assertIn("image_paths", result)

                # Verify the right number of images were generated
                self.assertEqual(len(result["image_paths"]), len(result["sentences"]))

                # Verify story was written to file
                mock_write_text.assert_called()

                # Verify mapping file was created
                mock_file_path = (
                    str(mock_file.call_args_list[-1][0][0])
                    if mock_file.call_args_list
                    else ""
                )
                self.assertIn("sentence_image_mapping.txt", mock_file_path)


if __name__ == "__main__":
    unittest.main()
