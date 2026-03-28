"""
REST API routes for the GrainSight web application.

Provides endpoints for grain bed generation, segmentation, measurement,
PSD analysis, and data export.  These endpoints are defined directly in
:mod:`app.main` for simplicity; this module is reserved for future
expansion (e.g. batch processing, image upload, parameter presets).
"""

from fastapi import APIRouter

router = APIRouter(prefix="/api", tags=["grainsight"])


# NOTE: Routes are defined directly in main.py for the initial version.
# This module is reserved for future expansion such as:
# - POST /api/upload        -- Upload external RGB + depth images
# - POST /api/batch         -- Batch processing of multiple images
# - GET  /api/presets       -- Parameter preset management
# - POST /api/report        -- Generate PDF analysis report
#
# Endpoints added in main.py:
# - POST /api/calibrate     -- Pixel-to-mm calibration (reference or direct)
# - GET  /api/calibration   -- Current calibration state
# - POST /api/compare-psd   -- Compare estimated PSD with ground truth sieve data
