# GrainSight -- 3D Particle Size & Granulometry Analyzer

A web-based application for grain size estimation from RGB-D data using
marker-based watershed segmentation, per-grain geometric measurement,
and Rosin-Rammler PSD curve fitting.

## Features

- **Synthetic grain bed generation** with 5 distribution types: uniform,
  normal, log-normal, bimodal, and Rosin-Rammler.
- **Marker-based watershed segmentation** using depth gradient magnitude.
- **18 per-grain metrics**: equivalent diameter, major/minor axes, aspect
  ratio, circularity, depth-integrated volume, and more.
- **PSD analysis**: cumulative curves (number and mass weighted), D-values
  (D10/D25/D50/D75/D80/D90), Rosin-Rammler fit, and sieve simulation.
- **Real-time web UI** with dark theme, interactive controls, PSD chart,
  and measurement table.
- **CSV export** of grain measurements.

## Quick Start

```bash
cd "d:/_Repos/_SCIENCE/FASL_3D_GrainSize"
python -m venv .venv
source .venv/Scripts/activate    # Windows: .venv\Scripts\activate
pip install -r requirements.txt
python run_app.py
```

Open http://127.0.0.1:8010 in your browser.

## Running Tests

```bash
python tests/test_generator.py
python tests/test_segmentation.py
python tests/test_measurement.py
python tests/test_granulometry.py
```

## Building Standalone Executable

```powershell
.\Build_PyInstaller.ps1
```

## Technology Stack

- **Backend**: Python, FastAPI, Uvicorn, NumPy, SciPy, scikit-image
- **Frontend**: Vanilla JavaScript, HTML5 Canvas, CSS3
- **Protocol**: REST + WebSocket
- **Packaging**: PyInstaller

## Documentation

- [Architecture](docs/architecture.md)
- [Granulometry Theory](docs/granulometry_theory.md)
- [Development History](docs/development_history.md)
- [References](docs/references.md)

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/generate` | Generate synthetic grain bed |
| POST | `/api/segment` | Re-run grain segmentation |
| GET | `/api/measurements` | Per-grain measurement table |
| GET | `/api/psd` | PSD curve + percentiles + R-R fit |
| POST | `/api/settings` | Update processing parameters |
| GET | `/api/state` | Full state snapshot |
| GET | `/api/export/csv` | Export measurements as CSV |
| WS | `/ws` | Real-time state streaming |

## License

Research use. FASL Lab.
