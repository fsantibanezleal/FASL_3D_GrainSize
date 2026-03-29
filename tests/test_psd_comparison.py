"""
Unit tests for PSD comparison functions.

Tests cover:
- compare_psd: RMSE, KS statistic, D50 error metrics
- generate_sieve_ground_truth: output structure and consistency
- Perfect match case (zero error)
- Known offset case
- Edge cases (short arrays, identical curves)
"""

import sys
import os
import unittest

import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.simulation.granulometry import (
    compare_psd,
    generate_sieve_ground_truth,
    compute_psd,
    compute_sieve_analysis,
    full_psd_analysis,
)


class TestComparePsd(unittest.TestCase):
    """Tests for compare_psd()."""

    def test_identical_curves_zero_error(self):
        """Comparing identical curves should yield RMSE ~ 0 and KS ~ 0."""
        sizes = np.linspace(1, 100, 50).tolist()
        passing = np.linspace(0, 100, 50).tolist()
        result = compare_psd(sizes, passing, sizes, passing)
        self.assertAlmostEqual(result['rmse'], 0.0, places=2)
        self.assertAlmostEqual(result['ks_statistic'], 0.0, places=2)
        self.assertAlmostEqual(result['d50_relative_error'], 0.0, places=2)

    def test_known_offset(self):
        """A uniform offset in passing should produce predictable RMSE."""
        sizes = np.linspace(1, 100, 50).tolist()
        passing_a = np.linspace(0, 100, 50).tolist()
        passing_b = np.linspace(10, 100, 50).tolist()  # shifted
        result = compare_psd(sizes, passing_a, sizes, passing_b)
        self.assertGreater(result['rmse'], 0.0)
        self.assertGreater(result['ks_statistic'], 0.0)

    def test_d50_values_present(self):
        """Result should contain estimated and true D50."""
        sizes = np.linspace(1, 50, 30).tolist()
        passing = np.linspace(0, 100, 30).tolist()
        result = compare_psd(sizes, passing, sizes, passing)
        self.assertIn('estimated_d50', result)
        self.assertIn('true_d50', result)
        self.assertIn('d50_relative_error', result)

    def test_different_size_grids(self):
        """Curves on different size grids should still compare correctly."""
        est_sizes = np.linspace(1, 80, 40).tolist()
        est_passing = np.linspace(0, 100, 40).tolist()
        true_sizes = np.linspace(5, 60, 20).tolist()
        true_passing = np.linspace(0, 100, 20).tolist()
        result = compare_psd(est_sizes, est_passing, true_sizes, true_passing)
        self.assertFalse(np.isnan(result['rmse']))
        self.assertFalse(np.isnan(result['ks_statistic']))

    def test_short_arrays_return_nan(self):
        """Arrays with < 2 elements should return NaN metrics."""
        result = compare_psd([1.0], [50.0], [1.0], [50.0])
        self.assertTrue(np.isnan(result['rmse']))

    def test_metrics_are_positive(self):
        """RMSE and KS should be non-negative."""
        rng = np.random.default_rng(42)
        d_est = rng.lognormal(2.5, 0.4, 80)
        d_true = rng.lognormal(2.6, 0.3, 100)
        s1, p1 = compute_psd(d_est.tolist())
        s2, p2 = compute_psd(d_true.tolist())
        result = compare_psd(s1.tolist(), p1.tolist(), s2.tolist(), p2.tolist())
        self.assertGreaterEqual(result['rmse'], 0.0)
        self.assertGreaterEqual(result['ks_statistic'], 0.0)
        self.assertGreaterEqual(result['d50_relative_error'], 0.0)


class TestGenerateSieveGroundTruth(unittest.TestCase):
    """Tests for generate_sieve_ground_truth()."""

    def setUp(self):
        rng = np.random.default_rng(42)
        self.diameters = rng.lognormal(mean=2.5, sigma=0.4, size=100).tolist()

    def test_output_keys(self):
        """Should return sieve_sizes, cum_passing, retained."""
        result = generate_sieve_ground_truth(self.diameters)
        self.assertIn('sieve_sizes', result)
        self.assertIn('cum_passing', result)
        self.assertIn('retained', result)

    def test_output_lengths_match(self):
        """All output arrays should have the same length."""
        result = generate_sieve_ground_truth(self.diameters)
        n = len(result['sieve_sizes'])
        self.assertEqual(len(result['cum_passing']), n)
        self.assertEqual(len(result['retained']), n)

    def test_cum_passing_monotonic(self):
        """Cumulative passing should be non-decreasing."""
        result = generate_sieve_ground_truth(self.diameters)
        cp = np.array(result['cum_passing'])
        if len(cp) > 1:
            self.assertTrue(np.all(np.diff(cp) >= -1e-10))

    def test_custom_sieve_sizes(self):
        """Custom sieve sizes should be used."""
        custom = [5.0, 10.0, 20.0, 50.0]
        result = generate_sieve_ground_truth(self.diameters, sieve_sizes=custom)
        self.assertEqual(len(result['sieve_sizes']), len(custom))

    def test_round_trip_consistency(self):
        """Ground truth sieve from known diameters should be consistent
        with compute_sieve_analysis."""
        gt = generate_sieve_ground_truth(self.diameters)
        sv_sizes, _, sv_passing = compute_sieve_analysis(self.diameters)
        np.testing.assert_array_almost_equal(
            gt['cum_passing'], sv_passing.tolist(), decimal=4,
        )


class TestEndToEndComparison(unittest.TestCase):
    """Integration test: generate, estimate PSD, compare with ground truth."""

    def test_full_comparison_pipeline(self):
        """Full pipeline: generate diameters, compute PSD, compare."""
        rng = np.random.default_rng(99)
        true_d = rng.lognormal(2.5, 0.3, 100).tolist()

        # Estimated PSD (simulate some noise)
        est_d = [d * (1 + rng.normal(0, 0.05)) for d in true_d]

        est_psd = full_psd_analysis(est_d)
        true_gt = generate_sieve_ground_truth(true_d)

        result = compare_psd(
            est_psd['sizes'], est_psd['passing'],
            true_gt['sieve_sizes'], true_gt['cum_passing'],
        )
        # With only 5% noise, RMSE should be moderate
        self.assertLess(result['rmse'], 30.0)
        self.assertLess(result['d50_relative_error'], 0.3)


if __name__ == "__main__":
    unittest.main()
