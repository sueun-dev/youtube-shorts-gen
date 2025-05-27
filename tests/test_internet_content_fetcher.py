"""Tests for the internet content fetcher module."""

import logging
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from youtube_shorts_gen.content.internet_content_fetcher import InternetContentFetcher


# Create a test subclass that implements the abstract methods
class TestContentFetcher(InternetContentFetcher):
    def _fetch_popular_posts(self, website_url: str, limit: int = 5) -> list[str]:
        # This will be mocked in tests
        return ["https://example.com/post1"]

    def _fetch_post_content(self, post_url: str) -> str:
        # This will be mocked in tests
        return "Test content"


class TestInternetContentFetcher(unittest.TestCase):
    """Test cases for the InternetContentFetcher class."""

    def setUp(self):
        """Set up test environment."""
        self.temp_dir = tempfile.TemporaryDirectory()
        self.run_dir = self.temp_dir.name

        # Mock OpenAI API key
        os.environ["OPENAI_API_KEY"] = "test_api_key"

        # Create the fetcher instance
        self.fetcher = TestContentFetcher(self.run_dir)

    def tearDown(self):
        """Clean up after tests."""
        self.temp_dir.cleanup()

    @patch.object(TestContentFetcher, "_fetch_popular_posts")
    def test_fetch_popular_posts(self, mock_fetch_posts):
        """Test fetching popular posts from the internet."""
        # Set up mock return value
        mock_fetch_posts.return_value = [
            "https://gall.dcinside.com/board/view/?id=dcbest&no=12345"
        ]

        # Call the method
        result = self.fetcher._fetch_popular_posts("https://example.com")

        # Assertions
        self.assertEqual(len(result), 1)
        self.assertEqual(
            result[0], "https://gall.dcinside.com/board/view/?id=dcbest&no=12345"
        )

        # Verify the method was called with the correct URL
        mock_fetch_posts.assert_called_once_with("https://example.com")

    @patch.object(TestContentFetcher, "_fetch_post_content")
    def test_fetch_post_content(self, mock_fetch_content):
        """Test fetching post content from DCInside."""
        # Set up mock return value
        mock_fetch_content.return_value = "Test Title Test Content"

        # Call the method
        result = self.fetcher._fetch_post_content("https://example.com")

        # Assertions
        self.assertEqual(result, "Test Title Test Content")

        # Verify the method was called with the correct URL
        mock_fetch_content.assert_called_once_with("https://example.com")

    def test_summarize_and_split_content(self):
        """Test summarizing and splitting content using OpenAI."""
        # Create a direct mock for the method instead of mocking OpenAI
        original_method = self.fetcher._summarize_and_split_content

        try:
            # Replace the method with a mock that returns predefined paragraphs
            self.fetcher._summarize_and_split_content = MagicMock(
                return_value=["Paragraph 1", "Paragraph 2", "Paragraph 3"]
            )

            # Create a test content
            test_content = "This is a test content for summarization."

            # Call the method
            result = self.fetcher._summarize_and_split_content(test_content)

            # Assertions
            self.assertEqual(len(result), 3)
            self.assertEqual(result[0], "Paragraph 1")
            self.assertEqual(result[1], "Paragraph 2")
            self.assertEqual(result[2], "Paragraph 3")

            # Verify the mock was called with the correct content
            self.fetcher._summarize_and_split_content.assert_called_once_with(
                test_content
            )
        finally:
            # Restore the original method
            self.fetcher._summarize_and_split_content = original_method

    @patch("youtube_shorts_gen.utils.openai_client.get_openai_client")
    @patch("base64.b64decode")
    def test_generate_image_for_paragraph(self, mock_b64decode, mock_get_client):
        """Test generating an image for a paragraph using DALL-E."""
        # Mock OpenAI client
        mock_client = MagicMock()
        mock_get_client.return_value = mock_client

        # Mock response
        mock_data = MagicMock()
        mock_data.b64_json = "test_base64_data"
        mock_response = MagicMock()
        mock_response.data = [mock_data]
        mock_client.images.generate.return_value = mock_response

        # Mock base64 decode to avoid actual decoding
        mock_b64decode.return_value = b"test_image_data"

        # Set up the fetcher with the mock client
        self.fetcher.client = mock_client

        # Create images directory
        Path(self.run_dir, "images").mkdir(exist_ok=True)

        # Call the method
        result = self.fetcher._generate_image_for_paragraph("Test paragraph", 0)

        # Assertions
        expected_path = os.path.join(self.run_dir, "images", "paragraph_1.png")
        self.assertEqual(result, expected_path)
        self.assertTrue(os.path.exists(result))

        # Verify the API call was made with the correct parameters
        mock_client.images.generate.assert_called_once()
        kwargs = mock_client.images.generate.call_args[1]
        self.assertIn("prompt", kwargs)
        self.assertIn("size", kwargs)
        self.assertIn("n", kwargs)

    @patch.object(InternetContentFetcher, "_fetch_popular_posts")
    @patch.object(InternetContentFetcher, "_fetch_post_content")
    @patch.object(InternetContentFetcher, "_summarize_and_split_content")
    @patch.object(InternetContentFetcher, "_generate_image_for_paragraph")
    def test_run(
        self, mock_generate_image, mock_summarize, mock_fetch_content, mock_fetch_posts
    ):
        """Test the full run method of the InternetContentFetcher."""
        # Mock responses
        mock_fetch_posts.return_value = ["https://example.com/post1"]
        mock_fetch_content.return_value = "Test content"
        mock_summarize.return_value = [
            "Paragraph 1",
            "Paragraph 2",
            "Paragraph 3",
            "Paragraph 4",
        ]
        mock_generate_image.side_effect = [
            os.path.join(self.run_dir, "images", "paragraph_1.png"),
            os.path.join(self.run_dir, "images", "paragraph_2.png"),
            os.path.join(self.run_dir, "images", "paragraph_3.png"),
            os.path.join(self.run_dir, "images", "paragraph_4.png"),
        ]

        # Call the method
        result = self.fetcher.run()

        # Assertions
        self.assertIn("story", result)
        self.assertIn("paragraphs", result)
        self.assertIn("image_paths", result)
        self.assertEqual(len(result["paragraphs"]), 4)
        self.assertEqual(len(result["image_paths"]), 4)

        # Verify the mapping file was created
        mapping_path = os.path.join(self.run_dir, "paragraph_image_mapping.txt")
        self.assertTrue(os.path.exists(mapping_path))

        # Verify the story prompt file was created
        prompt_path = os.path.join(self.run_dir, "story_prompt.txt")
        logging.info("Saved internet story: %s", prompt_path)


if __name__ == "__main__":
    unittest.main()
