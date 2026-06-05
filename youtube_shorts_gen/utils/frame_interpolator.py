"""Frame interpolation utility (stub implementation).

This is a stub implementation that doesn't require PyTorch.
It creates simple transition frames by blending the two input images.
"""

import logging
import os
from pathlib import Path

import cv2  # type: ignore
import numpy as np


def _blend_images(
    first_img: np.ndarray, second_img: np.ndarray, alpha: float
) -> np.ndarray:
    """Blend two images with the given alpha value (0.0 to 1.0).

    Args:
        first_img: First image (BGR format)
        second_img: Second image (BGR format)
        alpha: Blending factor (0.0 = first_img, 1.0 = second_img)

    Returns:
        Blended image
    """
    return cv2.addWeighted(first_img, 1 - alpha, second_img, alpha, 0)


def interpolate_between(
    img1_path: str | Path,
    img2_path: str | Path,
    num_inter_frames: int = 32,
    output_dir: str | Path | None = None,
) -> list[str]:
    """Generate *num_inter_frames* images between *img1* and *img2*.

    Returns list of output image paths (in order). If interpolation fails,
    returns empty list.

    Note: This is a stub implementation that creates simple blended transitions
    between images rather than using AI-based frame interpolation.
    """
    if num_inter_frames <= 0:
        return []

    if output_dir:
        output_dir_path = Path(output_dir)
    else:
        output_dir_path = Path(os.path.dirname(str(img1_path)))
    output_dir_path.mkdir(parents=True, exist_ok=True)

    first_img = cv2.imread(str(img1_path))
    second_img = cv2.imread(str(img2_path))

    if first_img is None or second_img is None:
        logging.error(
            "Could not read images for interpolation: %s, %s",
            img1_path,
            img2_path,
        )
        return []

    # Make sure images are the same size
    if first_img.shape != second_img.shape:
        # Resize the second image to match the first
        second_img = cv2.resize(second_img, (first_img.shape[1], first_img.shape[0]))

    outputs: list[str] = []
    for i in range(1, num_inter_frames + 1):
        # Calculate blending factor
        alpha = i / (num_inter_frames + 1)

        # Create blended frame
        frame = _blend_images(first_img, second_img, alpha)

        # Save the frame
        out_path = output_dir_path / f"interp_{Path(img1_path).stem}_{i}.png"
        if not cv2.imwrite(str(out_path), frame):
            logging.error("Failed to write interpolated frame: %s", out_path)
            continue
        outputs.append(str(out_path))

    return outputs
