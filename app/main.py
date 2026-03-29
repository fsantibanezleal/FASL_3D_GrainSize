"""
GrainSight -- 3D Particle Size & Granulometry Analyzer.

FastAPI web application for grain size estimation from RGB-D data using
marker-based watershed segmentation, per-grain measurement, and
Rosin-Rammler PSD curve fitting.

Usage:
    uvicorn app.main:app --reload --port 8010

The server exposes:
    GET  /                    -- Single-page application (index.html)
    POST /api/generate        -- Generate synthetic grain bed
    POST /api/segment         -- Run grain segmentation
    GET  /api/measurements    -- Get per-grain measurements
    GET  /api/psd             -- Get PSD curve + percentiles
    POST /api/settings        -- Update processing parameters
    GET  /api/state           -- Full state snapshot
    GET  /api/export/csv      -- Export measurements as CSV
    WS   /ws                  -- Real-time state streaming
"""

import asyncio
import csv
import io
import json
from pathlib import Path
from typing import List, Optional

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, StreamingResponse
from pydantic import BaseModel, Field

from .simulation.grain_generator import generate_grain_bed
from .simulation.segmentation import (
    segment_grains_watershed,
    segment_grains_depth_edges,
)
from .simulation.grain_measurement import measure_grains
from .simulation.granulometry import (
    full_psd_analysis,
    compare_psd,
    generate_sieve_ground_truth,
    compute_psd,
)
from .simulation.calibration import Calibration
from .simulation.depth_features import (
    compute_depth_gradient,
    detect_grain_peaks,
    compute_local_roughness,
)
from .simulation.volume_estimation import estimate_all_volumes

import numpy as np

# ------------------------------------------------------------------ #
# App setup
# ------------------------------------------------------------------ #

app = FastAPI(
    title="GrainSight",
    description="3D Particle Size & Granulometry Analyzer",
    version="2.0.0",
)

static_dir = Path(__file__).parent / "static"
app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

# ------------------------------------------------------------------ #
# Shared mutable state
# ------------------------------------------------------------------ #

calibration = Calibration()

state: dict = {
    "rgb": None,              # (H, W, 3) uint8
    "depth": None,            # (H, W) float32
    "labels": None,           # (H, W) int32
    "true_diameters": None,   # list[float]
    "measurements": None,     # list[dict]
    "psd": None,              # dict
    "comparison": None,       # dict -- PSD comparison metrics
    "settings": {
        "bed_type": "lognormal",
        "width": 256,
        "height": 256,
        "num_grains": 50,
        "mean_diameter": 20.0,
        "std_diameter": 5.0,
        "depth_range_min": 5.0,
        "depth_range_max": 50.0,
        "seed": None,
        "segmentation_method": "watershed",
        "min_grain_size": 5,
        "smooth_sigma": 1.5,
        "min_distance": 5,
        "peak_threshold_rel": 0.15,
        "depth_edge_threshold": 2.0,
        "pixel_size": 1.0,
        "psd_method": "number",
    },
}

ws_clients: list = []


# ------------------------------------------------------------------ #
# Pydantic schemas
# ------------------------------------------------------------------ #

class GenerateRequest(BaseModel):
    """Request body for grain bed generation."""
    bed_type: str = "lognormal"
    width: int = 256
    height: int = 256
    num_grains: int = 50
    mean_diameter: float = 20.0
    std_diameter: float = 5.0
    depth_range_min: float = 5.0
    depth_range_max: float = 50.0
    seed: Optional[int] = None


class SettingsUpdate(BaseModel):
    """Partial settings update."""
    segmentation_method: Optional[str] = None
    min_grain_size: Optional[int] = None
    smooth_sigma: Optional[float] = None
    min_distance: Optional[int] = None
    peak_threshold_rel: Optional[float] = None
    depth_edge_threshold: Optional[float] = None
    pixel_size: Optional[float] = None
    psd_method: Optional[str] = None


class CalibrateRequest(BaseModel):
    """Request body for calibration.

    Either provide (point_a, point_b, known_length_mm) for reference-object
    calibration, or provide pixel_size_mm for direct pixel-size entry.
    """
    point_a: Optional[List[float]] = None
    point_b: Optional[List[float]] = None
    known_length_mm: Optional[float] = None
    pixel_size_mm: Optional[float] = None


class ComparePsdRequest(BaseModel):
    """Request body for PSD comparison with ground truth sieve data."""
    true_sizes: List[float] = Field(..., description="Sieve sizes (mm)")
    true_passing: List[float] = Field(..., description="Cumulative passing (%)")


# ------------------------------------------------------------------ #
# Helpers
# ------------------------------------------------------------------ #

def _array_to_list(arr: Optional[np.ndarray]):
    """Convert a NumPy array to a nested Python list for JSON."""
    if arr is None:
        return None
    return arr.tolist()


def _run_segmentation():
    """Run segmentation on the current depth map."""
    if state["depth"] is None:
        return

    s = state["settings"]
    depth = state["depth"]
    rgb = state["rgb"]

    if s["segmentation_method"] == "depth_edges":
        labels = segment_grains_depth_edges(
            depth,
            edge_threshold=s["depth_edge_threshold"],
            min_grain_size=s["min_grain_size"],
        )
    else:
        labels = segment_grains_watershed(
            depth,
            rgb=rgb,
            min_grain_size=s["min_grain_size"],
            smooth_sigma=s["smooth_sigma"],
            min_distance=s["min_distance"],
            peak_threshold_rel=s["peak_threshold_rel"],
        )

    state["labels"] = labels


def _run_measurements():
    """Compute per-grain measurements and PSD."""
    if state["labels"] is None or state["depth"] is None:
        return

    s = state["settings"]

    # Use calibration if calibrated; otherwise fall back to settings pixel_size
    effective_pixel_size = (
        calibration.pixel_size_mm if calibration.calibrated
        else s["pixel_size"]
    )

    measurements = measure_grains(
        state["labels"], state["depth"],
        pixel_size=effective_pixel_size,
        calibration=calibration if calibration.calibrated else None,
    )
    state["measurements"] = measurements

    diameters = [m["equiv_diameter"] for m in measurements]
    if diameters:
        state["psd"] = full_psd_analysis(diameters, method=s["psd_method"])
    else:
        state["psd"] = None


def _build_state_payload() -> dict:
    """Build a JSON-serialisable snapshot of the current state."""
    rgb = state["rgb"]
    depth = state["depth"]
    labels = state["labels"]

    # Encode images as flat lists with dimensions for the frontend
    payload = {
        "has_data": rgb is not None,
        "width": int(rgb.shape[1]) if rgb is not None else 0,
        "height": int(rgb.shape[0]) if rgb is not None else 0,
        "rgb": _array_to_list(rgb),
        "depth": _array_to_list(depth),
        "labels": _array_to_list(labels),
        "num_grains": int(labels.max()) if labels is not None and labels.size > 0 else 0,
        "true_diameters": state["true_diameters"],
        "measurements": state["measurements"],
        "psd": state["psd"],
        "comparison": state["comparison"],
        "calibration": calibration.get_state(),
        "settings": state["settings"],
    }
    return payload


async def _broadcast(msg: dict):
    """Send a JSON message to all connected WebSocket clients."""
    text = json.dumps(msg)
    dead = []
    for ws in ws_clients:
        try:
            await ws.send_text(text)
        except Exception:
            dead.append(ws)
    for ws in dead:
        ws_clients.remove(ws)


# ------------------------------------------------------------------ #
# REST endpoints
# ------------------------------------------------------------------ #

@app.get("/")
async def root():
    """Serve the single-page application."""
    return FileResponse(str(static_dir / "index.html"))


@app.post("/api/generate")
async def api_generate(req: GenerateRequest):
    """Generate a synthetic grain bed and run full analysis pipeline."""
    rgb, depth, labels_gt, true_diameters = generate_grain_bed(
        bed_type=req.bed_type,
        width=req.width,
        height=req.height,
        num_grains=req.num_grains,
        mean_diameter=req.mean_diameter,
        std_diameter=req.std_diameter,
        depth_range=(req.depth_range_min, req.depth_range_max),
        seed=req.seed,
    )

    # Update generation settings
    state["settings"].update({
        "bed_type": req.bed_type,
        "width": req.width,
        "height": req.height,
        "num_grains": req.num_grains,
        "mean_diameter": req.mean_diameter,
        "std_diameter": req.std_diameter,
        "depth_range_min": req.depth_range_min,
        "depth_range_max": req.depth_range_max,
        "seed": req.seed,
    })

    state["rgb"] = rgb
    state["depth"] = depth
    state["true_diameters"] = true_diameters

    # Run segmentation + measurement
    _run_segmentation()
    _run_measurements()

    payload = _build_state_payload()
    await _broadcast({"type": "state", "data": payload})
    return {"status": "ok", "num_grains_generated": len(true_diameters)}


@app.post("/api/segment")
async def api_segment():
    """Re-run segmentation with current settings."""
    if state["depth"] is None:
        return {"status": "error", "detail": "No depth data loaded"}

    _run_segmentation()
    _run_measurements()

    payload = _build_state_payload()
    await _broadcast({"type": "state", "data": payload})
    return {"status": "ok"}


@app.get("/api/measurements")
async def api_measurements():
    """Return per-grain measurement table."""
    return {"measurements": state["measurements"] or []}


@app.get("/api/psd")
async def api_psd():
    """Return PSD curve, percentiles, and Rosin-Rammler fit."""
    return {"psd": state["psd"]}


@app.post("/api/settings")
async def api_settings(req: SettingsUpdate):
    """Update processing parameters and re-run analysis."""
    updates = req.dict(exclude_none=True)
    state["settings"].update(updates)

    if state["depth"] is not None:
        _run_segmentation()
        _run_measurements()

    payload = _build_state_payload()
    await _broadcast({"type": "state", "data": payload})
    return {"status": "ok", "settings": state["settings"]}


@app.get("/api/state")
async def api_state():
    """Return full application state."""
    return _build_state_payload()


@app.get("/api/export/csv")
async def api_export_csv():
    """Export grain measurements as a CSV file."""
    measurements = state["measurements"] or []
    if not measurements:
        return StreamingResponse(
            io.StringIO("No data"),
            media_type="text/csv",
        )

    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=measurements[0].keys())
    writer.writeheader()
    writer.writerows(measurements)

    output.seek(0)
    return StreamingResponse(
        output,
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=grain_measurements.csv"},
    )


# ------------------------------------------------------------------ #
# Calibration endpoints
# ------------------------------------------------------------------ #

@app.post("/api/calibrate")
async def api_calibrate(req: CalibrateRequest):
    """Calibrate pixel-to-mm conversion.

    Supports two modes:
    - Reference object: provide point_a, point_b, known_length_mm
    - Direct pixel size: provide pixel_size_mm
    """
    if req.pixel_size_mm is not None:
        ok = calibration.calibrate_from_pixel_size(req.pixel_size_mm)
    elif (req.point_a is not None and req.point_b is not None
          and req.known_length_mm is not None):
        ok = calibration.calibrate_from_reference(
            req.point_a, req.point_b, req.known_length_mm,
        )
    else:
        return {"status": "error",
                "detail": "Provide pixel_size_mm or (point_a, point_b, known_length_mm)"}

    if not ok:
        return {"status": "error", "detail": "Calibration failed (zero-length reference)"}

    # Also sync the settings pixel_size to calibration value
    state["settings"]["pixel_size"] = calibration.pixel_size_mm

    # Re-run measurements with new calibration
    if state["depth"] is not None and state["labels"] is not None:
        _run_measurements()
        payload = _build_state_payload()
        await _broadcast({"type": "state", "data": payload})

    return {"status": "ok", "calibration": calibration.get_state()}


@app.get("/api/calibration")
async def api_calibration():
    """Return current calibration state."""
    return calibration.get_state()


# ------------------------------------------------------------------ #
# PSD comparison endpoint
# ------------------------------------------------------------------ #

@app.post("/api/compare-psd")
async def api_compare_psd(req: ComparePsdRequest):
    """Compare estimated PSD against ground truth sieve data.

    Returns RMSE, KS statistic, D50 comparison metrics, and the
    interpolated ground truth curve for overlay rendering.
    """
    if state["psd"] is None:
        return {"status": "error", "detail": "No PSD data available. Generate a grain bed first."}

    estimated_sizes = state["psd"]["sizes"]
    estimated_passing = state["psd"]["passing"]

    metrics = compare_psd(
        estimated_sizes, estimated_passing,
        req.true_sizes, req.true_passing,
    )

    state["comparison"] = {
        "metrics": metrics,
        "true_sizes": req.true_sizes,
        "true_passing": req.true_passing,
    }

    payload = _build_state_payload()
    await _broadcast({"type": "state", "data": payload})

    return {"status": "ok", "comparison": state["comparison"]}


# ------------------------------------------------------------------ #
# WebSocket endpoint
# ------------------------------------------------------------------ #

@app.websocket("/ws")
async def websocket_endpoint(ws: WebSocket):
    """Real-time state streaming via WebSocket."""
    await ws.accept()
    ws_clients.append(ws)
    try:
        # Send current state on connect
        payload = _build_state_payload()
        await ws.send_text(json.dumps({"type": "state", "data": payload}))

        while True:
            data = await ws.receive_text()
            msg = json.loads(data)
            # Handle client messages if needed
            if msg.get("type") == "ping":
                await ws.send_text(json.dumps({"type": "pong"}))
    except WebSocketDisconnect:
        pass
    finally:
        if ws in ws_clients:
            ws_clients.remove(ws)
