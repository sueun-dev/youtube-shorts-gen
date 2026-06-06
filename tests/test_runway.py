"""Unit tests for youtube_shorts_gen.media.runway.VideoGenerator.

All RunwayML SDK calls, HTTP requests, and sleeps are mocked so the tests are
fully hermetic and fast. File I/O is confined to pytest's tmp_path.
"""

import base64
from unittest.mock import MagicMock, patch

import pytest

from youtube_shorts_gen.media.runway import VideoGenerator

_MOD = "youtube_shorts_gen.media.runway"

# A 1x1 transparent PNG, base64-encoded.
_PNG_B64 = (
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmM"
    "IQAAAABJRU5ErkJggg=="
)


def _write_png(path):
    """Write a tiny real PNG to *path* and return the path as a string."""
    path.write_bytes(base64.b64decode(_PNG_B64))
    return str(path)


def _make_generator(run_dir):
    """Build a VideoGenerator with a mocked RunwayML client.

    Returns ``(generator, mock_client)`` where ``mock_client`` is the MagicMock
    standing in for the RunwayML SDK client, so tests configure it directly.
    """
    with (
        patch(f"{_MOD}.RUNWAY_API_KEY", "test-key"),
        patch(f"{_MOD}.RunwayML") as mock_runway,
    ):
        gen = VideoGenerator(str(run_dir))
    mock_client = mock_runway.return_value
    assert gen.client is mock_client
    return gen, mock_client


def test_init_requires_api_key(tmp_path):
    """__init__ raises ValueError when RUNWAY_API_KEY is empty."""
    with (
        patch(f"{_MOD}.RUNWAY_API_KEY", ""),
        patch(f"{_MOD}.RunwayML"),
        pytest.raises(ValueError, match="RUNWAY_API_KEY"),
    ):
        VideoGenerator(str(tmp_path))


def test_create_runway_prompt_non_empty_and_saved(tmp_path):
    """_create_runway_prompt builds a non-empty string and saves it to disk."""
    gen, _ = _make_generator(tmp_path)

    prompt = gen._create_runway_prompt("A brave knight rescues a dragon today")

    assert isinstance(prompt, str)
    assert prompt.strip() != ""
    # Template fragments must be present.
    assert "realistic details" in prompt
    assert "cinematic lighting" in prompt
    saved = tmp_path / "runway_prompt.txt"
    assert saved.exists()
    assert saved.read_text(encoding="utf-8") == prompt


def test_create_runway_prompt_empty_story_uses_default_subject(tmp_path):
    """An empty story still yields a usable prompt (default subject path)."""
    gen, _ = _make_generator(tmp_path)

    prompt = gen._create_runway_prompt("")

    assert prompt.strip() != ""
    assert (tmp_path / "runway_prompt.txt").exists()


def test_image_to_data_uri_png(tmp_path):
    """_image_to_data_uri returns a base64 PNG data URI for a real file."""
    gen, _ = _make_generator(tmp_path)
    image_path = _write_png(tmp_path / "frame.png")

    uri = gen._image_to_data_uri(image_path)

    assert uri.startswith("data:image/png;base64,")
    encoded = uri.split(",", 1)[1]
    # Round-trips back to the original PNG bytes.
    assert base64.b64decode(encoded) == base64.b64decode(_PNG_B64)


def test_image_to_data_uri_jpg_mime(tmp_path):
    """A .jpg extension maps to the image/jpeg MIME type."""
    gen, _ = _make_generator(tmp_path)
    image_path = tmp_path / "frame.jpg"
    image_path.write_bytes(base64.b64decode(_PNG_B64))

    uri = gen._image_to_data_uri(str(image_path))

    assert uri.startswith("data:image/jpeg;base64,")


def test_generate_missing_image_raises(tmp_path):
    """generate() raises FileNotFoundError when the image path is absent."""
    gen, _ = _make_generator(tmp_path)
    missing = tmp_path / "does_not_exist.png"

    with pytest.raises(FileNotFoundError, match="Image file not found"):
        gen.generate(image_path=str(missing), prompt_text="hello world")


def test_generate_happy_path_returns_video_path(tmp_path):
    """Full happy path: create -> poll SUCCEEDED -> download -> return path."""
    gen, client = _make_generator(tmp_path)
    image_path = _write_png(tmp_path / "story_image.png")

    client.image_to_video.create.return_value = MagicMock(id="task-123")

    succeeded = MagicMock()
    succeeded.status = "SUCCEEDED"
    succeeded.output = ["http://x/v.mp4"]
    client.tasks.retrieve.return_value = succeeded

    http_response = MagicMock()
    http_response.status_code = 200
    http_response.iter_content.return_value = [b"chunk1", b"chunk2"]

    with (
        patch(f"{_MOD}.time.sleep"),
        patch(f"{_MOD}.requests.get", return_value=http_response) as mock_get,
    ):
        result = gen.generate(
            image_path=image_path, prompt_text="a serene mountain river"
        )

    # The create call carried the data URI and the generated prompt.
    create_kwargs = client.image_to_video.create.call_args.kwargs
    assert create_kwargs["prompt_image"].startswith("data:image/png;base64,")
    assert create_kwargs["prompt_text"].strip() != ""

    assert result != ""
    assert result.endswith(".mp4")
    out_path = tmp_path / "videos" / f"runway_video_{gen.current_video_id}.mp4"
    assert str(out_path) == result
    assert out_path.exists()
    assert out_path.read_bytes() == b"chunk1chunk2"
    mock_get.assert_called_once()
    assert mock_get.call_args.args[0] == "http://x/v.mp4"


def test_generate_uses_default_image_and_prompt_files(tmp_path):
    """With no args, generate() reads story_image.png and the prompt file."""
    gen, client = _make_generator(tmp_path)
    _write_png(tmp_path / "story_image.png")
    (tmp_path / "story_prompt.txt").write_text(
        "A quiet forest at dawn", encoding="utf-8"
    )

    client.image_to_video.create.return_value = MagicMock(id="t1")
    ok = MagicMock()
    ok.status = "SUCCEEDED"
    ok.output = ["http://x/v.mp4"]
    client.tasks.retrieve.return_value = ok

    http_response = MagicMock()
    http_response.status_code = 200
    http_response.iter_content.return_value = [b"data"]

    with (
        patch(f"{_MOD}.time.sleep"),
        patch(f"{_MOD}.requests.get", return_value=http_response),
    ):
        result = gen.generate()

    assert result.endswith(".mp4")
    assert (tmp_path / "videos").is_dir()


def test_generate_missing_prompt_file_raises(tmp_path):
    """generate() raises FileNotFoundError when the prompt file is missing."""
    gen, _ = _make_generator(tmp_path)
    image_path = _write_png(tmp_path / "img.png")

    with pytest.raises(FileNotFoundError, match="Prompt file not found"):
        gen.generate(image_path=image_path)


def test_generate_no_task_id_raises_runtime_error(tmp_path):
    """A create response without an id triggers a RuntimeError."""
    gen, client = _make_generator(tmp_path)
    image_path = _write_png(tmp_path / "img.png")

    client.image_to_video.create.return_value = MagicMock(id=None)

    with (
        patch(f"{_MOD}.time.sleep"),
        pytest.raises(RuntimeError, match="did not return a task id"),
    ):
        gen.generate(image_path=image_path, prompt_text="some prompt text")


def test_generate_failed_status_raises_runtime_error(tmp_path):
    """A FAILED task status raises a RuntimeError."""
    gen, client = _make_generator(tmp_path)
    image_path = _write_png(tmp_path / "img.png")

    client.image_to_video.create.return_value = MagicMock(id="t9")
    failed = MagicMock()
    failed.status = "FAILED"
    client.tasks.retrieve.return_value = failed

    with (
        patch(f"{_MOD}.time.sleep"),
        pytest.raises(RuntimeError, match="Video generation failed"),
    ):
        gen.generate(image_path=image_path, prompt_text="prompt body here")


def test_generate_polling_timeout_returns_empty(tmp_path):
    """Status never reaching a terminal state returns "" after max attempts."""
    gen, client = _make_generator(tmp_path)
    image_path = _write_png(tmp_path / "img.png")

    client.image_to_video.create.return_value = MagicMock(id="t-timeout")
    pending = MagicMock()
    pending.status = "RUNNING"
    client.tasks.retrieve.return_value = pending

    with (
        patch(f"{_MOD}.RUNWAY_MAX_POLL_ATTEMPTS", 3),
        patch(f"{_MOD}.time.sleep") as mock_sleep,
        patch(f"{_MOD}.requests.get") as mock_get,
    ):
        result = gen.generate(image_path=image_path, prompt_text="loop forever")

    assert result == ""
    assert client.tasks.retrieve.call_count == 3
    assert mock_sleep.call_count == 3
    mock_get.assert_not_called()


def test_generate_succeeded_but_no_output_raises(tmp_path):
    """SUCCEEDED with an empty output list raises a RuntimeError."""
    gen, client = _make_generator(tmp_path)
    image_path = _write_png(tmp_path / "img.png")

    client.image_to_video.create.return_value = MagicMock(id="t0")
    no_output = MagicMock()
    no_output.status = "SUCCEEDED"
    no_output.output = []
    client.tasks.retrieve.return_value = no_output

    with (
        patch(f"{_MOD}.time.sleep"),
        pytest.raises(RuntimeError, match="returned no output"),
    ):
        gen.generate(image_path=image_path, prompt_text="prompt content")


def test_download_video_non_200_raises_connection_error(tmp_path):
    """_download_video raises ConnectionError on a non-200 response."""
    gen, _ = _make_generator(tmp_path)
    gen.current_video_id = 4242

    bad_response = MagicMock()
    bad_response.status_code = 404

    with (
        patch(f"{_MOD}.requests.get", return_value=bad_response),
        pytest.raises(ConnectionError, match="status code = 404"),
    ):
        gen._download_video("http://x/missing.mp4")
