"""Frame interpolation utility (stub implementation).

This is a stub implementation that doesn't require PyTorch.
It creates simple transition frames by blending the two input images.
"""
from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import List

import cv2  # type: ignore
import numpy as np


# Simple helper functions for the stub implementation
def _blend_images(img1: np.ndarray, img2: np.ndarray, alpha: float) -> np.ndarray:
    """Blend two images with the given alpha value (0.0 to 1.0).
    
    Args:
        img1: First image (BGR format)
        img2: Second image (BGR format)
        alpha: Blending factor (0.0 = img1, 1.0 = img2)
        
    Returns:
        Blended image
    """
    return cv2.addWeighted(img1, 1 - alpha, img2, alpha, 0)


def interpolate_between(
    img1_path: str | Path,
    img2_path: str | Path,
    num_inter_frames: int = 32,
    output_dir: str | Path | None = None,
) -> List[str]:
    """Generate *num_inter_frames* images between *img1* and *img2*.

    Returns list of output image paths (in order). If interpolation fails,
    returns empty list.
    
    Note: This is a stub implementation that creates simple blended transitions
    between images rather than using AI-based frame interpolation.
    """
    if num_inter_frames <= 0:
        return []

    output_dir_path = Path(output_dir) if output_dir else Path(os.path.dirname(str(img1_path)))
    output_dir_path.mkdir(parents=True, exist_ok=True)

    img0 = cv2.imread(str(img1_path))
    img1 = cv2.imread(str(img2_path))

    if img0 is None or img1 is None:
        logging.error("Could not read images for interpolation: %s, %s", img1_path, img2_path)
        return []
        
    # Make sure images are the same size
    if img0.shape != img1.shape:
        # Resize the second image to match the first
        img1 = cv2.resize(img1, (img0.shape[1], img0.shape[0]))

    outputs: List[str] = []
    for i in range(1, num_inter_frames + 1):
        # Calculate blending factor
        alpha = i / (num_inter_frames + 1)
        
        # Create blended frame
        frame = _blend_images(img0, img1, alpha)
        
        # Save the frame
        out_path = output_dir_path / f"interp_{Path(img1_path).stem}_{i}.png"
        cv2.imwrite(str(out_path), frame)
        outputs.append(str(out_path))
        
    return outputs
