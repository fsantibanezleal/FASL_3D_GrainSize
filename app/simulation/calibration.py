"""
Image calibration: pixel-to-physical-unit conversion.

Calibration is essential for accurate grain size measurement.
Without it, measurements are in pixels; with it, in millimeters.

Two calibration methods:
1. Reference object: user places an object of known size, clicks
   two points to define the reference length.
2. Known pixel size: user enters the pixel pitch directly
   (e.g., from camera/sensor datasheet).
"""
import numpy as np
from dataclasses import dataclass


@dataclass
class Calibration:
    """Stores the pixel-to-physical calibration."""
    pixel_size_mm: float = 1.0  # mm per pixel
    reference_length_mm: float = 0.0
    reference_length_px: float = 0.0
    calibrated: bool = False

    def calibrate_from_reference(self, point_a, point_b, known_length_mm):
        """Calibrate using two points of known physical distance.

        pixel_size = known_length_mm / distance_in_pixels
        """
        dx = point_b[0] - point_a[0]
        dy = point_b[1] - point_a[1]
        dist_px = np.sqrt(dx**2 + dy**2)
        if dist_px < 1e-6:
            return False
        self.pixel_size_mm = known_length_mm / dist_px
        self.reference_length_mm = known_length_mm
        self.reference_length_px = dist_px
        self.calibrated = True
        return True

    def calibrate_from_pixel_size(self, pixel_size_mm):
        """Set pixel size directly from sensor specifications."""
        self.pixel_size_mm = pixel_size_mm
        self.calibrated = True
        return True

    def px_to_mm(self, value_px):
        """Convert pixel measurement to millimeters."""
        return value_px * self.pixel_size_mm

    def area_px_to_mm2(self, area_px):
        """Convert pixel area to mm squared."""
        return area_px * self.pixel_size_mm**2

    def get_state(self):
        return {
            'pixel_size_mm': self.pixel_size_mm,
            'calibrated': self.calibrated,
            'reference_length_mm': self.reference_length_mm,
            'reference_length_px': self.reference_length_px,
        }
