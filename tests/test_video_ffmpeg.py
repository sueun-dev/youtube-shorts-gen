"""Real-ffmpeg tests for VideoAssembler and VideoAudioSyncer.

These exercise the actual ffmpeg/ffprobe subprocess paths. The whole module
skips when ffmpeg/ffprobe are not available on PATH.
"""

import base64
import struct
import subprocess
import zlib
from pathlib import Path

import pytest

from tests.conftest import has_ffmpeg
from youtube_shorts_gen.media.video_assembler import VideoAssembler
from youtube_shorts_gen.media.video_audio_sync import VideoAudioSyncer

pytestmark = pytest.mark.skipif(
    not has_ffmpeg(), reason="ffmpeg not available"
)

# A 1x1 transparent PNG (decodes cleanly for ffmpeg image input).
_PNG_1X1 = (
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmM"
    "IQAAAABJRU5ErkJggg=="
)


def _png_chunk(tag: bytes, data: bytes) -> bytes:
    return (
        struct.pack(">I", len(data))
        + tag
        + data
        + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)
    )


def _write_png(path: Path, size: int = 16) -> Path:
    """Write a tiny opaque RGB PNG of ``size`` x ``size`` pixels."""
    ihdr = struct.pack(">IIBBBBB", size, size, 8, 2, 0, 0, 0)
    # One filter byte (0) per row, then size RGB pixels.
    row = b"\x00" + b"\x40\x80\xc0" * size
    raw = row * size
    idat = zlib.compress(raw, 9)
    png = (
        b"\x89PNG\r\n\x1a\n"
        + _png_chunk(b"IHDR", ihdr)
        + _png_chunk(b"IDAT", idat)
        + _png_chunk(b"IEND", b"")
    )
    path.write_bytes(png)
    return path


def _make_image(tmp_path: Path, name: str = "img.png", size: int = 16) -> str:
    return str(_write_png(tmp_path / name, size))


def _make_silent_mp3(path: Path, seconds: int = 2) -> str:
    """Synthesize a short silent stereo mp3 with ffmpeg."""
    subprocess.run(
        [
            "ffmpeg",
            "-y",
            "-f",
            "lavfi",
            "-i",
            "anullsrc=r=44100:cl=stereo",
            "-t",
            str(seconds),
            "-q:a",
            "9",
            str(path),
        ],
        check=True,
        capture_output=True,
    )
    return str(path)


# --------------------------------------------------------------------------
# VideoAssembler._get_audio_duration
# --------------------------------------------------------------------------


def test_get_audio_duration_real_file(tmp_path):
    audio = _make_silent_mp3(tmp_path / "a.mp3", seconds=2)
    assembler = VideoAssembler(str(tmp_path / "run"))
    duration = assembler._get_audio_duration(audio)
    assert 1.5 < duration < 2.7


def test_get_audio_duration_missing_file_returns_zero(tmp_path):
    assembler = VideoAssembler(str(tmp_path / "run"))
    missing = str(tmp_path / "nope.mp3")
    assert assembler._get_audio_duration(missing) == 0.0


# --------------------------------------------------------------------------
# VideoAssembler.create_segment_video
# --------------------------------------------------------------------------


def test_create_segment_video_happy_path(tmp_path):
    img = _make_image(tmp_path)
    audio = _make_silent_mp3(tmp_path / "a.mp3", seconds=2)
    assembler = VideoAssembler(str(tmp_path / "run"))

    out = assembler.create_segment_video(img, audio, index=0)

    assert out
    out_path = Path(out)
    assert out_path.exists()
    assert out_path.stat().st_size > 0
    assert out_path.name == "segment_1.mp4"
    # The produced video should be readable by ffprobe with a sane duration.
    assert assembler._get_video_duration(out) > 1.0


def test_create_segment_video_missing_image_returns_empty(tmp_path):
    audio = _make_silent_mp3(tmp_path / "a.mp3", seconds=2)
    assembler = VideoAssembler(str(tmp_path / "run"))
    out = assembler.create_segment_video(
        str(tmp_path / "missing.png"), audio, index=0
    )
    assert out == ""


def test_create_segment_video_missing_audio_returns_empty(tmp_path):
    img = _make_image(tmp_path)
    assembler = VideoAssembler(str(tmp_path / "run"))
    out = assembler.create_segment_video(
        img, str(tmp_path / "missing.mp3"), index=0
    )
    assert out == ""


# --------------------------------------------------------------------------
# VideoAssembler.create_video_from_images
# --------------------------------------------------------------------------


def test_create_video_from_images_happy_path(tmp_path):
    img = _make_image(tmp_path)
    assembler = VideoAssembler(str(tmp_path / "run"))
    out = assembler.create_video_from_images([img])
    assert out
    out_path = Path(out)
    assert out_path.exists()
    assert out_path.stat().st_size > 0
    # Temp processing dir is cleaned up afterwards.
    assert not (assembler.run_dir / "temp_images").exists()


def test_create_video_from_images_empty_list_returns_empty(tmp_path):
    assembler = VideoAssembler(str(tmp_path / "run"))
    assert assembler.create_video_from_images([]) == ""


def test_create_video_from_images_missing_file_returns_empty(tmp_path):
    assembler = VideoAssembler(str(tmp_path / "run"))
    out = assembler.create_video_from_images([str(tmp_path / "gone.png")])
    assert out == ""


# --------------------------------------------------------------------------
# VideoAssembler.concatenate_segments
# --------------------------------------------------------------------------


def test_concatenate_segments_happy_path(tmp_path):
    img = _make_image(tmp_path)
    audio = _make_silent_mp3(tmp_path / "a.mp3", seconds=2)
    assembler = VideoAssembler(str(tmp_path / "run"))
    seg = assembler.create_segment_video(img, audio, index=0)
    assert seg

    final = assembler.concatenate_segments([seg, seg])

    assert final
    final_path = Path(final)
    assert final_path.exists()
    assert final_path.stat().st_size > 0
    # Two copies of a ~2s segment -> roughly 4s.
    assert assembler._get_video_duration(final) > 3.0


def test_concatenate_segments_empty_returns_empty(tmp_path):
    assembler = VideoAssembler(str(tmp_path / "run"))
    assert assembler.concatenate_segments([]) == ""


def test_concatenate_segments_only_invalid_paths_returns_empty(tmp_path):
    assembler = VideoAssembler(str(tmp_path / "run"))
    out = assembler.concatenate_segments(["", str(tmp_path / "missing.mp4")])
    assert out == ""


# --------------------------------------------------------------------------
# VideoAssembler.merge_audio_video + create_looped_video
# --------------------------------------------------------------------------


def test_merge_audio_video_happy_path(tmp_path):
    img = _make_image(tmp_path)
    audio = _make_silent_mp3(tmp_path / "a.mp3", seconds=2)
    assembler = VideoAssembler(str(tmp_path / "run"))
    seg = assembler.create_segment_video(img, audio, index=0)
    assert seg

    out = str(tmp_path / "merged.mp4")
    result = assembler.merge_audio_video(seg, audio, out)

    assert result == out
    assert Path(out).exists()
    assert Path(out).stat().st_size > 0


def test_merge_audio_video_missing_video_returns_empty(tmp_path):
    audio = _make_silent_mp3(tmp_path / "a.mp3", seconds=2)
    assembler = VideoAssembler(str(tmp_path / "run"))
    out = assembler.merge_audio_video(
        str(tmp_path / "missing.mp4"), audio, str(tmp_path / "o.mp4")
    )
    assert out == ""


def test_create_looped_video_happy_path(tmp_path):
    img = _make_image(tmp_path)
    audio = _make_silent_mp3(tmp_path / "a.mp3", seconds=2)
    assembler = VideoAssembler(str(tmp_path / "run"))
    seg = assembler.create_segment_video(img, audio, index=0)
    assert seg

    out = str(tmp_path / "looped.mp4")
    result = assembler.create_looped_video(
        seg, target_duration=5.0, output_video_path=out
    )

    assert result == out
    looped = Path(out)
    assert looped.exists()
    # Looping a ~2s clip to reach 5s should produce >= ~6s (ceil(5/2)=3 loops).
    assert assembler._get_video_duration(out) > 4.0
    # Concat list temp file is removed in the finally block.
    assert not (looped.parent / f"loop_list_{looped.stem}.txt").exists()


def test_create_looped_video_missing_input_returns_empty(tmp_path):
    assembler = VideoAssembler(str(tmp_path / "run"))
    out = assembler.create_looped_video(
        str(tmp_path / "missing.mp4"), 5.0, str(tmp_path / "o.mp4")
    )
    assert out == ""


# --------------------------------------------------------------------------
# VideoAudioSyncer
# --------------------------------------------------------------------------


def test_syncer_get_duration_real_file(tmp_path):
    audio = _make_silent_mp3(tmp_path / "a.mp3", seconds=2)
    syncer = VideoAudioSyncer(str(tmp_path))
    duration = syncer.get_duration(Path(audio))
    assert isinstance(duration, float)
    assert 1.5 < duration < 2.7


def test_syncer_get_duration_missing_file_raises(tmp_path):
    syncer = VideoAudioSyncer(str(tmp_path))
    with pytest.raises(subprocess.CalledProcessError):
        syncer.get_duration(tmp_path / "missing.mp3")


def test_syncer_full_sync_happy_path(tmp_path):
    """End-to-end sync over a real generated video + audio."""
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    img = _make_image(run_dir, "img.png")
    seg_audio = _make_silent_mp3(run_dir / "seg.mp3", seconds=2)

    assembler = VideoAssembler(str(run_dir))
    seg = assembler.create_segment_video(img, seg_audio, index=0)
    assert seg

    syncer = VideoAudioSyncer(str(run_dir))
    # Place the inputs the syncer expects at its configured paths.
    Path(seg).replace(syncer.input_video)
    _make_silent_mp3(syncer.audio_path, seconds=3)

    result = syncer.sync()

    assert result == str(syncer.final_video)
    assert syncer.final_video.exists()
    assert syncer.final_video.stat().st_size > 0


def test_syncer_sync_missing_input_video_raises(tmp_path):
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    syncer = VideoAudioSyncer(str(run_dir))
    _make_silent_mp3(syncer.audio_path, seconds=2)
    with pytest.raises(FileNotFoundError):
        syncer.sync()


def test_png_fixture_decodes(tmp_path):
    """Sanity check that the embedded base64 PNG is still valid."""
    path = tmp_path / "embedded.png"
    path.write_bytes(base64.b64decode(_PNG_1X1))
    assert path.stat().st_size > 0


# --------------------------------------------------------------------------
# Smooth timelapse / slideshow / runway-segment (the heaviest ffmpeg paths)
# --------------------------------------------------------------------------


def _nonempty_file(path: str) -> bool:
    return bool(path) and Path(path).exists() and Path(path).stat().st_size > 0


def test_create_smooth_timelapse_with_transitions(tmp_path):
    """Multi-image timelapse builds a real video via xfade transitions."""
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    va = VideoAssembler(str(run_dir))
    images = [_make_image(tmp_path, f"frame_{i}.png") for i in range(3)]

    out = va.create_smooth_timelapse(
        images,
        output_filename="timelapse.mp4",
        transition_duration=0.2,
        frame_duration=0.6,
    )

    assert _nonempty_file(out)


def test_create_smooth_timelapse_with_music(tmp_path):
    """The music path merges a background track over the timelapse."""
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    va = VideoAssembler(str(run_dir))
    images = [_make_image(tmp_path, f"m_{i}.png") for i in range(2)]
    music = _make_silent_mp3(tmp_path / "bg.mp3", seconds=3)

    out = va.create_smooth_timelapse(
        images,
        output_filename="timelapse_music.mp4",
        transition_duration=0.2,
        frame_duration=0.6,
        music_path=music,
    )

    assert _nonempty_file(out)


def test_create_smooth_timelapse_custom_frame_durations(tmp_path):
    """Per-frame durations are honoured without error."""
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    va = VideoAssembler(str(run_dir))
    images = [_make_image(tmp_path, f"d_{i}.png") for i in range(3)]

    out = va.create_smooth_timelapse(
        images,
        output_filename="timelapse_durations.mp4",
        transition_duration=0.2,
        frame_durations=[0.5, 0.3, 0.5],
    )

    assert _nonempty_file(out)


def test_create_smooth_timelapse_single_image_fallback(tmp_path):
    """A single image falls back to a plain (transition-free) video."""
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    va = VideoAssembler(str(run_dir))
    image = _make_image(tmp_path, "solo.png")

    out = va.create_smooth_timelapse([image], output_filename="solo.mp4")

    assert _nonempty_file(out)


def test_create_smooth_timelapse_empty_returns_empty(tmp_path):
    """No images yields an empty string, not a crash."""
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    va = VideoAssembler(str(run_dir))

    assert va.create_smooth_timelapse([]) == ""


def test_create_slideshow_video(tmp_path):
    """A slideshow pairs each image with its narration audio."""
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    va = VideoAssembler(str(run_dir))
    images = [_make_image(tmp_path, f"slide_{i}.png") for i in range(2)]
    audios = [_make_silent_mp3(tmp_path / f"a_{i}.mp3", seconds=1) for i in range(2)]

    out = va.create_slideshow_video(images, audios, final_video_name="slideshow.mp4")

    assert _nonempty_file(out)


def test_create_segment_video_with_runway(tmp_path):
    """A Runway-style base video is merged with audio into a segment."""
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    va = VideoAssembler(str(run_dir))
    image = _make_image(tmp_path, "rw.png")
    base_video = va.create_video_from_images(
        [image], output_filename="rw_base.mp4", fps=4
    )
    assert _nonempty_file(base_video)
    audio = _make_silent_mp3(tmp_path / "rw.mp3", seconds=2)

    out = va.create_segment_video_with_runway(base_video, audio, index=0)

    assert _nonempty_file(out)


def test_crossfade_transition_has_real_duration(tmp_path):
    """[bug 4] An xfade clip must span transition_duration, not a single frame."""
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    va = VideoAssembler(str(run_dir))
    images = [_make_image(tmp_path, f"xf_{i}.png") for i in range(2)]
    transitions_dir = tmp_path / "trans"
    transitions_dir.mkdir()

    clips = va._build_xfade_filter(images, transitions_dir, "fade", 0.5)

    assert clips is not None
    assert len(clips) == 1
    probe = subprocess.run(
        [
            "ffprobe", "-v", "error", "-show_entries", "format=duration",
            "-of", "default=noprint_wrappers=1:nokey=1", clips[0],
        ],
        capture_output=True,
        text=True,
        check=True,
    )
    # ~0.5s, far above the ~0.033s (one-frame) collapse the old code produced.
    assert float(probe.stdout.strip()) >= 0.4
