"""Integration tests for the main entry point and the internet pipeline."""

import tempfile
import unittest
from unittest.mock import MagicMock, patch

import main
from youtube_shorts_gen.pipelines.internet_content_pipeline import (
    run_internet_content_pipeline,
)

_PIPE = "youtube_shorts_gen.pipelines.internet_content_pipeline"


class TestMainModule(unittest.TestCase):
    """Smoke tests for the public surface of the main module."""

    def test_main_exposes_pipeline_entrypoints(self):
        for name in ("run_pipeline_once", "main", "_process_pipeline_output"):
            self.assertTrue(callable(getattr(main, name, None)), name)

    def test_choice_constants_are_distinct(self):
        choices = {
            main.AI_CHOICE,
            main.INTERNET_CHOICE,
            main.YOUTUBE_TRANSCRIPT_CHOICE,
            main.TIMELAPSE_CHOICE,
        }
        self.assertEqual(len(choices), 4)


class TestInternetPipeline(unittest.TestCase):
    """Orchestration test for run_internet_content_pipeline with mocks."""

    @patch(f"{_PIPE}.VideoAssembler")
    @patch(f"{_PIPE}.VideoGenerator")
    @patch(f"{_PIPE}.MP3")
    @patch(f"{_PIPE}.ParagraphTTS")
    @patch(f"{_PIPE}.ScriptAndImageFromInternet")
    @patch(f"{_PIPE}.get_openai_client")
    def test_pipeline_produces_final_video(
        self, mock_client, mock_script, mock_tts, mock_mp3, mock_vgen, mock_vasm
    ):
        mock_client.return_value = MagicMock()
        mock_script.return_value.run.return_value = {
            "story": "A short story.",
            "sentences": ["Sentence one.", "Sentence two."],
            "image_paths": ["img1.png", "img2.png"],
        }
        mock_tts.return_value.generate_for_paragraphs.return_value = [
            "a1.mp3",
            "a2.mp3",
        ]
        mock_mp3.return_value.info.length = 3.0
        mock_vgen.return_value.generate.return_value = "base.mp4"
        assembler = mock_vasm.return_value
        assembler.create_looped_video.return_value = "looped.mp4"
        assembler.merge_audio_video.return_value = "segment.mp4"
        assembler.concatenate_segments.return_value = "final.mp4"

        with tempfile.TemporaryDirectory() as run_dir:
            result = run_internet_content_pipeline(run_dir)

        self.assertTrue(result["success"])
        self.assertEqual(result["final_video_path"], "final.mp4")
        self.assertEqual(len(result["segment_paths"]), 2)
        mock_script.return_value.run.assert_called_once()


if __name__ == "__main__":
    unittest.main()
