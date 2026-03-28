"""
Depth-based feature extraction for GrainSight.

Utilities for computing gradient magnitude, detecting grain peaks
(local maxima), and estimating surface roughness from a depth map.

These features serve two purposes:

1. **Segmentation support** -- grain peaks and depth edges feed into
   the watershed pipeline (see :mod:`segmentation`).
2. **Qualitative characterisation** -- local roughness distinguishes
   regions of fine vs. coarse material without explicit segmentation.

Gradient magnitude
------------------
.. math::

    |\\nabla z| = \\sqrt{\\left(\\frac{\\partial z}{\\partial x}\\right)^2
    + \\left(\\frac{\\partial z}{\\partial y}\\right)^2}

Computed via Sobel operators (3x3 kernel).

Local roughness
---------------
Within a sliding window of size :math:`w \\times w`:

.. math::

    \\sigma_z = \\sqrt{\\frac{1}{w^2} \\sum_{(i,j)\\in W}
    \\bigl(z_{i,j} - \\bar{z}_W\\bigr)^2}

High :math:`\\sigma_z` corresponds to coarse material (large grains
with pronounced peaks), while low :math:`\\sigma_z` indicates a smooth
or fine-grained surface.
"""

from __future__ import annotations

from typing import Tuple

import numpy as np
from scipy import ndimage
from skimage.feature import peak_local_max


def compute_depth_gradient(depth: np.ndarray) -> np.ndarray:
    """Gradient magnitude of the depth map.

    High values mark grain boundaries (depth discontinuities between
    adjacent grains or between a grain and the background).

    Parameters
    ----------
    depth : ndarray, shape (H, W), float
        Depth image.

    Returns
    -------
    grad_mag : ndarray, shape (H, W), float64
        Gradient magnitude at every pixel.
    """
    dz_dx = ndimage.sobel(depth.astype(np.float64), axis=1)
    dz_dy = ndimage.sobel(depth.astype(np.float64), axis=0)
    return np.hypot(dz_dx, dz_dy)


def detect_grain_peaks(
    depth: np.ndarray,
    min_distance: int = 5,
    threshold_rel: float = 0.3,
) -> np.ndarray:
    """Find local maxima in the depth map -- one peak per grain.

    Each grain's highest point is detected as a local maximum of the
    smoothed depth image.

    Parameters
    ----------
    depth : ndarray, shape (H, W), float
        Depth image.
    min_distance : int
        Minimum number of pixels between detected peaks.
    threshold_rel : float
        Minimum peak height as a fraction of the overall depth range.

    Returns
    -------
    peaks : ndarray, shape (N, 2)
        Row/column coordinates of detected peaks.
    """
    smoothed = ndimage.gaussian_filter(depth.astype(np.float64), sigma=1.5)
    coords = peak_local_max(
        smoothed,
        min_distance=max(min_distance, 1),
        threshold_rel=threshold_rel,
    )
    return coords


def compute_local_roughness(
    depth: np.ndarray,
    window_size: int = 5,
) -> np.ndarray:
    """Local surface roughness (standard deviation in a sliding window).

    Useful for qualitatively distinguishing fine vs. coarse material
    without explicit grain segmentation.

    Parameters
    ----------
    depth : ndarray, shape (H, W), float
        Depth image.
    window_size : int
        Side length of the square sliding window (must be odd).

    Returns
    -------
    roughness : ndarray, shape (H, W), float64
        Per-pixel roughness :math:`\\sigma_z`.
    """
    ws = max(window_size, 3) | 1  # ensure odd
    d = depth.astype(np.float64)

    # Local mean
    local_mean = ndimage.uniform_filter(d, size=ws)
    # Local mean of squares
    local_sq = ndimage.uniform_filter(d ** 2, size=ws)
    # Variance = E[X^2] - E[X]^2
    variance = np.maximum(0.0, local_sq - local_mean ** 2)

    return np.sqrt(variance)
