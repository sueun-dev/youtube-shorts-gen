"""Tests for the internet-content script/image module and the Dogdrip scraper."""

import shutil
import tempfile
import unittest
from unittest.mock import MagicMock, patch

from youtube_shorts_gen.content.script_and_image_from_internet import (
    ScriptAndImageFromInternet,
)
from youtube_shorts_gen.scrapers.dogdrip import fetch_dogdrip_content

_MODULE = "youtube_shorts_gen.content.script_and_image_from_internet"


class TestDogdripScraper(unittest.TestCase):
    """Tests for the functional Dogdrip scraper used in production."""

    @patch("youtube_shorts_gen.scrapers.dogdrip.time.sleep")
    @patch("youtube_shorts_gen.scrapers.dogdrip.requests.get")
    def test_fetch_dogdrip_content(self, mock_get, _mock_sleep):
        """The scraper visits the listing page then each post and returns text."""
        listing = MagicMock()
        listing.text = (
            "<html><body><td class='title'>"
            "<a class='link-reset' data-document-srl='123' href='/doc/123'>"
            "<span class='ed title-link'>Test Title</span></a></td></body></html>"
        )
        post = MagicMock()
        post.text = (
            "<html><body><div class='document_123_0'>Test content</div></body></html>"
        )
        mock_get.side_effect = [listing, post]

        stories = fetch_dogdrip_content()

        self.assertEqual(len(stories), 1)
        self.assertIn("Test Title", stories[0])
        self.assertIn("Test content", stories[0])
        self.assertEqual(mock_get.call_count, 2)


class TestScriptAndImageFromInternet(unittest.TestCase):
    """Tests for the ScriptAndImageFromInternet class."""

    def setUp(self):
        self.run_dir = tempfile.mkdtemp()
        self.fetcher = ScriptAndImageFromInternet(self.run_dir, client=MagicMock())

    def tearDown(self):
        shutil.rmtree(self.run_dir, ignore_errors=True)

    def test_tokenize_and_clean_splits_sentences(self):
        sentences = self.fetcher.tokenize_and_clean(
            "The dragon snarled loudly. The knight stepped back slowly. "
            "The princess was very afraid."
        )
        self.assertEqual(len(sentences), 3)
        self.assertEqual(sentences[0], "The dragon snarled loudly.")

    def test_normalise_caps_to_max(self):
        many = [f"Sentence number {i} here." for i in range(20)]
        self.assertEqual(len(self.fetcher.normalise_sentence_count(many)), 8)

    def test_normalise_splits_single_long_sentence(self):
        text = "a" * 20 + " " + "b" * 20
        result = self.fetcher.normalise_sentence_count(
            ["one chunk"], original_text=text
        )
        self.assertEqual(len(result), 2)

    @patch(f"{_MODULE}.generate_sequential_images")
    @patch(f"{_MODULE}.fetch_dogdrip_content")
    def test_run_returns_story_sentences_and_images(self, mock_fetch, mock_gen):
        mock_fetch.return_value = [
            "A dragon roared loudly. The knight fled fast. The princess laughed hard."
        ]
        mock_gen.side_effect = lambda client, prompts, paths: [str(p) for p in paths]

        result = self.fetcher.run()

        self.assertIn("story", result)
        self.assertIn("sentences", result)
        self.assertIn("image_paths", result)
        self.assertEqual(len(result["image_paths"]), len(result["sentences"]))
        mock_gen.assert_called_once()


if __name__ == "__main__":
    unittest.main()
