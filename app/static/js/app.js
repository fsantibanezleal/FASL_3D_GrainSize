/**
 * GrainSight -- Main application controller.
 *
 * Wires together WebSocket, UI controls, 2D renderers, and the
 * grain measurement table.  Handles user interactions and dispatches
 * API calls to the FastAPI backend.
 *
 * @module app
 */

"use strict";

document.addEventListener("DOMContentLoaded", () => {

    // -------------------------------------------------------------- //
    // DOM references
    // -------------------------------------------------------------- //
    const btnGenerate   = document.getElementById("btn-generate");
    const btnResegment  = document.getElementById("btn-resegment");
    const btnExport     = document.getElementById("btn-export");
    const btnHelp       = document.getElementById("btn-help");
    const helpModal     = document.getElementById("help-modal");
    const helpClose     = document.getElementById("help-close");
    const spinnerGen    = document.getElementById("spinner-gen");
    const spinnerSeg    = document.getElementById("spinner-seg");
    const grainTbody    = document.getElementById("grain-tbody");

    // Metric display elements
    const mGrains = document.getElementById("m-grains");
    const mD10    = document.getElementById("m-d10");
    const mD25    = document.getElementById("m-d25");
    const mD50    = document.getElementById("m-d50");
    const mD75    = document.getElementById("m-d75");
    const mD80    = document.getElementById("m-d80");
    const mD90    = document.getElementById("m-d90");
    const mRRx0   = document.getElementById("m-rr-x0");
    const mRRn    = document.getElementById("m-rr-n");
    const mRRr2   = document.getElementById("m-rr-r2");

    // Control inputs
    const ctrlBedType    = document.getElementById("ctrl-bed-type");
    const ctrlWidth      = document.getElementById("ctrl-width");
    const ctrlNumGrains  = document.getElementById("ctrl-num-grains");
    const ctrlMeanD      = document.getElementById("ctrl-mean-d");
    const ctrlStdD       = document.getElementById("ctrl-std-d");
    const ctrlSeed       = document.getElementById("ctrl-seed");
    const ctrlSegMethod  = document.getElementById("ctrl-seg-method");
    const ctrlMinGrain   = document.getElementById("ctrl-min-grain");
    const ctrlSigma      = document.getElementById("ctrl-sigma");
    const ctrlMinDist    = document.getElementById("ctrl-min-dist");
    const ctrlPeakThresh = document.getElementById("ctrl-peak-thresh");
    const ctrlPsdMethod  = document.getElementById("ctrl-psd-method");
    const ctrlPixelSize  = document.getElementById("ctrl-pixel-size");

    // -------------------------------------------------------------- //
    // State rendering
    // -------------------------------------------------------------- //

    function renderState(data) {
        if (!data || !data.has_data) return;

        // Draw images
        if (data.rgb)    Renderer2D.drawRGB("canvas-rgb", data.rgb);
        if (data.depth)  Renderer2D.drawDepth("canvas-depth", data.depth);
        if (data.labels) Renderer2D.drawLabels("canvas-labels", data.labels);

        // Draw PSD chart (with optional ground truth overlay)
        Renderer2D.drawPSD("canvas-psd", data.psd, data.comparison);

        // Update metrics bar
        mGrains.textContent = data.num_grains || "--";
        if (data.psd && data.psd.percentiles) {
            const p = data.psd.percentiles;
            mD10.textContent = p.D10 !== undefined ? p.D10.toFixed(2) : "--";
            mD25.textContent = p.D25 !== undefined ? p.D25.toFixed(2) : "--";
            mD50.textContent = p.D50 !== undefined ? p.D50.toFixed(2) : "--";
            mD75.textContent = p.D75 !== undefined ? p.D75.toFixed(2) : "--";
            mD80.textContent = p.D80 !== undefined ? p.D80.toFixed(2) : "--";
            mD90.textContent = p.D90 !== undefined ? p.D90.toFixed(2) : "--";
        }
        if (data.psd && data.psd.rosin_rammler) {
            const rr = data.psd.rosin_rammler;
            mRRx0.textContent = isNaN(rr.x0) ? "--" : rr.x0.toFixed(2);
            mRRn.textContent  = isNaN(rr.n)  ? "--" : rr.n.toFixed(2);
            mRRr2.textContent = isNaN(rr.r_squared) ? "--" : rr.r_squared.toFixed(3);
        }

        // Update grain table
        updateTable(data.measurements);

        // Update calibration status
        if (data.calibration) updateCalibStatus(data.calibration);

        // Update comparison results
        if (data.comparison && data.comparison.metrics) {
            showComparisonResults(data.comparison.metrics);
        }
    }

    function updateTable(measurements) {
        if (!grainTbody) return;
        grainTbody.innerHTML = "";

        if (!measurements || measurements.length === 0) {
            const tr = document.createElement("tr");
            tr.innerHTML = `<td colspan="6" style="text-align:center;color:#8b949e">No grains</td>`;
            grainTbody.appendChild(tr);
            return;
        }

        for (const m of measurements) {
            const tr = document.createElement("tr");
            tr.innerHTML = `
                <td>${m.id}</td>
                <td>${m.equiv_diameter.toFixed(2)}</td>
                <td>${m.area_px}</td>
                <td>${m.aspect_ratio.toFixed(2)}</td>
                <td>${m.circularity.toFixed(3)}</td>
                <td>${m.volume.toFixed(1)}</td>
            `;
            grainTbody.appendChild(tr);
        }
    }

    // -------------------------------------------------------------- //
    // API calls
    // -------------------------------------------------------------- //

    async function apiGenerate() {
        spinnerGen.classList.add("active");
        btnGenerate.disabled = true;

        const body = {
            bed_type: ctrlBedType.value,
            width: parseInt(ctrlWidth.value) || 256,
            height: parseInt(ctrlWidth.value) || 256,
            num_grains: parseInt(ctrlNumGrains.value) || 50,
            mean_diameter: parseFloat(ctrlMeanD.value) || 20,
            std_diameter: parseFloat(ctrlStdD.value) || 5,
            depth_range_min: 5.0,
            depth_range_max: 50.0,
            seed: ctrlSeed.value ? parseInt(ctrlSeed.value) : null,
        };

        try {
            const resp = await fetch("/api/generate", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify(body),
            });
            if (!resp.ok) console.error("Generate failed:", resp.status);
        } catch (e) {
            console.error("Generate error:", e);
        } finally {
            spinnerGen.classList.remove("active");
            btnGenerate.disabled = false;
        }
    }

    async function apiResegment() {
        spinnerSeg.classList.add("active");
        btnResegment.disabled = true;

        const settings = {
            segmentation_method: ctrlSegMethod.value,
            min_grain_size: parseInt(ctrlMinGrain.value) || 5,
            smooth_sigma: parseFloat(ctrlSigma.value) || 1.5,
            min_distance: parseInt(ctrlMinDist.value) || 5,
            peak_threshold_rel: parseFloat(ctrlPeakThresh.value) || 0.15,
            psd_method: ctrlPsdMethod.value,
            pixel_size: parseFloat(ctrlPixelSize.value) || 1.0,
        };

        try {
            const resp = await fetch("/api/settings", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify(settings),
            });
            if (!resp.ok) console.error("Settings failed:", resp.status);
        } catch (e) {
            console.error("Settings error:", e);
        } finally {
            spinnerSeg.classList.remove("active");
            btnResegment.disabled = false;
        }
    }

    // -------------------------------------------------------------- //
    // Event handlers
    // -------------------------------------------------------------- //

    btnGenerate.addEventListener("click", apiGenerate);
    btnResegment.addEventListener("click", apiResegment);

    btnExport.addEventListener("click", () => {
        window.open("/api/export/csv", "_blank");
    });

    btnHelp.addEventListener("click", () => {
        helpModal.classList.add("active");
    });

    helpClose.addEventListener("click", () => {
        helpModal.classList.remove("active");
    });

    helpModal.addEventListener("click", (e) => {
        if (e.target === helpModal) helpModal.classList.remove("active");
    });

    // Also re-segment when PSD method or pixel size change
    ctrlPsdMethod.addEventListener("change", apiResegment);

    // -------------------------------------------------------------- //
    // Calibration controls
    // -------------------------------------------------------------- //
    const btnCalibPixelSize = document.getElementById("btn-calib-pixel-size");
    const btnCalibReference = document.getElementById("btn-calib-reference");
    const calibStatus       = document.getElementById("calib-status");

    if (btnCalibPixelSize) {
        btnCalibPixelSize.addEventListener("click", async () => {
            const px = parseFloat(document.getElementById("ctrl-calib-pixel-size").value);
            if (isNaN(px) || px <= 0) return;
            try {
                const resp = await fetch("/api/calibrate", {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({ pixel_size_mm: px }),
                });
                const data = await resp.json();
                if (data.calibration) updateCalibStatus(data.calibration);
            } catch (e) { console.error("Calibration error:", e); }
        });
    }

    if (btnCalibReference) {
        btnCalibReference.addEventListener("click", async () => {
            const parsePoint = (s) => s.split(",").map(Number);
            const pa = parsePoint(document.getElementById("ctrl-calib-point-a").value);
            const pb = parsePoint(document.getElementById("ctrl-calib-point-b").value);
            const len = parseFloat(document.getElementById("ctrl-calib-length").value);
            if (pa.length !== 2 || pb.length !== 2 || isNaN(len)) return;
            try {
                const resp = await fetch("/api/calibrate", {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({ point_a: pa, point_b: pb, known_length_mm: len }),
                });
                const data = await resp.json();
                if (data.calibration) updateCalibStatus(data.calibration);
            } catch (e) { console.error("Calibration error:", e); }
        });
    }

    function updateCalibStatus(cal) {
        if (calibStatus) {
            calibStatus.textContent = cal.calibrated
                ? `Calibrated (${cal.pixel_size_mm.toFixed(4)} mm/px)`
                : "Uncalibrated";
        }
    }

    // -------------------------------------------------------------- //
    // Sieve data comparison
    // -------------------------------------------------------------- //
    const btnComparePsd   = document.getElementById("btn-compare-psd");
    const comparisonDiv   = document.getElementById("comparison-results");

    if (btnComparePsd) {
        btnComparePsd.addEventListener("click", async () => {
            const sizesStr  = document.getElementById("ctrl-sieve-sizes").value;
            const passStr   = document.getElementById("ctrl-sieve-passing").value;
            if (!sizesStr || !passStr) return;
            const trueSizes   = sizesStr.split(",").map(Number);
            const truePassing = passStr.split(",").map(Number);
            if (trueSizes.some(isNaN) || truePassing.some(isNaN)) return;
            try {
                const resp = await fetch("/api/compare-psd", {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({ true_sizes: trueSizes, true_passing: truePassing }),
                });
                const data = await resp.json();
                if (data.comparison && data.comparison.metrics) {
                    showComparisonResults(data.comparison.metrics);
                }
            } catch (e) { console.error("Compare PSD error:", e); }
        });
    }

    function showComparisonResults(m) {
        if (!comparisonDiv) return;
        comparisonDiv.innerHTML = `
            RMSE: ${m.rmse.toFixed(2)}%<br>
            KS stat: ${m.ks_statistic.toFixed(2)}%<br>
            D50 est: ${m.estimated_d50.toFixed(2)} | true: ${m.true_d50.toFixed(2)}<br>
            D50 rel. error: ${(m.d50_relative_error * 100).toFixed(1)}%
        `;
    }

    // Handle window resize
    window.addEventListener("resize", () => {
        // Re-render from the last known state via a fresh state fetch
        fetch("/api/state")
            .then(r => r.json())
            .then(data => renderState(data))
            .catch(() => {});
    });

    // -------------------------------------------------------------- //
    // WebSocket: receive state updates
    // -------------------------------------------------------------- //

    GrainWS.onMessage((msg) => {
        if (msg.type === "state" && msg.data) {
            renderState(msg.data);
        }
    });

    GrainWS.connect();
});
