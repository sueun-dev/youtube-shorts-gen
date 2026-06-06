"""End-to-end pipeline tests that run REAL ffmpeg with mocked external APIs.

These exercise the orchestration + video-assembly paths of the content
pipelines without calling OpenAI/ElevenLabs/Runway/YouTube. Image generation,
TTS, and Runway clips are mocked to produce real local files; ffmpeg, cv2, and
PIL run for real. The module skips entirely when ffmpeg is unavailable.
"""

import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch

import cv2
import numpy as np
import pytest

from tests.conftest import has_ffmpeg
from youtube_shorts_gen.media.video_assembler import VideoAssembler

pytestmark = pytest.mark.skipif(not has_ffmpeg(), reason="ffmpeg not available")


def _png(path: Path, shade: int = 100) -> str:
    cv2.imwrite(str(path), np.full((128, 128, 3), shade, np.uint8))
    return str(path)


def _silent_mp3(path: Path, seconds: int = 2) -> str:
    subprocess.run(
        [
            "ffmpeg", "-y", "-f", "lavfi", "-i", "anullsrc=r=44100:cl=stereo",
            "-t", str(seconds), "-q:a", "9", str(path),
        ],
        check=True,
        capture_output=True,
    )
    return str(path)


def _nonempty(path: str) -> bool:
    return bool(path) and Path(path).exists() and Path(path).stat().st_size > 0


def test_internet_pipeline_end_to_end(tmp_path):
    """run_internet_content_pipeline assembles a real final video."""
    pipe = "youtube_shorts_gen.pipelines.internet_content_pipeline"
    from youtube_shorts_gen.pipelines.internet_content_pipeline import (
        run_internet_content_pipeline,
    )

    run_dir = tmp_path / "run"
    (run_dir / "images").mkdir(parents=True)
    img1 = _png(run_dir / "images" / "sentence_1.png")
    img2 = _png(run_dir / "images" / "sentence_2.png", shade=180)
    base_video = VideoAssembler(str(run_dir)).create_video_from_images(
        [img1], output_filename="base.mp4", fps=4
    )
    audio1 = _silent_mp3(run_dir / "a1.mp3")
    audio2 = _silent_mp3(run_dir / "a2.mp3")

    script = MagicMock()
    script.run.return_value = {
        "story": "A short tale.",
        "sentences": ["First sentence here.", "Second sentence here."],
        "image_paths": [img1, img2],
    }
    tts = MagicMock()
    tts.generate_for_paragraphs.return_value = [audio1, audio2]
    vgen = MagicMock()
    vgen.generate.return_value = base_video

    with (
        patch(f"{pipe}.get_openai_client", return_value=MagicMock()),
        patch(f"{pipe}.ScriptAndImageFromInternet", return_value=script),
        patch(f"{pipe}.ParagraphTTS", return_value=tts),
        patch(f"{pipe}.VideoGenerator", return_value=vgen),
    ):
        result = run_internet_content_pipeline(str(run_dir))

    assert result["success"] is True
    assert len(result["segment_paths"]) == 2
    assert _nonempty(result["final_video_path"])


def test_timelapse_pipeline_end_to_end(tmp_path):
    """run_timelapse_pipeline overlays, interpolates, and renders a real video."""
    mod = "youtube_shorts_gen.pipelines.timelapse_pipeline"
    from youtube_shorts_gen.pipelines.timelapse_pipeline import run_timelapse_pipeline

    def fake_generate(client, prompts, paths):
        for i, p in enumerate(paths):
            cv2.imwrite(str(p), np.full((128, 128, 3), 30 * i + 20, np.uint8))
        return [str(p) for p in paths]

    run_dir = tmp_path / "run"
    run_dir.mkdir()
    with patch(f"{mod}.generate_sequential_images", side_effect=fake_generate):
        out = run_timelapse_pipeline(
            str(run_dir),
            MagicMock(),
            "Red Ferrari",
            2000,
            2003,
            upload_to_youtube=False,
        )

    assert _nonempty(out)


def test_ai_pipeline_end_to_end(tmp_path):
    """run_ai_content_pipeline syncs a real video and audio with ffmpeg."""
    pipe = "youtube_shorts_gen.pipelines.ai_content_pipeline"
    from youtube_shorts_gen.pipelines.ai_content_pipeline import run_ai_content_pipeline

    run_dir = tmp_path / "run"
    run_dir.mkdir()

    def make_base_video(*_args, **_kwargs):
        img = _png(run_dir / "vg.png")
        return VideoAssembler(str(run_dir)).create_video_from_images(
            [img], output_filename="output_story_video.mp4", fps=4
        )

    def make_audio(*_args, **_kwargs):
        return _silent_mp3(run_dir / "story_audio.mp3")

    script = MagicMock()
    script.run.return_value = {"story": "tale", "image_paths": ["vg.png"]}
    vgen = MagicMock()
    vgen.generate.side_effect = make_base_video
    tts = MagicMock()
    tts.generate_from_file.side_effect = make_audio

    with (
        patch(f"{pipe}.get_openai_client", return_value=MagicMock()),
        patch(f"{pipe}.ScriptAndImageGenerator", return_value=script),
        patch(f"{pipe}.VideoGenerator", return_value=vgen),
        patch(f"{pipe}.TTSGenerator", return_value=tts),
    ):
        result = run_ai_content_pipeline(str(run_dir))

    assert result["success"] is True
    assert _nonempty(result["final_video_path"])


def test_internet_pipeline_reports_failure(tmp_path):
    """A failing content step yields success=False, not an exception."""
    pipe = "youtube_shorts_gen.pipelines.internet_content_pipeline"
    from youtube_shorts_gen.pipelines.internet_content_pipeline import (
        run_internet_content_pipeline,
    )

    script = MagicMock()
    script.run.side_effect = RuntimeError("no stories")

    with (
        patch(f"{pipe}.get_openai_client", return_value=MagicMock()),
        patch(f"{pipe}.ScriptAndImageFromInternet", return_value=script),
    ):
        result = run_internet_content_pipeline(str(tmp_path))

    assert result["success"] is False
    assert "no stories" in result["error"]


if __name__ == "__main__":
    import sys

    sys.exit(pytest.main([__file__, "-v"]))
