"""Shared helpers for generating images with OpenAI's image API.

Provides a single entry point for image generation with a small on-disk cache so
repeated prompts do not incur duplicate API calls. Use :func:`generate_image`
for a single image or :func:`generate_sequential_images` for a batch.
"""

from __future__ import annotations

import base64
import hashlib
import json
import logging
from pathlib import Path
from typing import TYPE_CHECKING, Any

from youtube_shorts_gen.utils.config import (
    IMAGE_SIZES,
    OPENAI_IMAGE_MODEL,
    OPENAI_IMAGE_QUALITY,
    OPENAI_IMAGE_SIZE,
)

if TYPE_CHECKING:
    from openai import OpenAI

# On-disk cache so identical prompts reuse a previously generated image.
_CACHE_DIR = Path.home() / ".cache" / "youtube_shorts_gen" / "openai_images"
_CACHE_INDEX_FILE = _CACHE_DIR / "index.json"


def _load_cache_index() -> dict[str, str]:
    """Load the cache index from disk, returning an empty index on any error."""
    if not _CACHE_INDEX_FILE.exists():
        return {}
    try:
        return json.loads(_CACHE_INDEX_FILE.read_text())
    except (json.JSONDecodeError, OSError) as exc:
        logging.warning("Could not read image cache index; starting fresh: %s", exc)
        return {}


_CACHE_DIR.mkdir(parents=True, exist_ok=True)
_CACHE_INDEX: dict[str, str] = _load_cache_index()


def _make_cache_key(prompt: str, size: str, quality: str, model: str) -> str:
    """Create a stable hash key for an image-generation request."""
    return hashlib.sha256(f"{model}|{size}|{quality}|{prompt}".encode()).hexdigest()


def _get_cached_path(key: str) -> Path | None:
    """Return the cached image path for ``key`` if it still exists on disk."""
    path_str = _CACHE_INDEX.get(key)
    if path_str:
        path = Path(path_str)
        if path.exists():
            return path
    return None


def _store_cache(key: str, image_path: Path) -> None:
    """Record ``image_path`` for ``key`` and persist the index (best-effort)."""
    _CACHE_INDEX[key] = str(image_path)
    try:
        _CACHE_INDEX_FILE.write_text(json.dumps(_CACHE_INDEX))
    except OSError as exc:
        logging.warning("Could not persist image cache index: %s", exc)


def _resolve_size() -> str:
    """Return a size string supported by the image API, defaulting to 1024x1024."""
    if OPENAI_IMAGE_SIZE in IMAGE_SIZES:
        return OPENAI_IMAGE_SIZE
    logging.warning(
        "Unexpected OPENAI_IMAGE_SIZE %s - defaulting to 1024x1024", OPENAI_IMAGE_SIZE
    )
    return "1024x1024"


def _generate_one(client: OpenAI, prompt: str, output_path: Path) -> str:
    """Generate a single image, using the cache when possible.

    Returns the saved image path as a string, or ``""`` on failure.
    """
    cache_key = _make_cache_key(
        prompt, _resolve_size(), OPENAI_IMAGE_QUALITY, OPENAI_IMAGE_MODEL
    )
    cached = _get_cached_path(cache_key)
    if cached:
        logging.info("Image cache hit - reusing %s", cached)
        output_path.write_bytes(cached.read_bytes())
        return str(output_path)

    params: dict[str, Any] = {
        "model": OPENAI_IMAGE_MODEL,
        "prompt": prompt,
        "size": _resolve_size(),
        "quality": OPENAI_IMAGE_QUALITY,
        "n": 1,
    }
    response = client.images.generate(**params)

    if not response.data or not response.data[0].b64_json:
        logging.error("OpenAI returned an empty response for image generation")
        return ""

    output_path.write_bytes(base64.b64decode(response.data[0].b64_json))
    _store_cache(cache_key, output_path)
    logging.info("Saved image: %s", output_path)
    return str(output_path)


def generate_image(client: OpenAI, prompt: str, output_path: Path) -> str:
    """Generate an image from ``prompt`` and save it to ``output_path``.

    Args:
        client: An initialised OpenAI client.
        prompt: Text prompt describing the desired image.
        output_path: Destination path (including filename).

    Returns:
        The saved image path as a string, or ``""`` on failure.
    """
    try:
        return _generate_one(client, prompt, output_path)
    except (OSError, ValueError) as exc:
        logging.error("Image generation error: %s", exc)
        return ""
    except Exception:
        logging.exception("Unexpected error during image generation")
        return ""


def generate_sequential_images(
    client: OpenAI, prompts: list[str], output_paths: list[Path]
) -> list[str]:
    """Generate one image per prompt, saving each to the matching output path.

    Args:
        client: An initialised OpenAI client.
        prompts: Text prompts describing each desired image.
        output_paths: Destination paths (including filenames), aligned with
            ``prompts``.

    Returns:
        A list of saved image paths, with ``""`` in any position that failed.
    """
    if not prompts or len(prompts) != len(output_paths):
        logging.error("prompts and output_paths must be non-empty and equal length")
        return [""] * len(output_paths)

    return [
        generate_image(client, prompt, output_path)
        for prompt, output_path in zip(prompts, output_paths, strict=True)
    ]
