"""
Unit tests for the grain bed generator module.

Tests cover:
- Output shapes and dtypes
- All bed type distributions
- Reproducibility via seed
- Grain count and diameter range
"""

import sys
import os
import unittest

import numpy as np

# Ensure project root is importable
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.simulation.grain_generator import generate_grain_bed


class TestGrainGenerator(unittest.TestCase):
    """Tests for generate_grain_bed()."""

    def test_output_shapes(self):
        """RGB, depth, labels have correct shapes; diameters list is correct length."""
        rgb, depth, labels, diameters = generate_grain_bed(
            width=64, height=64, num_grains=10, seed=42,
        )
        self.assertEqual(rgb.shape, (64, 64, 3))
        self.assertEqual(depth.shape, (64, 64))
        self.assertEqual(labels.shape, (64, 64))
        self.assertEqual(len(diameters), 10)

    def test_output_dtypes(self):
        """Check NumPy dtypes of outputs."""
        rgb, depth, labels, _ = generate_grain_bed(
            width=32, height=32, num_grains=5, seed=1,
        )
        self.assertEqual(rgb.dtype, np.uint8)
        self.assertEqual(depth.dtype, np.float32)
        self.assertEqual(labels.dtype, np.int32)

    def test_all_bed_types(self):
        """All five distribution types produce valid output."""
        for bed_type in ("uniform", "normal", "lognormal", "bimodal", "rosin_rammler"):
            rgb, depth, labels, diameters = generate_grain_bed(
                bed_type=bed_type,
                width=64, height=64, num_grains=15, seed=99,
            )
            self.assertGreater(len(diameters), 0, f"{bed_type} produced 0 diameters")
            self.assertTrue(np.all(np.array(diameters) > 0), f"{bed_type} has non-positive diameters")

    def test_reproducibility(self):
        """Same seed produces identical outputs."""
        a = generate_grain_bed(width=32, height=32, num_grains=8, seed=123)
        b = generate_grain_bed(width=32, height=32, num_grains=8, seed=123)
        np.testing.assert_array_equal(a[0], b[0])  # RGB
        np.testing.assert_array_equal(a[1], b[1])  # Depth
        np.testing.assert_array_equal(a[2], b[2])  # Labels
        self.assertEqual(a[3], b[3])                # Diameters

    def test_labels_nonzero(self):
        """At least some pixels should be labelled (non-background)."""
        _, _, labels, _ = generate_grain_bed(
            width=128, height=128, num_grains=20, seed=7,
        )
        self.assertGreater(labels.max(), 0)

    def test_depth_range(self):
        """Depth values should fall within expected range."""
        _, depth, _, _ = generate_grain_bed(
            width=64, height=64, num_grains=10,
            depth_range=(10.0, 30.0), seed=5,
        )
        # Non-background pixels should have depth > 0
        fg = depth[depth > 0]
        if len(fg) > 0:
            self.assertLessEqual(fg.max(), 30.0 + 1.0)  # small tolerance


if __name__ == "__main__":
    unittest.main()
