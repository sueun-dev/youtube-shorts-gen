"""Integration tests for ParagraphProcessor and the internet content chain."""

import base64
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from youtube_shorts_gen.content.script_and_image_from_internet import (
    ScriptAndImageFromInternet,
)
from youtube_shorts_gen.media.paragraph_processor import ParagraphProcessor

_PNG_1X1 = (
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmM"
    "IQAAAABJRU5ErkJggg=="
)
_INET = "youtube_shorts_gen.content.script_and_image_from_internet"
_PP = "youtube_shorts_gen.media.paragraph_processor"
_VASM = "youtube_shorts_gen.media.video_assembler.VideoAssembler"

_STORY = (
    "The dragon snarled at the knight as she hid the princess behind her. "
    "Rearing her head back she let out a loud roar."
)
_PARAGRAPHS = [
    "The dragon snarled at the knight as she hid the princess behind her.",
    "Rearing her head back she let out a loud roar.",
]


class TestVideoCreationPipeline(unittest.TestCase):
    """Tests that the pipeline pairs every image with a segment correctly."""

    def setUp(self):
        self.run_dir = tempfile.mkdtemp()
        self.images_dir = Path(self.run_dir, "images")
        self.images_dir.mkdir(parents=True, exist_ok=True)
        self.image_paths = []
        for i in range(1, 3):
            path = self.images_dir / f"sentence_{i}.png"
            path.write_bytes(base64.b64decode(_PNG_1X1))
            self.image_paths.append(str(path))

    def tearDown(self):
        shutil.rmtree(self.run_dir, ignore_errors=True)

    @patch(f"{_PP}.ParagraphTTS")
    def test_pipeline_uses_all_images(self, mock_tts):
        mock_tts.return_value.generate_for_paragraphs.return_value = [
            f"{self.run_dir}/paragraph_audio/paragraph_1.mp3",
            f"{self.run_dir}/paragraph_audio/paragraph_2.mp3",
        ]

        segment_calls = []

        def fake_segment(*_args, **kwargs):
            segment_calls.append(kwargs.get("image_path"))
            return f"{self.run_dir}/segments/segment_{kwargs.get('index')}.mp4"

        with (
            patch.object(
                ParagraphProcessor,
                "_get_existing_image_paths",
                return_value=self.image_paths,
            ),
            patch(f"{_VASM}.create_segment_video", side_effect=fake_segment),
            patch(
                f"{_VASM}.concatenate_segments",
                return_value=f"{self.run_dir}/final_story_video.mp4",
            ),
        ):
            processor = ParagraphProcessor(self.run_dir, client=MagicMock())
            with patch.object(
                processor.text_processor,
                "get_content_segments",
                return_value=_PARAGRAPHS,
            ):
                result = processor.process(_STORY)

        self.assertEqual(len(result["segment_paths"]), 2)
        self.assertEqual(len(result["processed_paragraphs"]), 2)
        self.assertEqual(segment_calls, self.image_paths)

    @patch(f"{_INET}.generate_sequential_images")
    @patch(f"{_INET}.fetch_dogdrip_content")
    @patch(f"{_PP}.ParagraphTTS")
    def test_end_to_end_content_to_video(self, mock_tts, mock_fetch, mock_gen):
        mock_fetch.return_value = [_STORY]
        mock_gen.side_effect = lambda client, prompts, paths: [str(p) for p in paths]
        mock_tts.return_value.generate_for_paragraphs.return_value = [
            f"{self.run_dir}/paragraph_audio/paragraph_1.mp3",
            f"{self.run_dir}/paragraph_audio/paragraph_2.mp3",
        ]
        client = MagicMock()

        script_result = ScriptAndImageFromInternet(self.run_dir, client=client).run()
        self.assertIn("story", script_result)
        self.assertIn("sentences", script_result)
        self.assertIn("image_paths", script_result)

        processor = ParagraphProcessor(self.run_dir, client=client)
        with (
            patch.object(
                processor.text_processor,
                "get_content_segments",
                return_value=_PARAGRAPHS,
            ),
            patch.object(
                ParagraphProcessor,
                "_get_existing_image_paths",
                return_value=self.image_paths,
            ),
            patch(
                f"{_VASM}.create_segment_video",
                return_value=f"{self.run_dir}/segments/segment_1.mp4",
            ),
            patch(
                f"{_VASM}.concatenate_segments",
                return_value=f"{self.run_dir}/final_story_video.mp4",
            ),
        ):
            video_result = processor.process(script_result["story"])

        self.assertIn("segment_paths", video_result)
        self.assertIn("processed_paragraphs", video_result)


if __name__ == "__main__":
    unittest.main()
