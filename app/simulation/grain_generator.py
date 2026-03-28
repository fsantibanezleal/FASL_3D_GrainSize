"""
Synthetic 3D grain bed generation for GrainSight.

This module generates realistic RGB-D images of granular beds (rock
fragments, crushed ore, sediment) as they would appear from an overhead
RGB-D camera looking down at a conveyor belt, stockpile, or muck pile.

Each grain is modelled as a 3D ellipsoid projected onto the image plane.
The module supports several Particle Size Distributions commonly
encountered in mineral processing and geotechnical engineering:

    * **Uniform** -- equal-sized grains (testing baseline).
    * **Normal** -- Gaussian :math:`d \\sim \\mathcal{N}(\\mu, \\sigma^2)`.
    * **Log-normal** -- :math:`\\ln d \\sim \\mathcal{N}(\\mu, \\sigma^2)`,
      typical of crushed rock.
    * **Bimodal** -- two overlapping populations (coarse + fines).
    * **Rosin-Rammler** -- :math:`R(x)=1-\\exp\\!\\bigl(-(x/x_0)^n\\bigr)`,
      standard model for blast fragmentation.

Depth profiles
--------------
For each grain the depth map records an ellipsoidal surface whose peak
sits at the grain centre:

.. math::

    z(x,y) = z_{\\text{peak}} \\cdot
    \\sqrt{\\max\\!\\Bigl(0,\\;
    1 - \\frac{(x-x_c)^2}{a^2} - \\frac{(y-y_c)^2}{b^2}\\Bigr)}

where *a*, *b* are the semi-axes and :math:`z_{\\text{peak}}` is drawn
from ``depth_range``.

References
----------
* Rosin & Rammler (1933). *J. Inst. Fuel*, 7, 29--36.
* Maerz & Zhou (1998). *WipFrag image-based granulometry system*.
* Thurley (2011). *Automated online measurement of limestone
  fragmentation using 3D range data*.
"""

from __future__ import annotations

import math
from typing import List, Literal, Optional, Tuple

import numpy as np

# ------------------------------------------------------------------ #
# Public type alias
# ------------------------------------------------------------------ #
BedType = Literal["uniform", "normal", "lognormal", "bimodal", "rosin_rammler"]


# ------------------------------------------------------------------ #
# Size distribution samplers
# ------------------------------------------------------------------ #

def _sample_diameters(
    rng: np.random.Generator,
    n: int,
    bed_type: BedType,
    mean_d: float,
    std_d: float,
) -> np.ndarray:
    """Return *n* positive grain diameters drawn from the requested PSD.

    Parameters
    ----------
    rng : numpy.random.Generator
        Seeded random number generator.
    n : int
        Number of grains.
    bed_type : BedType
        Distribution family (see module docstring).
    mean_d, std_d : float
        Mean and standard deviation of the diameter distribution.
        For Rosin-Rammler, *mean_d* is the characteristic size x0 and
        *std_d* encodes the uniformity index n (clamped to >= 0.5).

    Returns
    -------
    diameters : ndarray, shape (n,)
        Positive grain diameters.
    """
    if bed_type == "uniform":
        diameters = np.full(n, mean_d)

    elif bed_type == "normal":
        diameters = rng.normal(mean_d, max(std_d, 1e-6), size=n)

    elif bed_type == "lognormal":
        # Convert mean/std of diameter to underlying normal parameters.
        var = max(std_d, 1e-6) ** 2
        mu_ln = math.log(mean_d ** 2 / math.sqrt(var + mean_d ** 2))
        sigma_ln = math.sqrt(math.log(1 + var / mean_d ** 2))
        diameters = rng.lognormal(mu_ln, sigma_ln, size=n)

    elif bed_type == "bimodal":
        # Two Gaussian populations: 60 % coarse, 40 % fines
        n_coarse = int(0.6 * n)
        n_fines = n - n_coarse
        coarse = rng.normal(mean_d * 1.5, std_d, size=n_coarse)
        fines = rng.normal(mean_d * 0.5, std_d * 0.5, size=n_fines)
        diameters = np.concatenate([coarse, fines])
        rng.shuffle(diameters)

    elif bed_type == "rosin_rammler":
        # Inverse-CDF sampling: d = x0 * (-ln(1 - U))^(1/n)
        x0 = mean_d
        n_rr = max(std_d, 0.5)  # uniformity index
        u = rng.uniform(0.001, 0.999, size=n)
        diameters = x0 * (-np.log(1.0 - u)) ** (1.0 / n_rr)

    else:
        raise ValueError(f"Unknown bed_type: {bed_type!r}")

    # Enforce minimum grain diameter (2 px)
    return np.clip(diameters, 2.0, None)


# ------------------------------------------------------------------ #
# Colour palette helpers
# ------------------------------------------------------------------ #

def _rock_colour(rng: np.random.Generator) -> Tuple[int, int, int]:
    """Return a random rock-like RGB colour in gray/brown tones."""
    base = rng.integers(80, 180)
    r = int(np.clip(base + rng.integers(-15, 15), 0, 255))
    g = int(np.clip(base + rng.integers(-20, 10), 0, 255))
    b = int(np.clip(base + rng.integers(-25, 5), 0, 255))
    return r, g, b


# ------------------------------------------------------------------ #
# Grain placement engine
# ------------------------------------------------------------------ #

def _place_grains(
    rng: np.random.Generator,
    width: int,
    height: int,
    diameters: np.ndarray,
    depth_range: Tuple[float, float],
    max_attempts: int = 200,
) -> List[dict]:
    """Place ellipsoidal grains with simple overlap avoidance.

    Each grain is stored as a dict with keys:
        cx, cy     -- centre pixel coordinates
        a, b       -- semi-axis lengths (pixels)
        angle      -- rotation angle (radians)
        z_peak     -- peak depth value
        colour     -- (R, G, B) tuple

    Overlap avoidance uses a greedy circle-packing heuristic: each new
    grain is placed at a random location and accepted only if it does
    not overlap more than 30 % of its radius with any existing grain.
    """
    grains: List[dict] = []
    centres: List[Tuple[float, float, float]] = []  # (cx, cy, r_eff)

    z_lo, z_hi = depth_range

    for d in diameters:
        # Random aspect ratio 0.6 -- 1.0 (slightly elongated)
        aspect = rng.uniform(0.6, 1.0)
        a = d / 2.0
        b = a * aspect
        angle = rng.uniform(0, math.pi)
        z_peak = rng.uniform(z_lo, z_hi)
        colour = _rock_colour(rng)
        r_eff = max(a, b)

        placed = False
        for _ in range(max_attempts):
            cx = rng.uniform(r_eff, width - r_eff)
            cy = rng.uniform(r_eff, height - r_eff)

            # Check overlap with existing grains
            ok = True
            for ocx, ocy, or_eff in centres:
                dist = math.hypot(cx - ocx, cy - ocy)
                if dist < 0.7 * (r_eff + or_eff):
                    ok = False
                    break
            if ok:
                placed = True
                break

        if not placed:
            # Force placement at random position (allow overlap)
            cx = rng.uniform(r_eff, width - r_eff)
            cy = rng.uniform(r_eff, height - r_eff)

        centres.append((cx, cy, r_eff))
        grains.append({
            "cx": float(cx),
            "cy": float(cy),
            "a": float(a),
            "b": float(b),
            "angle": float(angle),
            "z_peak": float(z_peak),
            "colour": colour,
        })

    return grains


# ------------------------------------------------------------------ #
# Rasterisation
# ------------------------------------------------------------------ #

def _rasterise(
    grains: List[dict],
    width: int,
    height: int,
    bg_depth: float = 0.0,
) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Render grain list into RGB, depth, and label images.

    The label image assigns each pixel to the grain index (1-based) that
    has the highest depth at that pixel (painter's algorithm on depth).
    Background pixels are labelled 0.

    Returns
    -------
    rgb : ndarray, shape (H, W, 3), dtype uint8
    depth : ndarray, shape (H, W), dtype float32
    labels : ndarray, shape (H, W), dtype int32
    """
    rgb = np.full((height, width, 3), 40, dtype=np.uint8)  # dark background
    depth = np.full((height, width), bg_depth, dtype=np.float32)
    labels = np.zeros((height, width), dtype=np.int32)

    # Pre-compute coordinate grid
    yy, xx = np.mgrid[0:height, 0:width]
    xx = xx.astype(np.float64)
    yy = yy.astype(np.float64)

    for idx, g in enumerate(grains, start=1):
        cx, cy = g["cx"], g["cy"]
        a, b = g["a"], g["b"]
        angle = g["angle"]
        z_peak = g["z_peak"]
        r, gc_, bc_ = g["colour"]

        cos_a = math.cos(angle)
        sin_a = math.sin(angle)

        # Bounding box for speed
        r_max = max(a, b) + 1
        x0 = max(0, int(cx - r_max))
        x1 = min(width, int(cx + r_max) + 1)
        y0 = max(0, int(cy - r_max))
        y1 = min(height, int(cy + r_max) + 1)

        lx = xx[y0:y1, x0:x1] - cx
        ly = yy[y0:y1, x0:x1] - cy

        # Rotate into grain-local frame
        lx_rot = lx * cos_a + ly * sin_a
        ly_rot = -lx * sin_a + ly * cos_a

        # Ellipsoid distance (normalised)
        e2 = (lx_rot / max(a, 1e-6)) ** 2 + (ly_rot / max(b, 1e-6)) ** 2
        inside = e2 < 1.0

        # Depth: ellipsoidal dome  z = z_peak * sqrt(1 - e2)
        z_local = np.where(inside, z_peak * np.sqrt(np.maximum(0.0, 1.0 - e2)), 0.0)

        # Painter's algorithm: overwrite where this grain is higher
        region_depth = depth[y0:y1, x0:x1]
        higher = z_local > region_depth

        mask = inside & higher

        if not np.any(mask):
            continue

        depth[y0:y1, x0:x1] = np.where(mask, z_local, region_depth)
        labels[y0:y1, x0:x1] = np.where(mask, idx, labels[y0:y1, x0:x1])

        # Shade colour with simple Lambertian-like darkening at edges
        shade = np.clip(np.sqrt(np.maximum(0.0, 1.0 - e2)), 0.3, 1.0)
        for c_idx, c_val in enumerate((r, gc_, bc_)):
            chan = rgb[y0:y1, x0:x1, c_idx]
            rgb[y0:y1, x0:x1, c_idx] = np.where(
                mask,
                np.clip(c_val * shade, 0, 255).astype(np.uint8),
                chan,
            )

    return rgb, depth, labels


# ------------------------------------------------------------------ #
# Public entry point
# ------------------------------------------------------------------ #

def generate_grain_bed(
    bed_type: BedType = "lognormal",
    width: int = 256,
    height: int = 256,
    num_grains: int = 50,
    mean_diameter: float = 20.0,
    std_diameter: float = 5.0,
    depth_range: Tuple[float, float] = (5.0, 50.0),
    seed: Optional[int] = None,
) -> Tuple[np.ndarray, np.ndarray, np.ndarray, List[float]]:
    """Generate a synthetic RGB-D grain bed image.

    Creates a realistic simulated image of rock fragments / particles as
    seen by an RGB-D camera looking down at a conveyor belt or stockpile
    surface.

    Each grain is modelled as a 3D ellipsoid projected onto the image
    plane with:

    * Random position (with overlap handling via greedy circle-packing)
    * Random size drawn from the specified distribution
    * Random orientation (rotation angle)
    * Random colour (gray/brown tones typical of rock)
    * Depth profile: ellipsoidal surface with peak at grain centre

    Parameters
    ----------
    bed_type : str
        Size distribution family.  One of ``'uniform'``, ``'normal'``,
        ``'lognormal'``, ``'bimodal'``, ``'rosin_rammler'``.
    width, height : int
        Output image dimensions in pixels.
    num_grains : int
        Number of grains to place (some may overlap if the image is too
        crowded).
    mean_diameter : float
        Mean (or characteristic) grain diameter in pixels.
    std_diameter : float
        Standard deviation of diameter.  For the Rosin-Rammler
        distribution this is the uniformity index *n* (>= 0.5).
    depth_range : tuple of float
        (min, max) depth peak for individual grains.  The background
        is at depth = 0.
    seed : int or None
        Random seed for reproducibility.

    Returns
    -------
    rgb : ndarray, shape (H, W, 3), dtype uint8
        Synthetic colour image of the grain bed.
    depth : ndarray, shape (H, W), dtype float32
        Depth map in arbitrary length units (e.g. mm).
    labels : ndarray, shape (H, W), dtype int32
        Per-pixel grain label; 0 = background, 1..N = grain index.
    true_diameters : list of float
        Ground-truth equivalent diameters of all generated grains,
        ordered by grain index (1-based).
    """
    rng = np.random.default_rng(seed)

    diameters = _sample_diameters(rng, num_grains, bed_type, mean_diameter, std_diameter)

    grains = _place_grains(rng, width, height, diameters, depth_range)

    rgb, depth, labels = _rasterise(grains, width, height)

    # True equivalent diameters: 2 * sqrt(a*b) for each ellipse
    true_diameters = [2.0 * math.sqrt(g["a"] * g["b"]) for g in grains]

    return rgb, depth, labels, true_diameters
