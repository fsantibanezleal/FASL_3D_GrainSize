"""
Unit tests for the granulometry / PSD module.

Tests cover:
- PSD curve computation (number and mass weighted)
- D-value interpolation correctness
- Rosin-Rammler fitting quality
- Sieve analysis output structure
- Full pipeline integration
"""

import sys
import os
import unittest

import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.simulation.granulometry import (
    compute_psd,
    compute_percentiles,
    fit_rosin_rammler,
    compute_sieve_analysis,
    full_psd_analysis,
)


class TestGranulometry(unittest.TestCase):
    """Tests for PSD analysis functions."""

    def setUp(self):
        """Create a known diameter set."""
        rng = np.random.default_rng(42)
        self.diameters = rng.lognormal(mean=2.5, sigma=0.4, size=100).tolist()

    def test_psd_output_shapes(self):
        """PSD curve arrays should be equal length."""
        sizes, passing = compute_psd(self.diameters, method="number")
        self.assertEqual(len(sizes), len(passing))
        self.assertGreater(len(sizes), 0)

    def test_psd_monotonic(self):
        """Cumulative passing should be monotonically non-decreasing."""
        sizes, passing = compute_psd(self.diameters, method="number")
        diffs = np.diff(passing)
        self.assertTrue(np.all(diffs >= -1e-10))

    def test_psd_mass_weighted(self):
        """Mass-weighted PSD should also be monotonic and reach ~100%."""
        sizes, passing = compute_psd(self.diameters, method="mass")
        self.assertTrue(np.all(np.diff(passing) >= -1e-10))
        self.assertAlmostEqual(passing[-1], 100.0, places=0)

    def test_percentiles_order(self):
        """D10 < D50 < D80 < D90."""
        sizes, passing = compute_psd(self.diameters)
        p = compute_percentiles(sizes, passing)
        self.assertLess(p["D10"], p["D50"])
        self.assertLess(p["D50"], p["D80"])
        self.assertLess(p["D80"], p["D90"])

    def test_rosin_rammler_fit(self):
        """Rosin-Rammler fit should have reasonable R-squared."""
        sizes, passing = compute_psd(self.diameters)
        rr = fit_rosin_rammler(sizes, passing)
        self.assertFalse(np.isnan(rr["x0"]))
        self.assertFalse(np.isnan(rr["n"]))
        self.assertGreater(rr["r_squared"], 0.8)

    def test_sieve_analysis_structure(self):
        """Sieve analysis should return three arrays of equal length."""
        sv_sizes, retained, cum_passing = compute_sieve_analysis(self.diameters)
        self.assertEqual(len(sv_sizes), len(retained))
        self.assertEqual(len(sv_sizes), len(cum_passing))

    def test_sieve_cum_passing_monotonic(self):
        """Sieve cumulative passing should be monotonically non-decreasing."""
        _, _, cum_passing = compute_sieve_analysis(self.diameters)
        if len(cum_passing) > 1:
            self.assertTrue(np.all(np.diff(cum_passing) >= -1e-10))

    def test_full_pipeline(self):
        """Full PSD analysis should return all expected keys."""
        result = full_psd_analysis(self.diameters, method="number")
        self.assertIn("sizes", result)
        self.assertIn("passing", result)
        self.assertIn("percentiles", result)
        self.assertIn("rosin_rammler", result)
        self.assertIn("sieve_sizes", result)
        self.assertIn("histogram", result)

    def test_empty_input(self):
        """Empty diameters should not crash."""
        sizes, passing = compute_psd([], method="number")
        self.assertEqual(len(sizes), 0)


if __name__ == "__main__":
    unittest.main()
