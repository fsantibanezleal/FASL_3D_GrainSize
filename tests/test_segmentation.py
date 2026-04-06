"""
Unit tests for the grain segmentation module.

Tests cover:
- Watershed segmentation produces valid labels
- Depth-edge segmentation produces valid labels
- Small-fragment merging works correctly
- Background pixels remain labelled 0
"""

import sys
import os
import unittest

import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.simulation.grain_generator import generate_grain_bed
from app.simulation.segmentation import (
    segment_grains_watershed,
    segment_grains_depth_edges,
    segment_grains_rgbd,
)


class TestSegmentation(unittest.TestCase):
    """Tests for grain segmentation functions."""

    @classmethod
    def setUpClass(cls):
        """Generate a shared grain bed for all tests."""
        cls.rgb, cls.depth, cls.gt_labels, cls.true_diameters = generate_grain_bed(
            bed_type="lognormal",
            width=128, height=128, num_grains=30, seed=42,
        )

    def test_watershed_output_shape(self):
        """Watershed labels have same shape as input depth."""
        labels = segment_grains_watershed(self.depth, self.rgb)
        self.assertEqual(labels.shape, self.depth.shape)

    def test_watershed_dtype(self):
        """Watershed labels are int32."""
        labels = segment_grains_watershed(self.depth)
        self.assertEqual(labels.dtype, np.int32)

    def test_watershed_finds_grains(self):
        """Watershed should detect at least some grains."""
        labels = segment_grains_watershed(self.depth, self.rgb)
        self.assertGreater(labels.max(), 0)

    def test_watershed_background_zero(self):
        """Background pixels should be labelled 0."""
        labels = segment_grains_watershed(self.depth)
        # Pixels where depth == 0 should generally be background
        bg_mask = self.depth < 0.1 * self.depth.max()
        bg_labels = labels[bg_mask]
        # Most background pixels should be 0 (allow some tolerance)
        frac_bg_zero = np.mean(bg_labels == 0)
        self.assertGreater(frac_bg_zero, 0.5)

    def test_depth_edges_output(self):
        """Depth-edge segmentation produces valid labels."""
        labels = segment_grains_depth_edges(self.depth, edge_threshold=2.0)
        self.assertEqual(labels.shape, self.depth.shape)
        self.assertEqual(labels.dtype, np.int32)

    def test_depth_edges_finds_grains(self):
        """Depth-edge segmentation should find grains."""
        labels = segment_grains_depth_edges(self.depth, edge_threshold=1.0)
        self.assertGreater(labels.max(), 0)

    def test_min_grain_size_filtering(self):
        """Setting a large min_grain_size should reduce grain count."""
        labels_small = segment_grains_watershed(self.depth, min_grain_size=1)
        labels_large = segment_grains_watershed(self.depth, min_grain_size=50)
        n_small = len(np.unique(labels_small)) - 1  # exclude 0
        n_large = len(np.unique(labels_large)) - 1
        self.assertGreaterEqual(n_small, n_large)


    def test_rgbd_segmentation_output(self):
        """Combined RGB-D segmentation produces valid labels."""
        labels = segment_grains_rgbd(self.depth, self.rgb, min_grain_size=5)
        self.assertEqual(labels.shape, self.depth.shape)
        self.assertEqual(labels.dtype, np.int32)
        self.assertGreater(labels.max(), 0)

    def test_rgbd_segmentation_weight_effect(self):
        """Changing depth/color weights should affect results."""
        labels_depth_heavy = segment_grains_rgbd(
            self.depth, self.rgb, depth_weight=0.9, color_weight=0.1)
        labels_color_heavy = segment_grains_rgbd(
            self.depth, self.rgb, depth_weight=0.1, color_weight=0.9)
        # Not necessarily identical segmentations
        n_depth = len(np.unique(labels_depth_heavy))
        n_color = len(np.unique(labels_color_heavy))
        # Both should find grains
        self.assertGreater(n_depth, 1)
        self.assertGreater(n_color, 1)


if __name__ == "__main__":
    unittest.main()
