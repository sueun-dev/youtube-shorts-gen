"""Utility functions for basic image manipulations used across the project."""

import logging
from collections.abc import Sequence
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

# Default font size acts as fallback; actual size is computed per-image.
DEFAULT_FONT_SIZE = 200


def _load_font(size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
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
        except OSError:
            continue
    # Fallback (size will be fixed and small)
    return ImageFont.load_default()


def overlay_text_on_images(
    image_paths: Sequence[str],
    texts: Sequence[str],
    output_dir: Path,
    font_size: int = DEFAULT_FONT_SIZE,
) -> list[str]:
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

    for img_path, text in zip(image_paths, texts, strict=False):
        try:
            with Image.open(img_path).convert("RGBA") as im:
                draw = ImageDraw.Draw(im)
                # Dynamically compute font size: ~13% of image width
                dynamic_font_size = max(10, int(im.width * 0.13))
                font = _load_font(dynamic_font_size)
                stroke_width = max(2, dynamic_font_size // 20)
                # Pillow 10 removed textsize; use textbbox for dimensions.
                bbox = draw.textbbox((0, 0), text, font=font)
                text_width = bbox[2] - bbox[0]
                x = (im.width - text_width) // 2
                y = 20  # padding from top

                # Draw text outline/stroke in white for visibility.
                for offset_x in range(-stroke_width, stroke_width + 1):
                    for offset_y in range(-stroke_width, stroke_width + 1):
                        if offset_x != 0 or offset_y != 0:
                            draw.text(
                                (x + offset_x, y + offset_y),
                                text,
                                font=font,
                                fill=(255, 255, 255, 255),
                            )
                # Draw the main text in bright yellow for contrast.
                draw.text((x, y), text, font=font, fill=(255, 255, 0, 255))

                out_path = output_dir / Path(img_path).name
                im.convert("RGB").save(out_path)
                result_paths.append(str(out_path))
        except (OSError, ValueError):
            logging.exception("Failed to overlay text on %s", img_path)
            result_paths.append(img_path)  # fallback to original on failure

    return result_paths
