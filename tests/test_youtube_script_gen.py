"""Tests for the AI script-and-image generator."""

import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from youtube_shorts_gen.content.script_and_image_gen import ScriptAndImageGenerator

_MODULE = "youtube_shorts_gen.content.script_and_image_gen"


class TestScriptAndImageGen(unittest.TestCase):
    """Tests for the ScriptAndImageGenerator class."""

    def setUp(self):
        self.run_dir = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.run_dir, ignore_errors=True)

    def _client_returning(self, story: str) -> MagicMock:
        client = MagicMock()
        response = MagicMock()
        response.choices = [MagicMock()]
        response.choices[0].message.content = story
        client.chat.completions.create.return_value = response
        return client

    @patch(f"{_MODULE}.generate_openai_image")
    def test_run_generates_story_and_image(self, mock_generate_image):
        client = self._client_returning("A glowing moon over a carnival.")
        mock_generate_image.return_value = str(Path(self.run_dir) / "story_image.png")

        result = ScriptAndImageGenerator(self.run_dir, client=client).run()

        client.chat.completions.create.assert_called_once()
        mock_generate_image.assert_called_once()
        self.assertEqual(result["story"], "A glowing moon over a carnival.")
        self.assertEqual(len(result["image_paths"]), 1)

    def test_run_propagates_api_errors(self):
        client = MagicMock()
        client.chat.completions.create.side_effect = ConnectionError("API down")

        with self.assertRaises(ConnectionError):
            ScriptAndImageGenerator(self.run_dir, client=client).run()


if __name__ == "__main__":
    unittest.main()
