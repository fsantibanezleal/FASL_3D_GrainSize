"""
Per-grain geometric measurement for GrainSight.

Given a label image and its associated depth map, this module extracts
a comprehensive set of geometric and morphological descriptors for every
segmented grain.

Measured properties
-------------------
For each grain *i* (connected component where ``labels == i``):

* **Area** (pixels and physical units):
  :math:`A = N_{\\text{pixels}} \\cdot p^2` where *p* is the pixel size.

* **Perimeter** -- contour length computed from the boundary pixels.

* **Bounding box** -- axis-aligned rectangle ``(x, y, w, h)``.

* **Equivalent circular diameter**:

  .. math:: d_{\\text{eq}} = 2\\,\\sqrt{\\frac{A}{\\pi}}

* **Major / minor axis lengths** -- eigenvalues of the 2D inertia
  tensor (PCA of pixel coordinates).

* **Aspect ratio**: ``major / minor``.

* **Orientation** (degrees) -- angle of the major axis.

* **Circularity** (Haralick):

  .. math:: C = \\frac{4\\,\\pi\\,A}{P^2}

  where *P* is the perimeter.  A perfect circle gives *C* = 1.

* **Mean depth** and depth range within the grain footprint.

* **Estimated volume** -- integral of depth over the grain area:

  .. math:: V = \\sum_{(x,y)\\in\\text{grain}}
             \\bigl(z(x,y) - z_{\\text{base}}\\bigr)\\,p^2

References
----------
* ISO 13322-1:2014 *Particle size analysis -- Image analysis methods*.
* Mora & Kwan (2000). *Sphericity, shape factor and convexity
  measurement of coarse aggregate*.
"""

from __future__ import annotations

import math
from typing import Dict, List

import numpy as np
from scipy import ndimage


def measure_grains(
    labels: np.ndarray,
    depth: np.ndarray,
    pixel_size: float = 1.0,
) -> List[Dict]:
    """Measure geometric properties of each segmented grain.

    Parameters
    ----------
    labels : ndarray, shape (H, W), int32
        Per-pixel grain label image (0 = background).
    depth : ndarray, shape (H, W), float
        Depth map aligned with ``labels``.
    pixel_size : float
        Physical size of one pixel (e.g. mm/px).  All length and area
        measurements are scaled by this factor.

    Returns
    -------
    grains : list of dict
        One dictionary per grain, ordered by label index.  Keys:

        ``id``, ``area_px``, ``area_mm2``, ``perimeter_px``,
        ``bbox_x``, ``bbox_y``, ``bbox_w``, ``bbox_h``,
        ``equiv_diameter``, ``major_axis``, ``minor_axis``,
        ``aspect_ratio``, ``orientation_deg``, ``circularity``,
        ``mean_depth``, ``depth_range``, ``volume``,
        ``centroid_x``, ``centroid_y``.
    """
    unique_labels = np.unique(labels)
    unique_labels = unique_labels[unique_labels > 0]

    results: List[Dict] = []

    for lbl in unique_labels:
        mask = labels == lbl
        ys, xs = np.where(mask)

        if len(xs) < 2:
            continue

        area_px = int(len(xs))
        area_mm2 = float(area_px * pixel_size ** 2)

        # Centroid
        cx = float(np.mean(xs))
        cy = float(np.mean(ys))

        # Bounding box
        bx, by = int(xs.min()), int(ys.min())
        bw, bh = int(xs.max() - bx + 1), int(ys.max() - by + 1)

        # Equivalent circular diameter: d = 2*sqrt(A / pi)
        equiv_d = 2.0 * math.sqrt(area_mm2 / math.pi) if area_mm2 > 0 else 0.0

        # Perimeter (boundary length via erosion)
        eroded = ndimage.binary_erosion(mask)
        perimeter_px = float(np.sum(mask & ~eroded))

        # Circularity: 4*pi*A / P^2
        circularity = (
            (4.0 * math.pi * area_px) / (perimeter_px ** 2)
            if perimeter_px > 0
            else 0.0
        )

        # PCA for major/minor axes
        coords = np.column_stack([xs - cx, ys - cy]).astype(np.float64)
        cov = np.cov(coords, rowvar=False)
        eigenvalues = np.linalg.eigvalsh(cov)
        eigenvalues = np.sort(eigenvalues)[::-1]
        major = 4.0 * math.sqrt(max(eigenvalues[0], 0)) * pixel_size
        minor = 4.0 * math.sqrt(max(eigenvalues[1], 0)) * pixel_size if len(eigenvalues) > 1 else major

        aspect = major / minor if minor > 0 else 1.0

        # Orientation from eigenvectors
        eigvecs = np.linalg.eigh(cov)[1]
        angle_rad = math.atan2(eigvecs[1, -1], eigvecs[0, -1])
        orientation_deg = math.degrees(angle_rad) % 180.0

        # Depth statistics
        depths_in_grain = depth[mask]
        mean_depth = float(np.mean(depths_in_grain))
        depth_range_val = float(np.ptp(depths_in_grain))

        # Volume estimation: sum (z - z_base) * pixel_size^2
        # z_base = minimum depth within the grain (approximation)
        z_base = float(np.min(depths_in_grain))
        volume = float(np.sum(depths_in_grain - z_base)) * pixel_size ** 2

        results.append({
            "id": int(lbl),
            "area_px": area_px,
            "area_mm2": round(area_mm2, 3),
            "perimeter_px": round(perimeter_px, 1),
            "bbox_x": bx,
            "bbox_y": by,
            "bbox_w": bw,
            "bbox_h": bh,
            "equiv_diameter": round(equiv_d, 3),
            "major_axis": round(major, 3),
            "minor_axis": round(minor, 3),
            "aspect_ratio": round(aspect, 3),
            "orientation_deg": round(orientation_deg, 1),
            "circularity": round(circularity, 4),
            "mean_depth": round(mean_depth, 3),
            "depth_range": round(depth_range_val, 3),
            "volume": round(volume, 3),
            "centroid_x": round(cx, 1),
            "centroid_y": round(cy, 1),
        })

    return results
