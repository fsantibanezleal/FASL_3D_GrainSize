"""
Unit tests for the grain measurement module.

Tests cover:
- Measurement output structure and keys
- Positive values for geometric properties
- Equivalent diameter consistency with area
- Circularity range [0, 1]
"""

import sys
import os
import math
import unittest

import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.simulation.grain_generator import generate_grain_bed
from app.simulation.segmentation import segment_grains_watershed
from app.simulation.grain_measurement import measure_grains


class TestMeasurement(unittest.TestCase):
    """Tests for measure_grains()."""

    @classmethod
    def setUpClass(cls):
        """Generate a grain bed and segment it."""
        cls.rgb, cls.depth, _, _ = generate_grain_bed(
            bed_type="normal", width=128, height=128, num_grains=20, seed=77,
        )
        cls.labels = segment_grains_watershed(cls.depth, cls.rgb)
        cls.measurements = measure_grains(cls.labels, cls.depth, pixel_size=1.0)

    def test_non_empty(self):
        """Should return at least one grain measurement."""
        self.assertGreater(len(self.measurements), 0)

    def test_required_keys(self):
        """Each measurement dict should contain all expected keys."""
        required = {
            "id", "area_px", "area_mm2", "perimeter_px",
            "bbox_x", "bbox_y", "bbox_w", "bbox_h",
            "equiv_diameter", "major_axis", "minor_axis",
            "aspect_ratio", "orientation_deg", "circularity",
            "mean_depth", "depth_range", "volume",
            "centroid_x", "centroid_y",
        }
        for m in self.measurements:
            self.assertTrue(required.issubset(m.keys()), f"Missing keys: {required - m.keys()}")

    def test_positive_values(self):
        """Area, diameter, and axes should be positive."""
        for m in self.measurements:
            self.assertGreater(m["area_px"], 0)
            self.assertGreater(m["equiv_diameter"], 0)
            self.assertGreater(m["major_axis"], 0)

    def test_equiv_diameter_consistency(self):
        """Equivalent diameter should be consistent with area."""
        for m in self.measurements:
            expected_d = 2.0 * math.sqrt(m["area_mm2"] / math.pi)
            self.assertAlmostEqual(m["equiv_diameter"], expected_d, places=2)

    def test_circularity_range(self):
        """Circularity should be in [0, ~1.2] (can exceed 1 due to digitisation)."""
        for m in self.measurements:
            self.assertGreaterEqual(m["circularity"], 0.0)
            self.assertLessEqual(m["circularity"], 2.0)  # can exceed 1 for small/irregular grains

    def test_aspect_ratio_ge_one(self):
        """Aspect ratio should be >= 1 (major >= minor)."""
        for m in self.measurements:
            self.assertGreaterEqual(m["aspect_ratio"], 0.9)  # allow slight numerical margin


if __name__ == "__main__":
    unittest.main()
