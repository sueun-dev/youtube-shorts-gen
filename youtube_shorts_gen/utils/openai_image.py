"""Shared utilities for generating images with OpenAI's DALL·E.

This module centralises the duplicated image-generation logic that previously
existed in three separate places. Use :func:`generate_image` instead of rolling
custom code.
"""
from __future__ import annotations

import base64
import logging
from pathlib import Path
from typing import TYPE_CHECKING

from youtube_shorts_gen.utils.config import (
    OPENAI_IMAGE_MODEL,
    OPENAI_IMAGE_QUALITY,
    OPENAI_IMAGE_SIZE,
)

if TYPE_CHECKING:  # pragma: no cover – only for type checking
    from openai import OpenAI


_ALLOWED_SIZES = {"1024x1024", "1792x1024", "1024x1792"}


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
        logging.info("Saved image: %s", output_path)
        return str(output_path)

    except Exception as exc:  # pylint: disable=broad-except
        logging.error("Image generation error: %s", exc)
        return ""
