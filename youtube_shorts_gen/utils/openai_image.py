"""Shared utilities for generating images with OpenAI's DALL·E.

This module centralises the duplicated image-generation logic that previously
existed in three separate places. Use :func:`generate_image` for single images or
:func:`generate_sequential_images` for naturally flowing image sequences.
"""
from __future__ import annotations

import base64
import logging
from pathlib import Path
import hashlib
import json
from typing import TYPE_CHECKING, List, Optional, Dict, Any

from youtube_shorts_gen.utils.config import (
    OPENAI_IMAGE_MODEL,
    OPENAI_IMAGE_QUALITY,
    OPENAI_IMAGE_SIZE,
)

if TYPE_CHECKING:  # pragma: no cover – only for type checking
    from openai import OpenAI


_ALLOWED_SIZES = {"1024x1024", "1792x1024", "1024x1792"}

# Simple on-disk cache directory for generated images
_CACHE_DIR = Path.home() / ".cache" / "youtube_shorts_gen" / "openai_images"
_CACHE_DIR.mkdir(parents=True, exist_ok=True)
_CACHE_INDEX_FILE = _CACHE_DIR / "index.json"

# Load existing index
if _CACHE_INDEX_FILE.exists():
    try:
        _CACHE_INDEX: Dict[str, str] = json.loads(_CACHE_INDEX_FILE.read_text())
    except json.JSONDecodeError:
        _CACHE_INDEX = {}
else:
    _CACHE_INDEX = {}

def _make_cache_key(prompt: str, size: str, quality: str, model: str) -> str:
    """Create a stable hash key for an image generation request."""
    return hashlib.sha256(f"{model}|{size}|{quality}|{prompt}".encode()).hexdigest()

def _get_cached_path(key: str) -> Optional[Path]:
    path_str = _CACHE_INDEX.get(key)
    if path_str:
        path = Path(path_str)
        if path.exists():
            return path
    return None

def _store_cache(key: str, image_path: Path) -> None:
    _CACHE_INDEX[key] = str(image_path)
    # Persist index to disk (best-effort)
    try:
        _CACHE_INDEX_FILE.write_text(json.dumps(_CACHE_INDEX))
    except Exception:  # pragma: no cover – caching should never crash
        pass


def _resolve_size() -> str:
    """Return a valid size string supported by DALL·E.

    Falls back to ``"1024x1024"`` if *OPENAI_IMAGE_SIZE* is unexpected.
    """
    if OPENAI_IMAGE_SIZE in _ALLOWED_SIZES:
        return OPENAI_IMAGE_SIZE

    logging.warning(
        "Unexpected OPENAI_IMAGE_SIZE %s – defaulting to 1024x1024",
        OPENAI_IMAGE_SIZE
    )
    return "1024x1024"


def generate_image(client: OpenAI, prompt: str, output_path: Path) -> str:
    """Generate an image using OpenAI's DALL·E and save it.

    Args:
        client: An initialised :class:`openai.OpenAI` client.
        prompt: Text prompt describing the desired image.
        output_path: Destination path (including filename).

    Returns
    -------
    str
        ``str`` path to the saved image on success, or ``""`` on failure.
    """
    try:
        # First check local cache
        cache_key = _make_cache_key(prompt, _resolve_size(), OPENAI_IMAGE_QUALITY, OPENAI_IMAGE_MODEL)
        cached = _get_cached_path(cache_key)
        if cached:
            logging.info("Cache hit for prompt – reusing %s", cached)
            output_path.write_bytes(cached.read_bytes())
            return str(output_path)

        response = client.images.generate(
            model=OPENAI_IMAGE_MODEL,
            prompt=prompt,
            size=_resolve_size(),
            quality=OPENAI_IMAGE_QUALITY,
            n=1,
        )

        if not response.data or not response.data[0].b64_json:
            logging.error("OpenAI API returned empty response for image generation")
            return ""

        image_data = response.data[0].b64_json
        output_path.write_bytes(base64.b64decode(image_data))
        # Save in cache for future reuse
        _store_cache(cache_key, output_path)
        logging.info("Saved image: %s", output_path)
        return str(output_path)

    except Exception as exc:  # pylint: disable=broad-except
        logging.error("Image generation error: %s", exc)
        return ""


def generate_sequential_images(
    client: OpenAI, prompts: List[str], output_paths: List[Path]
) -> List[str]:
    """Generate a sequence of images with visual continuity using OpenAI's multi-turn API.
    
    This function creates a series of images where each new image builds upon the previous one,
    resulting in a more natural flow when used in video creation.
    
    Args:
        client: An initialised :class:`openai.OpenAI` client.
        prompts: List of text prompts describing each desired image.
        output_paths: List of destination paths (including filenames).
        
    Returns:
        List of paths to saved images. Empty strings for any failed generations.
    """
    if not prompts or not output_paths or len(prompts) != len(output_paths):
        logging.error("Prompts and output_paths must be non-empty and of equal length")
        return [""] * len(output_paths) if output_paths else []
        
    image_paths = []
    previous_image_id: Optional[str] = None
    
    for i, (prompt, output_path) in enumerate(zip(prompts, output_paths)):
        try:
            # Use OpenAI multi-turn image generation (gpt-image-1) for frame-to-frame consistency
            cache_key = _make_cache_key(prompt, _resolve_size(), OPENAI_IMAGE_QUALITY, OPENAI_IMAGE_MODEL)
            cached_img_path = _get_cached_path(cache_key)
            if cached_img_path:
                logging.info("Cache hit for prompt – reusing %s", cached_img_path)
                output_path.write_bytes(cached_img_path.read_bytes())
                image_paths.append(str(output_path))
                previous_image_id = None  # Cannot pass ID; but style consistency via cache
                continue

            generate_kwargs: Dict[str, Any] = {
                "model": OPENAI_IMAGE_MODEL,
                "prompt": prompt,
                "size": _resolve_size(),
                "quality": OPENAI_IMAGE_QUALITY,
                "n": 1,
            }
            if previous_image_id:
                # Pass the previous image ID for multi-turn consistency
                generate_kwargs["previous_response"] = previous_image_id

            response = client.images.generate(**generate_kwargs)
            
            if not response.data or not response.data[0].b64_json:
                logging.error("OpenAI API returned empty response for image generation")
                image_paths.append("")
                continue
                
            # Save the image
            image_data = response.data[0].b64_json
            output_path.write_bytes(base64.b64decode(image_data))
            logging.info("Saved image: %s", output_path)
            image_paths.append(str(output_path))
            # store in cache
            _store_cache(cache_key, output_path)
            
            # Store the generated image's ID for the next turn (multi-turn)
            try:
                previous_image_id = response.data[0].id  # type: ignore[attr-defined]
            except (AttributeError, IndexError):
                previous_image_id = None
                
        except Exception as exc:
            logging.error("Sequential image generation error: %s", exc)
            image_paths.append("")
    
    return image_paths
