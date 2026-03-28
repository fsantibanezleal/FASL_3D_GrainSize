"""
Grain volume estimation from depth profiles for GrainSight.

Given a segmented depth map, each grain's 3D volume is estimated by
integrating the depth over its 2D footprint, after subtracting the
estimated base plane (the surface on which the grain rests).

Volume estimation model
-----------------------
For a single grain occupying pixel set :math:`\\Omega`:

.. math::

    V = \\sum_{(x,y)\\,\\in\\,\\Omega}
    \\bigl[z(x,y) - z_{\\text{base}}(x,y)\\bigr]\\;\\Delta x\\,\\Delta y

where :math:`z_{\\text{base}}` is the interpolated base surface beneath
the grain and :math:`\\Delta x, \\Delta y` are the pixel spacings.

Base plane estimation
---------------------
The base plane is estimated from a narrow band of pixels surrounding
the grain (dilated mask minus the grain itself).  A least-squares
planar fit is performed:

.. math::

    z_{\\text{base}}(x,y) = a\\,x + b\\,y + c

If fewer than three border pixels are available, a flat base at the
minimum surrounding depth is used instead.

Equivalent sphere diameter
--------------------------
Once the volume *V* is known, an equivalent-sphere diameter can be
computed:

.. math::

    d_{\\text{sphere}} = \\left(\\frac{6\\,V}{\\pi}\\right)^{1/3}

References
----------
* Thurley (2011). *Automated online measurement of limestone
  fragmentation using 3D range data*.
* Kim et al. (2003). *3D surface profile measurement of rock
  fragments and its application*.
"""

from __future__ import annotations

from typing import Dict, List

import numpy as np
from scipy import ndimage


def estimate_base_plane(
    depth: np.ndarray,
    label_mask: np.ndarray,
    dilate_iterations: int = 3,
) -> np.ndarray:
    """Estimate the base plane under a grain from surrounding pixels.

    The base surface is computed from a narrow band of pixels just
    outside the grain boundary.  If enough border pixels are available
    (>= 6), a planar fit :math:`z = ax + by + c` is used; otherwise, a
    flat plane at the median border depth is returned.

    Parameters
    ----------
    depth : ndarray (H, W), float
        Full depth map.
    label_mask : ndarray (H, W), bool
        Binary mask of the grain of interest.
    dilate_iterations : int
        Number of dilation iterations to grow the border band.

    Returns
    -------
    base_plane : ndarray (H, W), float
        Estimated base depth at every pixel (only meaningful inside
        the grain mask, but computed globally for convenience).
    """
    dilated = ndimage.binary_dilation(label_mask, iterations=dilate_iterations)
    border = dilated & (~label_mask) & (depth > 0)

    border_ys, border_xs = np.where(border)
    border_depths = depth[border]

    h, w = depth.shape

    if len(border_depths) < 6:
        # Fall back to flat plane at median border depth
        flat_val = float(np.median(border_depths)) if len(border_depths) > 0 else 0.0
        return np.full((h, w), flat_val, dtype=np.float64)

    # Least-squares planar fit: z = a*x + b*y + c
    A = np.column_stack([border_xs, border_ys, np.ones(len(border_xs))])
    coeffs, _, _, _ = np.linalg.lstsq(A, border_depths, rcond=None)
    a, b, c = coeffs

    yy, xx = np.mgrid[0:h, 0:w]
    base_plane = a * xx + b * yy + c
    return base_plane.astype(np.float64)


def estimate_grain_volume(
    depth: np.ndarray,
    label_mask: np.ndarray,
    pixel_size: float = 1.0,
) -> float:
    """Estimate the volume of a single grain from its depth profile.

    .. math::

        V = \\sum_{(x,y)\\in\\Omega}
        \\max\\bigl(0,\\; z(x,y) - z_{\\text{base}}(x,y)\\bigr)
        \\cdot p^2

    Parameters
    ----------
    depth : ndarray (H, W), float
        Full depth map.
    label_mask : ndarray (H, W), bool
        Binary mask of the grain.
    pixel_size : float
        Physical size of one pixel (mm/px).

    Returns
    -------
    volume : float
        Estimated grain volume in cubic length units.
    """
    base = estimate_base_plane(depth, label_mask)
    heights = np.maximum(0.0, depth[label_mask] - base[label_mask])
    return float(np.sum(heights)) * pixel_size ** 2


def estimate_all_volumes(
    depth: np.ndarray,
    labels: np.ndarray,
    pixel_size: float = 1.0,
) -> List[Dict]:
    """Estimate volumes for all grains in a label image.

    Parameters
    ----------
    depth : ndarray (H, W), float
    labels : ndarray (H, W), int32
        0 = background, 1..N = grain indices.
    pixel_size : float

    Returns
    -------
    volumes : list of dict
        Each dict has keys ``id``, ``volume``, ``equiv_sphere_diameter``.
    """
    unique = np.unique(labels)
    unique = unique[unique > 0]

    results: List[Dict] = []
    for lbl in unique:
        mask = labels == lbl
        vol = estimate_grain_volume(depth, mask, pixel_size)
        # Equivalent sphere diameter: d = (6V/pi)^(1/3)
        if vol > 0:
            d_sphere = (6.0 * vol / np.pi) ** (1.0 / 3.0)
        else:
            d_sphere = 0.0

        results.append({
            "id": int(lbl),
            "volume": round(vol, 4),
            "equiv_sphere_diameter": round(d_sphere, 4),
        })

    return results
