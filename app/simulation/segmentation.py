"""
Grain boundary detection and segmentation for GrainSight.

This module implements marker-based watershed segmentation specifically
designed for granular materials imaged by an RGB-D camera.  The depth
map is the primary input: grains appear as local peaks separated by
valleys (inter-grain gaps).

Algorithm overview
------------------
1. **Pre-processing** -- bilateral-like smoothing (Gaussian) to reduce
   sensor noise while preserving grain edges.

2. **Gradient computation** -- the depth gradient magnitude

   .. math::

       |\\nabla z| = \\sqrt{\\left(\\frac{\\partial z}{\\partial x}\\right)^2
       + \\left(\\frac{\\partial z}{\\partial y}\\right)^2}

   is high at grain boundaries (depth discontinuities).

3. **Marker detection** -- local maxima of the depth map (grain peaks)
   serve as foreground markers.  An h-minima transform identifies
   valleys as boundary markers.

4. **Watershed transform** -- the gradient magnitude is treated as a
   topographic surface; markers seed the basins; watershed flooding
   builds grain boundaries.

5. **Post-processing** -- small fragments are merged into neighbours,
   border-touching grains are optionally removed, and boundaries are
   refined using the RGB gradient when available.

References
----------
* Beucher & Lantuejoul (1979). *Use of watersheds in contour detection*.
* Meyer (1994). *Topographic distance and watershed lines*.
* Thurley & Ng (2008). *Identification and sizing of the entirely
  visible rocks from 3D surface data*.
"""

from __future__ import annotations

from typing import Optional, Tuple

import numpy as np
from scipy import ndimage
from skimage.feature import peak_local_max
from skimage.segmentation import watershed


# ------------------------------------------------------------------ #
# Helpers
# ------------------------------------------------------------------ #

def _smooth_depth(depth: np.ndarray, sigma: float = 1.5) -> np.ndarray:
    """Gaussian smoothing of the depth map to suppress sensor noise.

    Parameters
    ----------
    depth : ndarray (H, W)
        Raw depth image.
    sigma : float
        Standard deviation of the Gaussian kernel.

    Returns
    -------
    smoothed : ndarray (H, W)
    """
    return ndimage.gaussian_filter(depth.astype(np.float64), sigma=sigma)


def _depth_gradient(depth: np.ndarray) -> np.ndarray:
    """Compute gradient magnitude of the depth map.

    .. math::

        |\\nabla z| = \\sqrt{(dz/dx)^2 + (dz/dy)^2}

    Parameters
    ----------
    depth : ndarray (H, W)

    Returns
    -------
    grad_mag : ndarray (H, W)
    """
    dz_dx = ndimage.sobel(depth, axis=1)
    dz_dy = ndimage.sobel(depth, axis=0)
    return np.hypot(dz_dx, dz_dy)


# ------------------------------------------------------------------ #
# Main segmentation
# ------------------------------------------------------------------ #

def segment_grains_watershed(
    depth: np.ndarray,
    rgb: Optional[np.ndarray] = None,
    min_grain_size: int = 5,
    depth_threshold: Optional[float] = None,
    smooth_sigma: float = 1.5,
    min_distance: int = 5,
    peak_threshold_rel: float = 0.15,
) -> np.ndarray:
    """Segment individual grains using marker-based watershed.

    The algorithm follows the pipeline described in the module docstring:
    smooth -> gradient -> markers (local maxima) -> watershed -> clean.

    Parameters
    ----------
    depth : ndarray, shape (H, W), float
        Depth map.  Higher values = grain peaks.
    rgb : ndarray, shape (H, W, 3), uint8, optional
        Colour image.  If provided, its gradient is added to the depth
        gradient to improve boundary precision on colour boundaries.
    min_grain_size : int
        Grains with fewer pixels than this are merged into their
        largest neighbour.
    depth_threshold : float or None
        Minimum depth value to consider as foreground.  If *None*, the
        threshold is set automatically to ``0.1 * depth.max()``.
    smooth_sigma : float
        Gaussian smoothing sigma applied to the depth map.
    min_distance : int
        Minimum pixel distance between detected grain peaks.
    peak_threshold_rel : float
        Relative threshold (0--1) for ``peak_local_max``.

    Returns
    -------
    labels : ndarray, shape (H, W), int32
        Per-pixel grain labels.  ``0`` = background.
    """
    # 1. Pre-processing
    smoothed = _smooth_depth(depth, sigma=smooth_sigma)

    # 2. Foreground mask
    if depth_threshold is None:
        depth_threshold = 0.1 * smoothed.max() if smoothed.max() > 0 else 0.0
    fg_mask = smoothed > depth_threshold

    # 3. Gradient magnitude (landscape for watershed)
    grad = _depth_gradient(smoothed)

    # Optionally blend RGB gradient
    if rgb is not None and rgb.ndim == 3:
        gray = np.mean(rgb.astype(np.float64), axis=2)
        rgb_grad = _depth_gradient(gray)
        # Normalise both to [0, 1] and combine
        g_max = grad.max() or 1.0
        r_max = rgb_grad.max() or 1.0
        grad = 0.7 * (grad / g_max) + 0.3 * (rgb_grad / r_max)

    # 4. Detect markers (local maxima of the *inverted* gradient =
    #    peaks of depth which sit in gradient valleys).
    #    We use peak_local_max on the smoothed depth itself.
    coords = peak_local_max(
        smoothed,
        min_distance=max(min_distance, 1),
        threshold_rel=peak_threshold_rel,
        labels=fg_mask.astype(np.uint8),
    )

    if len(coords) == 0:
        return np.zeros(depth.shape, dtype=np.int32)

    markers = np.zeros(depth.shape, dtype=np.int32)
    for i, (r, c) in enumerate(coords, start=1):
        markers[r, c] = i

    # 5. Watershed
    labels = watershed(grad, markers=markers, mask=fg_mask)
    labels = labels.astype(np.int32)

    # 6. Post-processing: merge small fragments
    labels = _merge_small(labels, min_grain_size)

    return labels


def segment_grains_depth_edges(
    depth: np.ndarray,
    edge_threshold: float = 2.0,
    min_grain_size: int = 5,
) -> np.ndarray:
    """Simpler segmentation using depth discontinuities.

    Grains are separated by valleys (low depth) or sharp depth edges.
    The algorithm thresholds the gradient magnitude to find boundaries
    and labels connected foreground components.

    Parameters
    ----------
    depth : ndarray, shape (H, W), float
        Depth map.
    edge_threshold : float
        Gradient magnitude above this value is classified as a boundary.
    min_grain_size : int
        Remove components smaller than this.

    Returns
    -------
    labels : ndarray, shape (H, W), int32
    """
    smoothed = _smooth_depth(depth, sigma=1.0)
    grad = _depth_gradient(smoothed)

    boundary = grad > edge_threshold
    foreground = (smoothed > 0.1 * smoothed.max()) & (~boundary)

    labels, _ = ndimage.label(foreground)
    labels = _merge_small(labels.astype(np.int32), min_grain_size)

    return labels


# ------------------------------------------------------------------ #
# Small-fragment merging
# ------------------------------------------------------------------ #

def _merge_small(labels: np.ndarray, min_size: int) -> np.ndarray:
    """Merge small labelled regions into their largest neighbour.

    For each region smaller than *min_size* pixels, the region is
    reassigned to whichever neighbouring label occupies the most pixels
    along its boundary.  If no neighbour exists, the region becomes
    background (0).

    Parameters
    ----------
    labels : ndarray (H, W), int32
    min_size : int

    Returns
    -------
    labels : ndarray (H, W), int32  (modified in-place)
    """
    unique, counts = np.unique(labels, return_counts=True)
    small = unique[(counts < min_size) & (unique > 0)]

    if len(small) == 0:
        return labels

    for s in small:
        mask = labels == s
        dilated = ndimage.binary_dilation(mask, iterations=1)
        border = dilated & (~mask)
        neighbours = labels[border]
        neighbours = neighbours[neighbours > 0]
        if len(neighbours) > 0:
            vals, cts = np.unique(neighbours, return_counts=True)
            labels[mask] = vals[np.argmax(cts)]
        else:
            labels[mask] = 0

    # Re-number to be contiguous
    unique_new = np.unique(labels)
    unique_new = unique_new[unique_new > 0]
    remap = np.zeros(labels.max() + 1, dtype=np.int32)
    for new_id, old_id in enumerate(unique_new, start=1):
        remap[old_id] = new_id
    remap[0] = 0
    labels = remap[labels]

    return labels
