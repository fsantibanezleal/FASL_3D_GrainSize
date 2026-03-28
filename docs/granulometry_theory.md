# Granulometry Theory -- GrainSight

## 1. Particle Size Distribution (PSD)

A **Particle Size Distribution** (PSD) describes the relative amounts of particles at
each size class in a sample. It is fundamental in mineral processing, geotechnical
engineering, and sedimentology.

### 1.1 Number-Weighted PSD

The cumulative fraction of particles finer than size _x_:

$$F_N(x) = \frac{\#\{d_i \le x\}}{N}$$

where _N_ is the total number of particles and _d_i_ are the individual diameters.

### 1.2 Mass-Weighted PSD

Assuming constant density and spherical particles, mass is proportional to _d^3_:

$$F_M(x) = \frac{\sum_{d_i \le x} d_i^3}{\sum d_i^3}$$

Mass-weighted distributions emphasise coarse particles more than number-weighted ones.

---

## 2. Characteristic D-Values

D-values (percentiles) are extracted by interpolating the cumulative PSD curve:

| Symbol | Meaning | Typical Application |
|--------|---------|---------------------|
| D10    | 10% passing | Effective size (filtration, hydraulic conductivity) |
| D25    | 25% passing | Quartile boundary |
| D50    | 50% passing (median) | General characterisation |
| D75    | 75% passing | Quartile boundary |
| D80    | 80% passing | Comminution circuit design (Bond work index) |
| D90    | 90% passing | Downstream equipment sizing |

---

## 3. Rosin-Rammler Distribution

The Rosin-Rammler (Weibull) model, introduced by Rosin & Rammler (1933), is the
standard model for describing blast fragmentation and crushed rock:

### 3.1 Cumulative Passing

$$F(x) = 1 - \exp\!\left[-\left(\frac{x}{x_0}\right)^n\right]$$

### 3.2 Cumulative Retained

$$R(x) = \exp\!\left[-\left(\frac{x}{x_0}\right)^n\right]$$

### 3.3 Parameters

- **x_0** (characteristic size): the size at which 63.2% of the material passes.
  Computed from: _F(x_0) = 1 - exp(-1) = 0.632_.
- **n** (uniformity index): controls the width/spread of the distribution.
  - n < 1: very broad distribution (poorly sorted)
  - n ~ 1: typical for blasted rock
  - n = 2-4: well-graded crushed aggregate
  - n > 5: very uniform (nearly single-sized)

### 3.4 Linearisation

Taking double logarithms:

$$\ln\!\bigl[-\ln(1 - F)\bigr] = n \ln(x) - n \ln(x_0)$$

This yields a straight line with slope _n_ and intercept _-n ln(x_0)_.

### 3.5 Probability Density Function

$$f(x) = \frac{n}{x_0}\left(\frac{x}{x_0}\right)^{n-1}\exp\!\left[-\left(\frac{x}{x_0}\right)^n\right]$$

---

## 4. Equivalent Diameter

Since grains are rarely spherical, various equivalent diameters are used:

### 4.1 Equivalent Circular Area Diameter

$$d_{\text{eq}} = 2\sqrt{\frac{A}{\pi}}$$

The diameter of a circle with the same area _A_ as the grain's projected footprint.

### 4.2 Feret Diameter

The distance between two parallel tangent lines to the grain boundary. The maximum
Feret diameter approximates the sieve-passing size.

### 4.3 Major and Minor Axes (PCA)

Principal Component Analysis of the grain's pixel coordinates yields the major and
minor axis lengths. The aspect ratio is:

$$\text{AR} = \frac{a_{\text{major}}}{a_{\text{minor}}}$$

---

## 5. Circularity and Shape Factors

### 5.1 Circularity (Haralick)

$$C = \frac{4\pi A}{P^2}$$

where _P_ is the perimeter. A perfect circle yields _C_ = 1; elongated or
irregular grains have _C_ < 1.

### 5.2 Sphericity (3D)

When volume _V_ and surface area _S_ are available:

$$\Psi = \frac{\pi^{1/3}(6V)^{2/3}}{S}$$

---

## 6. Sieve Analysis

Physical sieve analysis passes a sample through a stack of sieves with
progressively finer openings. The standard sieve series (ISO 565:1990):

| Opening (mm) |
|--------------|
| 0.075, 0.15, 0.3, 0.6, 1.18, 2.36, 4.75, 9.5, 19, 37.5, 50, 75, 100 |

GrainSight simulates sieve analysis by classifying each grain's equivalent
diameter into the appropriate sieve fraction.

---

## 7. Watershed Segmentation Algorithm

The marker-based watershed algorithm treats the depth gradient magnitude as a
topographic surface:

1. **Pre-processing**: Gaussian smoothing (sigma-adjustable) suppresses noise.
2. **Gradient**: Sobel operators compute |nabla z| = sqrt((dz/dx)^2 + (dz/dy)^2).
3. **Markers**: Local maxima of the depth map identify grain peaks.
4. **Flooding**: The watershed transform floods from markers, building boundaries
   where flood fronts from different basins meet.
5. **Merging**: Small fragments (< min_grain_size pixels) are merged into neighbours.

### 7.1 Depth-Based vs. Intensity-Based Segmentation

Traditional image-based fragmentation software (WipFrag, Split Desktop, GoldSize)
uses 2D edge detection on colour/intensity images. GrainSight's depth-based approach
offers advantages:

- **Depth discontinuities** at grain boundaries are more reliable than colour edges.
- **Overlapping grains** can be separated by depth ordering (painter's algorithm).
- **Volume estimation** is possible from the depth profile.
- **Reduced sensitivity** to lighting conditions and grain colour similarity.

---

## 8. Volume Estimation from Depth

For each segmented grain, the volume is estimated by integrating depth above the
base plane:

$$V = \sum_{(x,y) \in \Omega} \bigl[z(x,y) - z_{\text{base}}(x,y)\bigr] \Delta x \, \Delta y$$

The base plane is estimated from pixels surrounding the grain using a least-squares
planar fit:

$$z_{\text{base}}(x, y) = ax + by + c$$

The equivalent-sphere diameter from volume:

$$d_{\text{sphere}} = \left(\frac{6V}{\pi}\right)^{1/3}$$

---

## 9. References

1. Rosin, P. & Rammler, E. (1933). The laws governing the fineness of powdered coal. _J. Inst. Fuel_, 7, 29-36.
2. Bond, F.C. (1952). The third theory of comminution. _Trans. AIME_, 193, 484-494.
3. Beucher, S. & Lantuejoul, C. (1979). Use of watersheds in contour detection.
4. Meyer, F. (1994). Topographic distance and watershed lines.
5. Thurley, M. & Ng, K. (2008). Identification and sizing of the entirely visible rocks from 3D surface data.
6. ISO 13322-1:2014. Particle size analysis -- Image analysis methods.
7. ISO 565:1990. Test sieves -- Metal wire cloth, perforated metal plate and electroformed sheet.
8. Maerz, N.H. & Zhou, W. (1998). WipFrag image-based granulometry system.
9. Mora, C.F. & Kwan, A.K.H. (2000). Sphericity, shape factor, and convexity measurement of coarse aggregate.
