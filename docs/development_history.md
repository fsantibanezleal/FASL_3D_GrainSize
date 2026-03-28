# Development History -- GrainSight

## v2.0.0 (2026-03-28)

**Full implementation of the GrainSight 3D Particle Size & Granulometry Analyzer.**

### Core Features
- Synthetic grain bed generation with 5 distribution types:
  uniform, normal, log-normal, bimodal, Rosin-Rammler.
- Ellipsoidal grain model with realistic depth profiles:
  `z(x,y) = z_peak * sqrt(max(0, 1 - (x-cx)^2/a^2 - (y-cy)^2/b^2))`.
- Greedy circle-packing placement with configurable overlap tolerance.
- RGB colouring with Lambertian-like edge shading.

### Segmentation
- Marker-based watershed segmentation on depth gradient magnitude.
- Local maxima peak detection for foreground markers.
- Optional RGB gradient blending for boundary refinement.
- Depth-edge segmentation as simpler alternative method.
- Small-fragment merging post-processing with contiguous re-labelling.

### Measurement
- 18 per-grain geometric descriptors including equivalent diameter,
  PCA-based major/minor axes, circularity, and depth-integrated volume.
- Base plane estimation via least-squares planar fit from surrounding pixels.

### Granulometry
- Cumulative PSD curve (number-weighted and mass-weighted).
- D-value extraction (D10, D25, D50, D75, D80, D90) by interpolation.
- Rosin-Rammler distribution fitting via non-linear least squares:
  `F(x) = 1 - exp(-(x/x0)^n)`.
- Simulated sieve analysis using ISO 565 standard sieve series.
- Complete analysis pipeline returning curves + histogram + percentiles.

### Frontend
- Dark theme with amber/gold accent colour scheme.
- 3-panel image display: RGB, depth (pseudocolour), segmented labels.
- Interactive PSD chart with cumulative curve, histogram, and Dx markers.
- Real-time grain measurement table with sorting.
- Comprehensive help modal explaining granulometry, D-values, and algorithms.
- Tooltips on all controls describing parameter effects.
- WebSocket-based real-time state synchronisation.

### API
- `POST /api/generate` -- synthetic grain bed generation.
- `POST /api/segment` -- re-run segmentation with current settings.
- `GET /api/measurements` -- per-grain measurement table.
- `GET /api/psd` -- PSD curve, percentiles, Rosin-Rammler fit.
- `POST /api/settings` -- update processing parameters.
- `GET /api/state` -- full state snapshot.
- `GET /api/export/csv` -- export measurements as CSV.
- `WS /ws` -- real-time state broadcast.

### Infrastructure
- FastAPI + Uvicorn on port 8010.
- PyInstaller build spec and PowerShell build script.
- Comprehensive test suite for all core modules.
- Full documentation: theory, architecture, references.
