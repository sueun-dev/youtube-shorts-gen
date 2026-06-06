"""Tests for youtube_shorts_gen.utils.openai_image.

Covers the cache MISS path (writes file, returns path, calls the client), the
empty-response path (returns ""), a forced cache HIT (reuses bytes without
calling the client), and generate_sequential_images alignment / failure paths.

All file I/O uses tmp_path and the module-level on-disk cache is isolated by
monkeypatching _CACHE_INDEX and _CACHE_INDEX_FILE to fresh, temporary values.
"""

import base64
from unittest.mock import MagicMock

import pytest

from youtube_shorts_gen.utils import openai_image

# A valid 1x1 transparent PNG encoded as base64.
PNG_B64 = (
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z"
    "8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg=="
)


@pytest.fixture(autouse=True)
def isolate_cache(monkeypatch, tmp_path):
    """Give every test a fresh, on-disk cache index in a temp location."""
    monkeypatch.setattr(openai_image, "_CACHE_INDEX", {})
    monkeypatch.setattr(
        openai_image, "_CACHE_INDEX_FILE", tmp_path / "index.json"
    )


def _make_client(b64=PNG_B64, empty=False):
    """Build a MagicMock OpenAI client for images.generate."""
    client = MagicMock()
    if empty:
        client.images.generate.return_value.data = []
    else:
        datum = MagicMock()
        datum.b64_json = b64
        client.images.generate.return_value.data = [datum]
    return client


def test_generate_image_cache_miss_writes_file(tmp_path):
    """A cache miss writes the decoded bytes and returns the output path."""
    client = _make_client()
    out = tmp_path / "img.png"

    result = openai_image.generate_image(client, "a prompt", out)

    assert result == str(out)
    assert out.exists()
    assert out.read_bytes() == base64.b64decode(PNG_B64)
    client.images.generate.assert_called_once()


def test_generate_image_populates_cache_index(tmp_path):
    """A successful generation records the path in the cache index + file."""
    client = _make_client()
    out = tmp_path / "img.png"

    openai_image.generate_image(client, "another prompt", out)

    assert str(out) in openai_image._CACHE_INDEX.values()
    assert openai_image._CACHE_INDEX_FILE.exists()


def test_generate_image_empty_response_returns_empty(tmp_path):
    """An empty data list yields "" and writes nothing."""
    client = _make_client(empty=True)
    out = tmp_path / "img.png"

    result = openai_image.generate_image(client, "prompt", out)

    assert result == ""
    assert not out.exists()


def test_generate_image_blank_b64_returns_empty(tmp_path):
    """A datum with falsy b64_json yields "" (treated as empty)."""
    client = _make_client(b64="")
    out = tmp_path / "img.png"

    result = openai_image.generate_image(client, "prompt", out)

    assert result == ""
    assert not out.exists()


def test_generate_image_cache_hit_skips_client(tmp_path, monkeypatch):
    """A forced cache hit reuses bytes without calling images.generate."""
    cached = tmp_path / "cached.png"
    cached_bytes = base64.b64decode(PNG_B64)
    cached.write_bytes(cached_bytes)

    monkeypatch.setattr(
        openai_image, "_get_cached_path", lambda key: cached
    )

    client = _make_client()
    out = tmp_path / "out.png"
    result = openai_image.generate_image(client, "prompt", out)

    assert result == str(out)
    assert out.read_bytes() == cached_bytes
    client.images.generate.assert_not_called()


def test_generate_image_error_path_returns_empty(tmp_path):
    """An OSError during generation is caught and "" is returned."""
    client = MagicMock()
    client.images.generate.side_effect = OSError("disk full")
    out = tmp_path / "img.png"

    result = openai_image.generate_image(client, "prompt", out)

    assert result == ""
    assert not out.exists()


def test_generate_image_unexpected_error_returns_empty(tmp_path):
    """A non-(OSError, ValueError) exception is also swallowed -> ""."""
    client = MagicMock()
    client.images.generate.side_effect = RuntimeError("boom")
    out = tmp_path / "img.png"

    result = openai_image.generate_image(client, "prompt", out)

    assert result == ""
    assert not out.exists()


def test_generate_sequential_images_happy_path(tmp_path):
    """Each prompt produces an aligned output path."""
    client = _make_client()
    prompts = ["p1", "p2"]
    outs = [tmp_path / "a.png", tmp_path / "b.png"]

    results = openai_image.generate_sequential_images(client, prompts, outs)

    assert results == [str(outs[0]), str(outs[1])]
    assert all(p.exists() for p in outs)
    assert client.images.generate.call_count == 2


def test_generate_sequential_images_mismatched_lengths(tmp_path):
    """Length mismatch returns "" entries sized to output_paths."""
    client = _make_client()
    outs = [tmp_path / "a.png", tmp_path / "b.png", tmp_path / "c.png"]

    results = openai_image.generate_sequential_images(client, ["only"], outs)

    assert results == ["", "", ""]
    client.images.generate.assert_not_called()


def test_generate_sequential_images_empty_prompts(tmp_path):
    """Empty prompts returns a list of "" matching output_paths length."""
    client = _make_client()
    outs = [tmp_path / "a.png"]

    results = openai_image.generate_sequential_images(client, [], outs)

    assert results == [""]
    client.images.generate.assert_not_called()


def test_generate_sequential_images_partial_failure(tmp_path):
    """A per-item failure yields "" in that position while others succeed."""
    client = MagicMock()
    good = MagicMock()
    good.b64_json = PNG_B64
    ok_resp = MagicMock()
    ok_resp.data = [good]
    client.images.generate.side_effect = [ok_resp, OSError("fail")]

    prompts = ["p1", "p2"]
    outs = [tmp_path / "a.png", tmp_path / "b.png"]

    results = openai_image.generate_sequential_images(client, prompts, outs)

    assert results == [str(outs[0]), ""]
    assert outs[0].exists()
    assert not outs[1].exists()


def test_cache_key_is_stable_and_prompt_sensitive():
    """_make_cache_key is deterministic and varies with the prompt."""
    k1 = openai_image._make_cache_key("p", "1024x1024", "medium", "m")
    k2 = openai_image._make_cache_key("p", "1024x1024", "medium", "m")
    k3 = openai_image._make_cache_key("other", "1024x1024", "medium", "m")

    assert k1 == k2
    assert k1 != k3


def test_get_cached_path_missing_file_returns_none(tmp_path, monkeypatch):
    """_get_cached_path returns None when the recorded path is gone."""
    monkeypatch.setattr(
        openai_image,
        "_CACHE_INDEX",
        {"key": str(tmp_path / "nonexistent.png")},
    )

    assert openai_image._get_cached_path("key") is None


def test_store_cache_persists_index(tmp_path, monkeypatch):
    """_store_cache writes the index file with the new entry."""
    index_file = tmp_path / "index.json"
    monkeypatch.setattr(openai_image, "_CACHE_INDEX_FILE", index_file)
    monkeypatch.setattr(openai_image, "_CACHE_INDEX", {})

    img = tmp_path / "img.png"
    openai_image._store_cache("k", img)

    assert index_file.exists()
    assert str(img) in index_file.read_text()
    assert openai_image._CACHE_INDEX["k"] == str(img)


def test_full_cache_roundtrip_second_call_reuses(tmp_path):
    """First call generates; an aligned second call reuses without the API."""
    client = _make_client()
    out1 = tmp_path / "first.png"
    out2 = tmp_path / "second.png"

    first = openai_image.generate_image(client, "same prompt", out1)
    assert first == str(out1)
    assert client.images.generate.call_count == 1

    # Same prompt -> cache hit; client should not be called again.
    second = openai_image.generate_image(client, "same prompt", out2)
    assert second == str(out2)
    assert out2.read_bytes() == out1.read_bytes()
    assert client.images.generate.call_count == 1
