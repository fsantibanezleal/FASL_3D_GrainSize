# Architecture -- GrainSight

## System Overview

GrainSight is a single-page web application built with **FastAPI** (Python)
and a vanilla JavaScript frontend. The application performs grain size
analysis from RGB-D data using image processing algorithms.

```
Browser (SPA)                 FastAPI Server (port 8010)
+---------------------+      +----------------------------+
| index.html          | HTTP | /api/generate              |
| app.js              |----->| /api/segment               |
| renderer2d.js       |      | /api/measurements          |
| renderer3d.js       |      | /api/psd                   |
| websocket.js        | WS   | /api/settings              |
|                     |<---->| /ws (state broadcast)      |
+---------------------+      +----------------------------+
                                        |
                              +---------v---------+
                              |  Simulation Core  |
                              |  grain_generator  |
                              |  segmentation     |
                              |  grain_measurement|
                              |  granulometry     |
                              |  depth_features   |
                              |  volume_estimation|
                              +-------------------+
```

## Data Flow Pipeline

1. **Generation**: `grain_generator.py` creates synthetic RGB-D images with
   ground-truth labels and known grain diameters.

2. **Segmentation**: `segmentation.py` processes the depth map through
   the watershed pipeline to produce a label image.

3. **Measurement**: `grain_measurement.py` computes geometric properties
   (area, diameter, axes, circularity, volume) for each labelled grain.

4. **Granulometry**: `granulometry.py` computes the PSD curve, extracts
   D-values, fits Rosin-Rammler, and simulates sieve analysis.

5. **Broadcast**: The full state (images + measurements + PSD) is sent
   to all connected WebSocket clients for real-time rendering.

## Module Responsibilities

| Module | Purpose |
|--------|---------|
| `main.py` | FastAPI app, endpoints, WebSocket, state management |
| `grain_generator.py` | Synthetic grain bed generation (ellipsoid-based) |
| `segmentation.py` | Marker-based watershed + depth-edge segmentation |
| `grain_measurement.py` | Per-grain geometric descriptors |
| `granulometry.py` | PSD curves, D-values, Rosin-Rammler fitting |
| `depth_features.py` | Gradient, peak detection, roughness |
| `volume_estimation.py` | Depth integration, base plane fitting |

## Frontend Architecture

The frontend consists of four JavaScript modules:

- **websocket.js**: WebSocket connection with auto-reconnect.
- **renderer2d.js**: Canvas-based rendering of RGB, depth, labels, PSD chart.
- **renderer3d.js**: Isometric wireframe surface rendering (placeholder for Three.js).
- **app.js**: Application controller, event handling, API calls.

## Technology Stack

- **Backend**: Python 3.10+, FastAPI, Uvicorn, NumPy, SciPy, scikit-image, Pillow
- **Frontend**: Vanilla JS (ES6+), HTML5 Canvas, CSS3 custom properties
- **Protocol**: REST + WebSocket for real-time state sync
- **Packaging**: PyInstaller for standalone executable
