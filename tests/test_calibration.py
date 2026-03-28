"""
Unit tests for the calibration module.

Tests cover:
- Default state (uncalibrated)
- Calibration from reference points
- Calibration from direct pixel size
- Pixel-to-mm and area conversions
- Edge cases (zero-length reference)
- Integration with grain measurement
"""

import sys
import os
import math
import unittest

import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.simulation.calibration import Calibration
from app.simulation.grain_generator import generate_grain_bed
from app.simulation.segmentation import segment_grains_watershed
from app.simulation.grain_measurement import measure_grains


class TestCalibration(unittest.TestCase):
    """Tests for Calibration dataclass."""

    def test_default_uncalibrated(self):
        """New calibration should be uncalibrated with pixel_size=1.0."""
        cal = Calibration()
        self.assertFalse(cal.calibrated)
        self.assertEqual(cal.pixel_size_mm, 1.0)

    def test_calibrate_from_pixel_size(self):
        """Direct pixel size calibration should set calibrated=True."""
        cal = Calibration()
        result = cal.calibrate_from_pixel_size(0.25)
        self.assertTrue(result)
        self.assertTrue(cal.calibrated)
        self.assertAlmostEqual(cal.pixel_size_mm, 0.25)

    def test_calibrate_from_reference(self):
        """Reference-based calibration computes correct pixel size."""
        cal = Calibration()
        # 100 px horizontal distance = 10 mm  =>  0.1 mm/px
        result = cal.calibrate_from_reference([0, 0], [100, 0], 10.0)
        self.assertTrue(result)
        self.assertTrue(cal.calibrated)
        self.assertAlmostEqual(cal.pixel_size_mm, 0.1, places=6)
        self.assertAlmostEqual(cal.reference_length_mm, 10.0)
        self.assertAlmostEqual(cal.reference_length_px, 100.0)

    def test_calibrate_from_reference_diagonal(self):
        """Diagonal reference should compute Euclidean distance."""
        cal = Calibration()
        # Distance = sqrt(30^2 + 40^2) = 50 px.  Known = 25 mm => 0.5 mm/px
        result = cal.calibrate_from_reference([10, 10], [40, 50], 25.0)
        self.assertTrue(result)
        self.assertAlmostEqual(cal.pixel_size_mm, 0.5, places=6)

    def test_calibrate_zero_distance_fails(self):
        """Zero-length reference should fail gracefully."""
        cal = Calibration()
        result = cal.calibrate_from_reference([5, 5], [5, 5], 10.0)
        self.assertFalse(result)
        self.assertFalse(cal.calibrated)

    def test_px_to_mm(self):
        """Pixel-to-mm conversion should use pixel_size_mm."""
        cal = Calibration()
        cal.calibrate_from_pixel_size(0.5)
        self.assertAlmostEqual(cal.px_to_mm(10), 5.0)
        self.assertAlmostEqual(cal.px_to_mm(0), 0.0)
        self.assertAlmostEqual(cal.px_to_mm(1), 0.5)

    def test_area_px_to_mm2(self):
        """Area conversion should use pixel_size^2."""
        cal = Calibration()
        cal.calibrate_from_pixel_size(0.5)
        # 100 px^2 * (0.5 mm/px)^2 = 25 mm^2
        self.assertAlmostEqual(cal.area_px_to_mm2(100), 25.0)

    def test_get_state(self):
        """get_state should return a dict with expected keys."""
        cal = Calibration()
        cal.calibrate_from_pixel_size(2.0)
        s = cal.get_state()
        self.assertIn('pixel_size_mm', s)
        self.assertIn('calibrated', s)
        self.assertIn('reference_length_mm', s)
        self.assertIn('reference_length_px', s)
        self.assertTrue(s['calibrated'])
        self.assertAlmostEqual(s['pixel_size_mm'], 2.0)

    def test_measurement_with_calibration(self):
        """measure_grains should use calibration pixel_size when provided."""
        rgb, depth, _, _ = generate_grain_bed(
            bed_type="normal", width=64, height=64, num_grains=10, seed=88,
        )
        labels = segment_grains_watershed(depth, rgb)

        cal = Calibration()
        cal.calibrate_from_pixel_size(0.5)

        m_cal = measure_grains(labels, depth, calibration=cal)
        m_def = measure_grains(labels, depth, pixel_size=1.0)

        # With 0.5 mm/px, areas should be 0.25x the default (pixel_size=1.0)
        if len(m_cal) > 0 and len(m_def) > 0:
            ratio = m_cal[0]["area_mm2"] / m_def[0]["area_mm2"]
            self.assertAlmostEqual(ratio, 0.25, places=2)

    def test_calibration_overrides_pixel_size(self):
        """When calibration is provided, pixel_size argument is ignored."""
        rgb, depth, _, _ = generate_grain_bed(
            bed_type="normal", width=64, height=64, num_grains=10, seed=88,
        )
        labels = segment_grains_watershed(depth, rgb)

        cal = Calibration()
        cal.calibrate_from_pixel_size(2.0)

        # pixel_size=1.0 should be overridden by calibration pixel_size=2.0
        m1 = measure_grains(labels, depth, pixel_size=1.0, calibration=cal)
        m2 = measure_grains(labels, depth, pixel_size=999.0, calibration=cal)

        if len(m1) > 0 and len(m2) > 0:
            self.assertAlmostEqual(m1[0]["area_mm2"], m2[0]["area_mm2"], places=3)


if __name__ == "__main__":
    unittest.main()
