# User Guide -- GrainSight

This guide walks through the typical **Generate -> Segment -> Calibrate -> Export**
workflow, explains how to pick a segmentation method and weights, how to read
D-values and Rosin-Rammler fits, and how to compare a measured PSD with
reference sieve data.

Screenshots reference the default frontend captured in
`docs/png/frontend.png`.

---

## 1. Starting the app

```bash
python run_app.py
# open http://127.0.0.1:8010
```

The left panel hosts the control surface (generation, segmentation,
calibration, export). The centre shows the RGB image, depth map, label
overlay, and 3D surface. The right panel shows the PSD curve and the
per-grain measurement table.

Connection status is shown by the "Connected" dot in the header — a green
indicator means the WebSocket channel is open and the server will push state
updates live as you generate or re-segment.

![Frontend](png/frontend.png)

---

## 2. Generate -> Segment -> Calibrate -> Export workflow

### 2.1 Generate a synthetic bed

Use the **Generation** panel to pick:

| Control | What it does |
|---------|--------------|
| `Distribution` | `uniform`, `normal`, `lognormal`, `bimodal`, `rosin_rammler` |
| `Mean diameter` | Target mean grain size (pixels or mm once calibrated) |
| `Std / n` | Standard deviation — or, for `rosin_rammler`, the uniformity index _n_ |
| `Count` | Target number of grains |
| `Seed` | RNG seed for reproducibility |
| `Resolution` | Image size in pixels |

Click **Generate**. The backend produces:

- `rgb` — colour image (shaded grains on a dark background)
- `depth` — height map in normalised units
- `labels` — ground-truth integer label map (one label per grain)

These are broadcast to the browser over `/ws` and rendered on the 2D and 3D
canvases.

### 2.2 Run segmentation

The **Segmentation** panel chooses how the app segments grains. Three
methods are available:

| Method | Input used | Best for |
|--------|-----------|----------|
| `watershed` | depth only | Controlled lab beds with clear gradients |
| `depth_edges` | depth edges + morphology | Scenes with strong per-grain rims |
| `rgbd` | depth gradient + colour gradient (linearly combined) | General muck piles with both textural and geometric cues |

Picking a method:

- **Start with `rgbd`** for any realistic bed. It fuses geometric (depth)
  and textural (colour) information and is the most forgiving.
- **Fall back to `watershed`** if colour is unreliable (flat lighting,
  monochromatic scene).
- **Use `depth_edges`** on scenes where grain boundaries are very sharp but
  grain bodies are textureless.

### 2.3 Tune RGB-D weights

When `rgbd` is selected, two sliders control the fusion ratio:

- `depth_weight` (default 0.6) — contribution of the depth gradient
- `color_weight` (default 0.4) — contribution of the colour gradient

The two sliders are linked: they always sum to 1.0. Rules of thumb:

| Scene | Recommended weights |
|-------|--------------------|
| Conveyor belt with uniform lighting | `depth=0.7`, `color=0.3` |
| Natural surface with varying texture | `depth=0.5`, `color=0.5` |
| Wet/glossy ore | `depth=0.8`, `color=0.2` (reflections hurt colour) |

Extra watershed/edge parameters:

- `min_distance` — minimum spacing between seeds; raise it to merge
  over-segmented grains.
- `sigma` — Gaussian pre-smoothing; 1.5–2.5 works for typical images.
- `compactness` — higher values produce more regular regions.

Click **Re-segment** after changing parameters to update the label map
without regenerating the bed.

### 2.4 Calibrate pixels to millimetres

The **Calibration** panel converts pixel measurements to physical units.

Two modes are supported:

- **Reference object**: click/enter the pixel length of a known object (for
  example a coin or a scale bar) and its real-world length in millimetres.
  `pixel_size_mm` is computed as `real_mm / pixels`.
- **Direct scale entry**: enter `pixel_size_mm` directly when the camera
  intrinsics are known.

Once calibrated, every diameter, axis length and volume in the measurement
table is re-expressed in mm / mm^3. Un-calibrated runs keep the pixel units
so you can still inspect the distribution shape.

### 2.5 Export

The **Export** button triggers `GET /api/export/csv` and downloads one row
per grain with all 18 ISO 13322-1 descriptors. Columns include
`label`, `area`, `equivalent_diameter`, `major_axis`, `minor_axis`,
`aspect_ratio`, `circularity`, `perimeter`, `bbox_*`, `centroid_*`,
`depth_mean`, `depth_std`, `volume`, `surface_area_3d`.

The CSV is suitable for downstream tools (Excel, pandas, R) and preserves
whatever calibration was active at the moment of export.

---

## 3. Interpreting D-values and Rosin-Rammler fits

### 3.1 D-values

The PSD chart exposes six cumulative percentiles:

| D-value | Meaning |
|---------|---------|
| D10 | Effective size — hydraulic conductivity proxy |
| D25 | Lower quartile |
| D50 | Median — the headline grain size |
| D75 | Upper quartile |
| D80 | Comminution circuit design size (Bond work index) |
| D90 | Downstream equipment sizing |

A healthy run for a well-mixed bed typically shows
`D90 / D10 ~ 3 – 8`. Very wide spreads (>10) usually mean under-segmentation
(few large merged grains) — re-segment with `min_distance` raised.

### 3.2 Rosin-Rammler fit

`granulometry.py` fits `R(x) = 1 - exp(-(x / x0)^n)` via `scipy.curve_fit`
with `n ∈ [0.5, 5]`. The fit returns:

| Parameter | Meaning |
|-----------|---------|
| `x0` | Characteristic size — diameter at 63.2% passing |
| `n` | Uniformity index — shape of the distribution |
| `r2` | Coefficient of determination of the fit |

Reading `n`:

- `n > 3` — narrow distribution (tightly graded material, product of
  screening)
- `1.5 <= n <= 3` — typical crushed rock / blast muck pile
- `n < 1.5` — broad distribution (poorly graded, wide range of sizes)

`r2 > 0.95` indicates the sample really does follow Rosin-Rammler. Lower
values suggest a bimodal bed (try the `bimodal` generator for comparison).

---

## 4. PSD comparison with sieve data

Use `POST /api/settings` (or the **Comparison** section of the UI) to load a
sieve dataset as `{mesh_mm, cum_pct_passing}` pairs. The backend computes:

| Metric | What it tells you |
|--------|-------------------|
| `RMSE` | Root-mean-squared error between measured and reference cumulative passing curves |
| `KS statistic` | Maximum absolute difference (Kolmogorov-Smirnov) |
| `D50 error` | Relative error at the median |

Good agreement for image-based granulometry on crushed ore is
`RMSE < 5 %`, `KS < 0.08`, `|ΔD50| < 10 %`. Larger errors usually trace
back to:

- Missed fines (grains below the min-size filter) — lower the
  `min_grain_area` threshold.
- Over-merged coarse grains — raise `min_distance` in segmentation.
- Calibration drift — re-run **Calibration** against a fresh reference.

---

## 5. Typical recipes

**Recipe A — Lab bed of crushed granite.** `rgbd`, weights (0.7, 0.3),
`sigma=2.0`, `min_distance=15`. Expect `D50 ≈ mean_d`,
`n ≈ 2.0 - 2.5`.

**Recipe B — Conveyor with fine dust.** `rgbd`, weights (0.5, 0.5),
`sigma=1.5`, `min_distance=10`, raise `min_grain_area` to 40 px to suppress
noise.

**Recipe C — Bimodal blast muck pile.** Generate with `bimodal`, segment
with `rgbd` (0.6, 0.4), compare against sieve data; expect `RMSE < 6 %`
and `r2 < 0.95` on the Rosin-Rammler fit (the single-mode model
under-fits).

---

## 6. Further reading

- [Architecture](architecture.md) — system overview and data flow
- [Granulometry theory](granulometry_theory.md) — PSD, D-values, Rosin-Rammler
- [Segmentation theory](segmentation_theory.md) — watershed, depth edges, RGB-D fusion
- [Development history](development_history.md) — changelog
- [References](references.md) — academic papers and standards
