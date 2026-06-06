"""Regression tests for bugs found by the adversarial review.

Each test pins the corrected behavior so the bug cannot silently return.
"""

import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

from youtube_shorts_gen.content.transcript_segmenter import TranscriptSegmenter
from youtube_shorts_gen.media.paragraph_processor import ParagraphProcessor
from youtube_shorts_gen.media.video_audio_sync import VideoAudioSyncer
from youtube_shorts_gen.pipelines.youtube_transcript_pipeline import (
    _assemble_segment_videos,
    _generate_line_assets,
)
from youtube_shorts_gen.utils import config

_YT = "youtube_shorts_gen.pipelines.youtube_transcript_pipeline"


def test_chunk_merge_not_triggered_on_exact_multiple():
    """[bug 7] An exact multiple of the chunk size must not be merged."""
    segmenter = TranscriptSegmenter(client=MagicMock())
    words = "word " * (2 * config.TRANSCRIPT_WORDS_PER_CHUNK)  # exactly 2 chunks
    chunks = segmenter._split_into_chunks(words.strip())
    assert len(chunks) == 2  # not merged into one double-size chunk


def test_runway_timeout_keeps_line_lists_aligned():
    """[bug 1] A Runway timeout on one line must not desync audio/visuals."""
    tts = MagicMock()
    tts.run_dir = Path("/tmp")
    tts.generate_from_text.side_effect = lambda line: f"audio_{line}.mp3"
    vgen = MagicMock()
    # Line 1's Runway generation "times out" (returns ""); line 2 succeeds.
    vgen.generate.side_effect = ["", "clip2.mp4"]

    with patch(
        f"{_YT}.generate_image_for_line",
        side_effect=lambda client, line, path: f"img_{line}.png",
    ):
        images, audios, runways, generated, reused = _generate_line_assets(
            MagicMock(), ["L1", "L2"], Path("/tmp"), tts, vgen
        )

    assert len(images) == len(audios) == len(runways) == 2
    # Each list index still refers to the same line.
    assert images == ["img_L1.png", "img_L2.png"]
    assert audios == ["audio_L1.mp3", "audio_L2.mp3"]
    # Line 1 has no Runway clip (falls back to its own static image); line 2
    # keeps its own clip — never paired with the other line's audio.
    assert runways == ["", "clip2.mp4"]
    assert generated == 1
    assert reused == 0


def test_empty_runway_path_falls_back_to_static_image():
    """[bug 1b] An empty runway path must not pass Path("").exists() (which is
    True), and must fall back to the line's own static image."""
    assembler = MagicMock()
    assembler.create_segment_video.return_value = "static.mp4"

    _assemble_segment_videos(assembler, ["img0"], ["a0"], [""])

    assembler.create_segment_video.assert_called_once_with(
        image_path="img0", audio_path="a0", index=0
    )
    assembler.create_segment_video_with_runway.assert_not_called()


def test_partial_tts_failure_keeps_text_image_audio_aligned():
    """[bug 6] A non-trailing TTS failure must not mispair audio with images."""
    run_dir = tempfile.mkdtemp()
    try:
        processor = ParagraphProcessor(run_dir, client=MagicMock())
        segment_calls = []

        def fake_segment(image_path, audio_path, index):
            segment_calls.append((image_path, audio_path))
            return str(Path(run_dir) / "segments" / f"seg{index}.mp4")

        with (
            patch.object(
                processor.text_processor,
                "get_content_segments",
                return_value=["T0", "T1", "T2"],
            ),
            patch.object(
                ParagraphProcessor,
                "_get_existing_image_paths",
                return_value=["i0", "i1", "i2"],
            ),
            patch.object(
                processor.tts_generator,
                "generate_for_paragraphs",
                return_value=["a0", "", "a2"],  # middle paragraph's TTS failed
            ),
            patch.object(
                processor.video_assembler,
                "create_segment_video",
                side_effect=fake_segment,
            ),
            patch.object(
                processor.video_assembler,
                "concatenate_segments",
                return_value="final.mp4",
            ),
        ):
            processor.process("story text")

        # i2 must be paired with a2 (its own audio), NOT with a2-shifted-onto-i1.
        assert segment_calls == [("i0", "a0"), ("i2", "a2")]
    finally:
        import shutil

        shutil.rmtree(run_dir, ignore_errors=True)


def test_get_duration_returns_zero_for_na(tmp_path):
    """[bug 5] ffprobe 'N/A' must degrade to 0.0, not raise ValueError."""
    syncer = VideoAudioSyncer(str(tmp_path))
    fake = MagicMock()
    fake.stdout = "N/A\n"
    target = "youtube_shorts_gen.media.video_audio_sync.subprocess.run"
    with patch(target, return_value=fake):
        assert syncer.get_duration(tmp_path / "x.mp4") == 0.0


def test_image_sizes_match_gpt_image_1():
    """[bug 9] The validated image sizes must match the gpt-image-1 model."""
    assert "1536x1024" in config.IMAGE_SIZES
    assert "1024x1536" in config.IMAGE_SIZES
    # DALL-E-3-only sizes must not be accepted for gpt-image-1.
    assert "1792x1024" not in config.IMAGE_SIZES
    assert "1024x1792" not in config.IMAGE_SIZES
