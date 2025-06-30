"""
Test suite for the script_and_image_from_internet module.

This module tests the ScriptAndImageFromInternet class which handles
fetching content from the internet and generating images for it.
"""

import os
import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock, mock_open, patch

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
                            "selftext": (
                                "The dragon snarled at the knight as "
                                "behind her. Rearing her head back"
                                "'FOR THE LAST TIME!"
                                "THE KING GOT THE CASTLE "
                                "AND THE GOLD!"
                            ),
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

    @patch("youtube_shorts_gen.scrapers.dogdrip_scraper.requests.get")
    def test_dogdrip_scraper(self, mock_requests_get):
        """Test that DogdripScraper correctly fetches and processes content."""
        # Import needed here to avoid circular imports
        from youtube_shorts_gen.scrapers.dogdrip_scraper import DogdripScraper

        # Mock the requests.get response
        mock_response = MagicMock()
        mock_response.text = (
            "<html><body><td class='title'><a class='link-reset' "
            "data-document-srl='123' href='/doc/123'>"
            "<span class='ed title-link'>Test Title</span></a></td>"
            "<div class='document_123_0'>Test content</div></body></html>"
        )
        mock_requests_get.return_value = mock_response

        # Create DogdripScraper instance directly with custom URL
        scraper = DogdripScraper(url="http://example.com/test.html")

        # Call the fetch_content method
        result = scraper.fetch_content()

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
        # Second call should contain the doc/123 path
        self.assertIn("doc/123", mock_requests_get.call_args_list[1][0][0])

    @patch("openai.OpenAI")
    def test_split_into_sentences(self, mock_openai_class):
        """Test that split_into_sentences correctly splits text into sentences."""
        # Test story
        test_story = (
            "The dragon snarled. The knight stepped back. The princess was afraid."
        )

        # Create mock OpenAI client
        mock_client = mock_openai_class.return_value

        # Create the ScriptAndImageFromInternet instance
        fetcher = ScriptAndImageFromInternet(self.test_run_dir, client=mock_client)

        # Call the method
        result = fetcher.split_into_sentences(test_story)

        # Assertions
        self.assertEqual(len(result), 3)
        self.assertEqual(result[0], "The dragon snarled.")
        self.assertEqual(result[1], "The knight stepped back.")
        self.assertEqual(result[2], "The princess was afraid.")

    @patch("openai.OpenAI")
    def test_split_into_sentences_handles_short_text(self, mock_openai_class):
        """Test that split_into_sentences handles short text correctly."""
        # Short test text with no clear sentence breaks
        test_story = "Dragon and knight"

        # Create mock OpenAI client
        mock_client = mock_openai_class.return_value

        # Create the ScriptAndImageFromInternet instance
        fetcher = ScriptAndImageFromInternet(self.test_run_dir, client=mock_client)

        # Call the method
        result = fetcher.split_into_sentences(test_story)

        # Even though it's short, it should be returned as is if over 10 chars
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0], "Dragon and knight")

    @patch("openai.OpenAI")
    @patch("youtube_shorts_gen.content.script_and_image_from_internet.generate_openai_image")
    def test_generate_image_for_sentence(self, mock_generate_image, mock_openai_class):
        """Test that _generate_image_for_sentence creates and saves an image."""
        # Create mock OpenAI client
        mock_client = mock_openai_class.return_value
        
        # Set up the mock for generate_image with a side_effect function
        expected_image_path = str(Path(self.test_run_dir, "images") / "sentence_2.png")
        
        def mock_generate_side_effect(client, prompt, output_path):
            # Return the expected path regardless of inputs
            return expected_image_path
            
        mock_generate_image.side_effect = mock_generate_side_effect

        # Create the ScriptAndImageFromInternet instance
        fetcher = ScriptAndImageFromInternet(self.test_run_dir, client=mock_client)

        # Test sentence
        test_sentence = "The dragon snarled at the knight."

        # Call the method
        result = fetcher._generate_image_for_sentence(test_sentence, 1)

        # Assertions
        self.assertEqual(result, expected_image_path)
        
        # Verify generate_image was called with the correct client and a path
        mock_generate_image.assert_called_once()
        args, _ = mock_generate_image.call_args
        self.assertEqual(args[0], mock_client)  # First arg should be client
        self.assertTrue(isinstance(args[2], Path))  # Third arg should be a Path

    @patch("youtube_shorts_gen.content.script_and_image_from_internet.random.choice")
    @patch("requests.get")
    @patch("openai.OpenAI")
    def test_run_full_process(
        self, mock_openai_class, mock_requests_get, mock_random_choice
    ):
        """Test the full run method that fetches content and generates images."""
        # Mock the requests.get response for both the main page and post page
        main_page_response = MagicMock()
        main_page_response.text = (
            "<html><body><td class='title'><a class='link-reset' "
            "data-document-srl='123' href='/doc/123'>"
            "<span class='ed title-link'>Test Title</span></a></td></body></html>"
        )

        post_page_response = MagicMock()
        post_page_response.text = (
            "<html><body><div class='document_123_0'>Test content</div></body></html>"
        )

        # Configure mock to return different responses for different URLs
        mock_requests_get.side_effect = [main_page_response, post_page_response]

        # Mock random.choice to return the first story consistently
        mock_random_choice.return_value = (
            "The dragon snarled at the knight as she hid the princess behind her. "
            "Rearing her head back she let out a loud roar, 'FOR THE LAST TIME! "
            "I GOT FULL CUSTODY IN THE DIVORCE, THE KING GOT THE CASTLE AND THE GOLD!'"
        )

        # Create mock OpenAI client
        mock_client = mock_openai_class.return_value
        
        # Mock the image generation response
        mock_image_data = MagicMock()
        mock_image_data.b64_json = self.test_image_b64
        mock_image_response = MagicMock()
        mock_image_response.data = [mock_image_data]
        mock_client.images.generate.return_value = mock_image_response

        # Create the ScriptAndImageFromInternet instance
        with (
            patch("pathlib.Path.write_text") as mock_write_text,
            patch("builtins.open", mock_open()) as mock_file,
        ):
            fetcher = ScriptAndImageFromInternet(self.test_run_dir, client=mock_client)

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
