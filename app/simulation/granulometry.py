"""
Particle Size Distribution (PSD) analysis for GrainSight.

This module computes cumulative grain size distribution curves, extracts
characteristic percentile values (D10, D50, D80, ...), fits the
Rosin-Rammler model, and simulates a physical sieve analysis.

Theory
------
The **cumulative PSD** expresses the fraction of material finer than a
given size *x*.  Two weighting schemes are common:

* **Number-weighted** (count-based):

  .. math:: F_N(x) = \\frac{\\#\\{d_i \\le x\\}}{N}

* **Mass-weighted** (volume-based, assumes :math:`\\rho=\\text{const}`):

  .. math:: F_M(x) = \\frac{\\sum_{d_i \\le x} d_i^3}{\\sum d_i^3}

Percentile values
-----------------
:math:`D_p` is the size at which *p* % of the material passes:

* **D10** -- effective size (filtration, hydraulic conductivity).
* **D50** -- median grain size.
* **D80** -- 80 % passing size (used in comminution design, Bond work
  index calculations).

Rosin-Rammler distribution
--------------------------
The cumulative fraction retained is:

.. math::

    R(x) = \\exp\\!\\left[-\\left(\\frac{x}{x_0}\\right)^{n}\\right]

Equivalently, the fraction passing is:

.. math::

    F(x) = 1 - \\exp\\!\\left[-\\left(\\frac{x}{x_0}\\right)^{n}\\right]

where :math:`x_0` is the **characteristic size** (63.2 % passing) and
:math:`n` is the **uniformity index** (higher *n* -> narrower PSD).

Linearisation for fitting:

.. math::

    \\ln\\!\\bigl[-\\ln(1-F)\\bigr] = n\\,\\ln(x) - n\\,\\ln(x_0)

References
----------
* Rosin & Rammler (1933). *J. Inst. Fuel*, 7, 29--36.
* Bond (1952). *Trans. AIME*, 193, 484--494.
* ISO 565:1990 *Test sieves*.
"""

from __future__ import annotations

from typing import Dict, List, Optional, Sequence, Tuple

import numpy as np
from scipy.optimize import curve_fit


# ------------------------------------------------------------------ #
# Standard sieve sizes (mm)
# ------------------------------------------------------------------ #

STANDARD_SIEVE_SIZES: List[float] = [
    0.075, 0.15, 0.3, 0.6, 1.18, 2.36, 4.75,
    9.5, 19.0, 37.5, 50.0, 75.0, 100.0,
]


# ------------------------------------------------------------------ #
# PSD computation
# ------------------------------------------------------------------ #

def compute_psd(
    diameters: Sequence[float],
    method: str = "number",
    n_bins: int = 50,
) -> Tuple[np.ndarray, np.ndarray]:
    """Compute the cumulative Particle Size Distribution curve.

    Parameters
    ----------
    diameters : sequence of float
        Measured equivalent diameters (one per grain).
    method : ``'number'`` or ``'mass'``
        Weighting scheme.  ``'mass'`` uses :math:`V \\propto d^3`.
    n_bins : int
        Number of size classes for the output curve.

    Returns
    -------
    sizes : ndarray, shape (n_bins,)
        Sieve / size values (ascending).
    passing : ndarray, shape (n_bins,)
        Cumulative fraction passing (0--100 %).
    """
    d = np.asarray(diameters, dtype=np.float64)
    if len(d) == 0:
        return np.array([]), np.array([])

    sizes = np.linspace(d.min() * 0.5, d.max() * 1.1, n_bins)

    if method == "mass":
        total_mass = np.sum(d ** 3)
        if total_mass == 0:
            return sizes, np.zeros_like(sizes)
        passing = np.array([
            np.sum(d[d <= s] ** 3) / total_mass * 100.0
            for s in sizes
        ])
    else:
        n_total = len(d)
        passing = np.array([
            np.sum(d <= s) / n_total * 100.0
            for s in sizes
        ])

    return sizes, passing


# ------------------------------------------------------------------ #
# Percentile extraction
# ------------------------------------------------------------------ #

def compute_percentiles(
    sizes: np.ndarray,
    passing: np.ndarray,
    percentiles: Sequence[float] = (10, 25, 50, 75, 80, 90),
) -> Dict[str, float]:
    """Extract D-values from a PSD curve by linear interpolation.

    Parameters
    ----------
    sizes, passing : ndarray
        Cumulative PSD curve (from :func:`compute_psd`).
    percentiles : sequence of float
        Desired percentile values (e.g. 10, 50, 80).

    Returns
    -------
    d_values : dict
        Mapping ``"D10"`` -> value, ``"D50"`` -> value, etc.
        If a percentile cannot be interpolated it is set to ``NaN``.
    """
    result: Dict[str, float] = {}
    for p in percentiles:
        key = f"D{int(p)}"
        if len(sizes) == 0 or len(passing) == 0:
            result[key] = float("nan")
            continue
        # Find the first index where passing >= p
        idx = np.searchsorted(passing, p)
        if idx == 0:
            result[key] = float(sizes[0])
        elif idx >= len(sizes):
            result[key] = float(sizes[-1])
        else:
            # Linear interpolation
            x0, x1 = sizes[idx - 1], sizes[idx]
            y0, y1 = passing[idx - 1], passing[idx]
            if y1 == y0:
                result[key] = float(x0)
            else:
                result[key] = float(x0 + (p - y0) * (x1 - x0) / (y1 - y0))
        result[key] = round(result[key], 4)
    return result


# ------------------------------------------------------------------ #
# Rosin-Rammler fit
# ------------------------------------------------------------------ #

def _rosin_rammler_cdf(x: np.ndarray, x0: float, n: float) -> np.ndarray:
    """Rosin-Rammler cumulative % passing.

    .. math:: F(x) = 100 \\cdot \\bigl[1 - \\exp(-(x/x_0)^n)\\bigr]
    """
    return 100.0 * (1.0 - np.exp(-((x / x0) ** n)))


def fit_rosin_rammler(
    sizes: np.ndarray,
    passing: np.ndarray,
) -> Dict[str, float]:
    """Fit a Rosin-Rammler distribution to PSD data.

    Uses non-linear least squares on the cumulative passing curve.

    Parameters
    ----------
    sizes, passing : ndarray
        Cumulative PSD curve.

    Returns
    -------
    params : dict
        ``x0`` -- characteristic size (63.2 % passing).
        ``n``  -- uniformity index.
        ``r_squared`` -- coefficient of determination.
    """
    if len(sizes) < 3 or len(passing) < 3:
        return {"x0": float("nan"), "n": float("nan"), "r_squared": 0.0}

    # Filter out zero/negative sizes and passing outside (0, 100)
    mask = (sizes > 0) & (passing > 0) & (passing < 100)
    xs = sizes[mask]
    ys = passing[mask]

    if len(xs) < 3:
        return {"x0": float("nan"), "n": float("nan"), "r_squared": 0.0}

    try:
        popt, _ = curve_fit(
            _rosin_rammler_cdf,
            xs, ys,
            p0=[np.median(xs), 2.0],
            bounds=([1e-6, 0.1], [xs.max() * 10, 20.0]),
            maxfev=5000,
        )
        x0, n = popt

        # R-squared
        y_pred = _rosin_rammler_cdf(xs, x0, n)
        ss_res = np.sum((ys - y_pred) ** 2)
        ss_tot = np.sum((ys - np.mean(ys)) ** 2)
        r2 = 1.0 - ss_res / ss_tot if ss_tot > 0 else 0.0

        return {
            "x0": round(float(x0), 4),
            "n": round(float(n), 4),
            "r_squared": round(float(r2), 4),
        }
    except (RuntimeError, ValueError):
        return {"x0": float("nan"), "n": float("nan"), "r_squared": 0.0}


# ------------------------------------------------------------------ #
# Sieve analysis simulation
# ------------------------------------------------------------------ #

def compute_sieve_analysis(
    diameters: Sequence[float],
    sieve_sizes: Optional[Sequence[float]] = None,
) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Simulate a physical sieve analysis.

    Each grain passes through the finest sieve whose opening exceeds
    the grain's equivalent diameter.

    Parameters
    ----------
    diameters : sequence of float
        Grain diameters.
    sieve_sizes : sequence of float or None
        Sieve opening sizes in ascending order.  If *None*, a standard
        series is generated from the data range.

    Returns
    -------
    sieve_sizes : ndarray
        Sieve openings (ascending).
    retained : ndarray
        Percentage retained on each sieve (by count).
    cum_passing : ndarray
        Cumulative percentage passing each sieve.
    """
    d = np.asarray(diameters, dtype=np.float64)
    if len(d) == 0:
        return np.array([]), np.array([]), np.array([])

    if sieve_sizes is None:
        # Build sieve series that covers the data range
        sieve_sizes_arr = np.array([
            s for s in STANDARD_SIEVE_SIZES
            if s <= d.max() * 1.5
        ])
        if len(sieve_sizes_arr) == 0:
            sieve_sizes_arr = np.linspace(d.min() * 0.5, d.max() * 1.2, 10)
    else:
        sieve_sizes_arr = np.asarray(sieve_sizes, dtype=np.float64)

    sieve_sizes_arr = np.sort(sieve_sizes_arr)
    n_total = len(d)

    retained = np.zeros(len(sieve_sizes_arr))
    cum_passing = np.zeros(len(sieve_sizes_arr))

    for i, s in enumerate(sieve_sizes_arr):
        n_passing = np.sum(d <= s)
        cum_passing[i] = n_passing / n_total * 100.0

    # Retained on each sieve = difference in cumulative passing
    retained[0] = 100.0 - cum_passing[0]
    for i in range(1, len(retained)):
        retained[i] = cum_passing[i] - cum_passing[i - 1]

    return sieve_sizes_arr, retained, cum_passing


# ------------------------------------------------------------------ #
# Convenience: full analysis pipeline
# ------------------------------------------------------------------ #

def full_psd_analysis(
    diameters: Sequence[float],
    method: str = "number",
) -> Dict:
    """Run the complete PSD analysis pipeline.

    Parameters
    ----------
    diameters : sequence of float
        Grain equivalent diameters.
    method : ``'number'`` or ``'mass'``

    Returns
    -------
    result : dict
        Keys: ``sizes``, ``passing``, ``percentiles``,
        ``rosin_rammler``, ``sieve_sizes``, ``sieve_retained``,
        ``sieve_passing``, ``histogram`` (bin edges and counts).
    """
    sizes, passing = compute_psd(diameters, method=method)
    percentiles = compute_percentiles(sizes, passing)
    rr = fit_rosin_rammler(sizes, passing)
    sv_sizes, sv_retained, sv_passing = compute_sieve_analysis(diameters)

    # Histogram
    d_arr = np.asarray(diameters, dtype=np.float64)
    if len(d_arr) > 0:
        counts, bin_edges = np.histogram(d_arr, bins=20)
    else:
        counts, bin_edges = np.array([]), np.array([])

    return {
        "sizes": sizes.tolist(),
        "passing": passing.tolist(),
        "percentiles": percentiles,
        "rosin_rammler": rr,
        "sieve_sizes": sv_sizes.tolist(),
        "sieve_retained": sv_retained.tolist(),
        "sieve_passing": sv_passing.tolist(),
        "histogram": {
            "bin_edges": bin_edges.tolist(),
            "counts": counts.tolist(),
        },
    }
