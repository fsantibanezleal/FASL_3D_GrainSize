# Development History -- GrainSight

## v2.1.1 (2026-04-18)

**Docs and deployment hygiene.**

- New `docs/user_guide.md` covering the Generate -> Segment -> Calibrate ->
  Export workflow, how to pick a segmentation method and weights, how to
  read D-values and Rosin-Rammler fits, and PSD comparison with sieve
  data. Linked from README Documentation section.
- README `## Port` promoted to `### Port Assignment` with an explicit
  link to the CAOS_MANAGE Hetzner VPS port ledger, per
  project-quality-standards Part 3 step 15.
- Project-structure tree in README now lists `user_guide.md` and
  `segmentation_theory.md`.

## v2.1.0 (2026-04-18)

**RGB-D fusion segmentation integrated end-to-end.**

### Segmentation
- New `segment_grains_rgbd(depth, rgb, depth_weight, color_weight, ...)`
  producing a fused gradient `w_d * |nabla z|_n + w_c * |nabla I|_n`
  and running watershed on the combined surface.
- Markers continue to be derived from smoothed depth peaks -- retains
  the "one peak per grain" property while letting colour refine boundaries.
- Two new tests (`test_rgbd_segmentation_output`,
  `test_rgbd_segmentation_weight_effect`) bring the suite to 52 passing.

### Frontend
- Segmentation method dropdown now includes `RGB-D fusion`.
- Two linked sliders (`Depth weight`, `Color weight`) expose the
  fusion coefficients; moving either keeps `w_d + w_c = 1`.
- Sliders only render when the `rgbd` method is selected.
- Help modal documents recommended weight regimes.

### Docs
- New `docs/segmentation_theory.md` -- full derivation of all three
  segmentation methods, when to use each, and parameter effects.
- New `docs/svg/segmentation-pipeline.svg` -- diagram of the depth
  and RGB-D watershed paths.
- README reorganised: features call out the three methods; docs
  index links segmentation theory; pipeline SVG embedded.

### Backend
- `SettingsUpdate` schema and default `state["settings"]` include
  `depth_weight` and `color_weight`.
- Settings endpoint forwards the new fields to `segment_grains_rgbd`.

### Deployment
- Added `passenger_wsgi.py` for cPanel Passenger ASGI deployment.

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
