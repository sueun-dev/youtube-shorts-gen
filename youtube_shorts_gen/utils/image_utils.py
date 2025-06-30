"""Utility functions for basic image manipulations used across the project."""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Sequence

from PIL import Image, ImageDraw, ImageFont


def _load_font(size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:  # type: ignore[name-defined]
    """Attempt to load a TrueType font; fall back to default if not found."""
    font_candidates = [
        "DejaVuSans-Bold.ttf",  # Linux / many Pillow installations
        "/Library/Fonts/Arial Bold.ttf",  # macOS common path
        "/System/Library/Fonts/Supplemental/Arial Bold.ttf",  # macOS supplemental
        "Arial.ttf",  # Windows / generic
    ]
    for candidate in font_candidates:
        try:
            return ImageFont.truetype(candidate, size)
        except Exception:
            continue
    # Fallback (size will be fixed and small)
    return ImageFont.load_default()


# Default font size acts as fallback; actual size will be computed per-image
DEFAULT_FONT_SIZE = 200


def overlay_text_on_images(image_paths: Sequence[str], texts: Sequence[str], output_dir: Path, font_size: int = DEFAULT_FONT_SIZE) -> list[str]:
    """Overlay given text on each image and save to *output_dir*.

    Args:
        image_paths: Paths to source images.
        texts: Text to overlay on each corresponding image.
        output_dir: Directory to store modified images.
        font_size: Font size for the text.

    Returns:
        List of paths to the images with text overlay.
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    result_paths: list[str] = []

    # Use a default font (Pillow built-in) to avoid external dependencies
    # Load font with fallback logic
    # Font will be loaded later per-image after computing appropriate size
    base_font_path = None
    for cand in [
        "DejaVuSans-Bold.ttf",
        "/Library/Fonts/Arial Bold.ttf",
        "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
        "Arial.ttf",
    ]:
        try:
            ImageFont.truetype(cand, 10)
            base_font_path = cand
            break
        except Exception:
            continue

    for img_path, text in zip(image_paths, texts):
        try:
            with Image.open(img_path).convert("RGBA") as im:
                draw = ImageDraw.Draw(im)
                # Dynamically compute font size: ~13% of image width
                dynamic_font_size = max(10, int(im.width * 0.13))
                font = ImageFont.truetype(base_font_path, dynamic_font_size) if base_font_path else _load_font(dynamic_font_size)
                stroke_width = max(2, dynamic_font_size // 20)
                # Pillow 10 removed textsize; use textbbox for accurate dimensions
                # If default font (fixed small size), dynamically increase font using heuristic
                if isinstance(font, ImageFont.ImageFont) and font == ImageFont.load_default():
                    # Basic heuristic to scale using multiple draws
                    scale_factor = font_size // 10  # crude scaling
                    text_scaled = " ".join(list(text)) * scale_factor  # widen artificially
                bbox = draw.textbbox((0, 0), text, font=font)
                text_width = bbox[2] - bbox[0]
                text_height = bbox[3] - bbox[1]
                x = (im.width - text_width) // 2
                y = 20  # padding from top
                # Draw the main text in white with no background
                # Use a very thick white outline to make text stand out

                # Draw text outline/stroke in white for better visibility
                for offset_x in range(-stroke_width, stroke_width + 1):
                    for offset_y in range(-stroke_width, stroke_width + 1):
                        if offset_x != 0 or offset_y != 0:
                            draw.text((x + offset_x, y + offset_y), text, font=font, fill=(255, 255, 255, 255))
                # Draw the main text in bright yellow for contrast
                draw.text((x, y), text, font=font, fill=(255, 255, 0, 255))

                out_path = output_dir / Path(img_path).name
                im.convert("RGB").save(out_path)
                result_paths.append(str(out_path))
        except Exception as e:
            logging.error("Failed to overlay text on %s: %s", img_path, e)
            result_paths.append(img_path)  # fallback to original if failure

    return result_paths
