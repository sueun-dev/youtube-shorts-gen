"""Tests for frame_interpolator and image_utils using real cv2/numpy/PIL.

These exercise the stub frame interpolation (cv2/numpy blending) and the
PIL-based text overlay helper with tiny, real, on-disk images.
"""

import cv2  # type: ignore
import numpy as np
from PIL import Image

from youtube_shorts_gen.utils.frame_interpolator import interpolate_between
from youtube_shorts_gen.utils.image_utils import overlay_text_on_images


def _make_image(path, color, size=(16, 16)):
    """Write a tiny solid-color BGR image to *path* via cv2."""
    height, width = size
    arr = np.zeros((height, width, 3), dtype=np.uint8)
    arr[:, :] = color
    assert cv2.imwrite(str(path), arr)
    return path


# --------------------------------------------------------------------------
# interpolate_between
# --------------------------------------------------------------------------


def test_interpolate_returns_n_readable_frames(tmp_path):
    """Happy path: returns num_inter_frames real, readable image files."""
    img1 = _make_image(tmp_path / "a.png", (0, 0, 0))
    img2 = _make_image(tmp_path / "b.png", (255, 255, 255))
    out_dir = tmp_path / "out"

    outputs = interpolate_between(img1, img2, num_inter_frames=4, output_dir=out_dir)

    assert len(outputs) == 4
    for path in outputs:
        assert path.startswith(str(out_dir))
        frame = cv2.imread(path)
        assert frame is not None
        assert frame.shape == (16, 16, 3)
    # Frames should be ordered/distinct: blending a black->white pair must
    # produce monotonically increasing brightness.
    means = []
    for p in outputs:
        frame = cv2.imread(p)
        assert frame is not None
        means.append(float(frame.mean()))
    assert means == sorted(means)
    assert means[0] < means[-1]


def test_interpolate_single_frame_edge_case(tmp_path):
    """Edge case: num_inter_frames=1 yields exactly one mid blend frame."""
    img1 = _make_image(tmp_path / "a.png", (0, 0, 0))
    img2 = _make_image(tmp_path / "b.png", (200, 200, 200))
    out_dir = tmp_path / "single"

    outputs = interpolate_between(img1, img2, num_inter_frames=1, output_dir=out_dir)

    assert len(outputs) == 1
    frame = cv2.imread(outputs[0])
    assert frame is not None
    # alpha = 1/(1+1) = 0.5 -> roughly half of 200.
    assert 90 <= float(frame.mean()) <= 110


def test_interpolate_resizes_mismatched_images(tmp_path):
    """Mismatched sizes are resized to the first image's shape."""
    img1 = _make_image(tmp_path / "a.png", (10, 20, 30), size=(16, 16))
    img2 = _make_image(tmp_path / "b.png", (40, 50, 60), size=(32, 8))
    out_dir = tmp_path / "resized"

    outputs = interpolate_between(img1, img2, num_inter_frames=2, output_dir=out_dir)

    assert len(outputs) == 2
    for path in outputs:
        frame = cv2.imread(path)
        assert frame is not None
        assert frame.shape == (16, 16, 3)


def test_interpolate_defaults_output_dir_to_img1_dir(tmp_path):
    """When output_dir is None, frames land next to the first image."""
    src_dir = tmp_path / "src"
    src_dir.mkdir()
    img1 = _make_image(src_dir / "a.png", (0, 0, 0))
    img2 = _make_image(src_dir / "b.png", (255, 255, 255))

    outputs = interpolate_between(img1, img2, num_inter_frames=2)

    assert len(outputs) == 2
    for path in outputs:
        assert str(src_dir) in path


def test_interpolate_non_positive_frames_returns_empty(tmp_path):
    """num_inter_frames <= 0 short-circuits to an empty list."""
    img1 = _make_image(tmp_path / "a.png", (0, 0, 0))
    img2 = _make_image(tmp_path / "b.png", (255, 255, 255))

    assert interpolate_between(img1, img2, num_inter_frames=0) == []
    assert interpolate_between(img1, img2, num_inter_frames=-3) == []


def test_interpolate_unreadable_image_returns_empty(tmp_path):
    """A missing/unreadable source image yields an empty list."""
    img1 = _make_image(tmp_path / "a.png", (0, 0, 0))
    missing = tmp_path / "does_not_exist.png"
    out_dir = tmp_path / "out"

    outputs = interpolate_between(img1, missing, num_inter_frames=3, output_dir=out_dir)

    assert outputs == []


# --------------------------------------------------------------------------
# overlay_text_on_images
# --------------------------------------------------------------------------


def _make_pil_image(path, size=(64, 64), color=(10, 20, 30)):
    """Write a tiny solid RGB image to *path* via PIL."""
    Image.new("RGB", size, color).save(path)
    return path


def test_overlay_returns_one_output_per_input(tmp_path):
    """Happy path: one saved output per input, all readable RGB images."""
    paths = [
        str(_make_pil_image(tmp_path / "one.png")),
        str(_make_pil_image(tmp_path / "two.png")),
    ]
    texts = ["HELLO", "WORLD"]
    out_dir = tmp_path / "overlaid"

    results = overlay_text_on_images(paths, texts, out_dir)

    assert len(results) == len(paths)
    for original, result in zip(paths, results, strict=True):
        assert result != original
        assert result.startswith(str(out_dir))
        with Image.open(result) as im:
            assert im.mode == "RGB"
            assert im.size == (64, 64)


def test_overlay_changes_pixels(tmp_path):
    """Overlaid text actually modifies pixels vs the source image."""
    src = _make_pil_image(tmp_path / "src.png", color=(0, 0, 0))
    out_dir = tmp_path / "out"

    results = overlay_text_on_images([str(src)], ["TEXT"], out_dir)

    assert len(results) == 1
    with Image.open(src) as before, Image.open(results[0]) as after:
        assert list(before.getdata()) != list(after.convert("RGB").getdata())


def test_overlay_mismatched_lengths_uses_shortest(tmp_path):
    """zip(strict=False) means extra images without text are skipped."""
    paths = [
        str(_make_pil_image(tmp_path / "a.png")),
        str(_make_pil_image(tmp_path / "b.png")),
    ]
    out_dir = tmp_path / "out"

    results = overlay_text_on_images(paths, ["only-one"], out_dir)

    assert len(results) == 1
    assert results[0].startswith(str(out_dir))


def test_overlay_unreadable_image_falls_back_to_original(tmp_path):
    """A bad image path is caught and the original path is returned."""
    good = str(_make_pil_image(tmp_path / "good.png"))
    bad = str(tmp_path / "missing.png")
    out_dir = tmp_path / "out"

    results = overlay_text_on_images([good, bad], ["a", "b"], out_dir)

    assert len(results) == 2
    assert results[0].startswith(str(out_dir))
    # Failed entry falls back to the original input path unchanged.
    assert results[1] == bad
