/**
 * GrainSight -- 2D Canvas renderers for images and PSD chart.
 *
 * Renders:
 *  - RGB grain bed image
 *  - Depth map (pseudocolour heat-map)
 *  - Segmented label image (random colours per grain)
 *  - PSD cumulative curve + histogram + Dx markers
 *
 * All canvases auto-resize to their container.
 *
 * @module renderer2d
 */

"use strict";

const Renderer2D = (() => {

    // -------------------------------------------------------------- //
    // Label colour palette (deterministic from label index)
    // -------------------------------------------------------------- //
    const PALETTE = [];
    (function _buildPalette() {
        const hueStep = 37;  // golden-angle-ish
        for (let i = 0; i < 256; i++) {
            const h = (i * hueStep) % 360;
            const s = 60 + (i * 7) % 30;
            const l = 45 + (i * 11) % 20;
            PALETTE.push(`hsl(${h}, ${s}%, ${l}%)`);
        }
    })();

    function _labelColour(idx) {
        if (idx <= 0) return [30, 30, 30];
        const h = ((idx * 37) % 360) / 360;
        const s = 0.6 + ((idx * 7) % 30) / 100;
        const l = 0.45 + ((idx * 11) % 20) / 100;
        return _hslToRgb(h, s, l);
    }

    function _hslToRgb(h, s, l) {
        let r, g, b;
        if (s === 0) { r = g = b = l; }
        else {
            const hue2rgb = (p, q, t) => {
                if (t < 0) t += 1; if (t > 1) t -= 1;
                if (t < 1/6) return p + (q - p) * 6 * t;
                if (t < 1/2) return q;
                if (t < 2/3) return p + (q - p) * (2/3 - t) * 6;
                return p;
            };
            const q = l < 0.5 ? l * (1 + s) : l + s - l * s;
            const p = 2 * l - q;
            r = hue2rgb(p, q, h + 1/3);
            g = hue2rgb(p, q, h);
            b = hue2rgb(p, q, h - 1/3);
        }
        return [Math.round(r * 255), Math.round(g * 255), Math.round(b * 255)];
    }

    // -------------------------------------------------------------- //
    // Depth pseudocolour (Inferno-like)
    // -------------------------------------------------------------- //
    function _depthColour(val, minD, maxD) {
        const t = maxD > minD ? (val - minD) / (maxD - minD) : 0;
        // Simplified inferno palette
        const r = Math.round(255 * Math.min(1, t * 3));
        const g = Math.round(255 * Math.max(0, Math.min(1, (t - 0.33) * 3)));
        const b = Math.round(255 * Math.max(0, Math.min(1, (t - 0.66) * 3)));
        if (val <= 0) return [10, 10, 20];
        return [
            Math.round(Math.min(255, 10 + t * 200 + (1-t) * 20)),
            Math.round(Math.min(255, 10 + Math.pow(t, 1.5) * 220)),
            Math.round(Math.min(255, 60 + (1 - t) * 150 + t * 30))
        ];
    }

    // -------------------------------------------------------------- //
    // Canvas setup helper
    // -------------------------------------------------------------- //
    function _fitCanvas(canvas) {
        const rect = canvas.parentElement.getBoundingClientRect();
        // Account for the panel title bar
        const titleEl = canvas.parentElement.querySelector(".panel-title");
        const titleH = titleEl ? titleEl.offsetHeight : 0;
        canvas.width = Math.floor(rect.width);
        canvas.height = Math.floor(rect.height - titleH);
    }

    // -------------------------------------------------------------- //
    // Image renderers
    // -------------------------------------------------------------- //

    /**
     * Draw an RGB image onto a canvas, scaled to fit.
     * @param {string} canvasId - Canvas element id.
     * @param {number[][]} rgbData - 3D array [H][W][3] of uint8.
     */
    function drawRGB(canvasId, rgbData) {
        const canvas = document.getElementById(canvasId);
        if (!canvas || !rgbData || rgbData.length === 0) return;
        _fitCanvas(canvas);

        const ctx = canvas.getContext("2d");
        const H = rgbData.length;
        const W = rgbData[0].length;
        const imgData = ctx.createImageData(W, H);

        for (let y = 0; y < H; y++) {
            for (let x = 0; x < W; x++) {
                const i = (y * W + x) * 4;
                imgData.data[i]     = rgbData[y][x][0];
                imgData.data[i + 1] = rgbData[y][x][1];
                imgData.data[i + 2] = rgbData[y][x][2];
                imgData.data[i + 3] = 255;
            }
        }

        // Scale to fit canvas
        const offscreen = new OffscreenCanvas(W, H);
        const offCtx = offscreen.getContext("2d");
        offCtx.putImageData(imgData, 0, 0);

        ctx.clearRect(0, 0, canvas.width, canvas.height);
        ctx.imageSmoothingEnabled = false;

        const scale = Math.min(canvas.width / W, canvas.height / H);
        const dx = (canvas.width - W * scale) / 2;
        const dy = (canvas.height - H * scale) / 2;
        ctx.drawImage(offscreen, dx, dy, W * scale, H * scale);
    }

    /**
     * Draw a depth map as a pseudocolour image.
     * @param {string} canvasId
     * @param {number[][]} depthData - 2D array [H][W] of float.
     */
    function drawDepth(canvasId, depthData) {
        const canvas = document.getElementById(canvasId);
        if (!canvas || !depthData || depthData.length === 0) return;
        _fitCanvas(canvas);

        const ctx = canvas.getContext("2d");
        const H = depthData.length;
        const W = depthData[0].length;

        // Find min/max
        let minD = Infinity, maxD = -Infinity;
        for (let y = 0; y < H; y++) {
            for (let x = 0; x < W; x++) {
                const v = depthData[y][x];
                if (v > 0) {
                    if (v < minD) minD = v;
                    if (v > maxD) maxD = v;
                }
            }
        }
        if (minD === Infinity) { minD = 0; maxD = 1; }

        const imgData = ctx.createImageData(W, H);
        for (let y = 0; y < H; y++) {
            for (let x = 0; x < W; x++) {
                const i = (y * W + x) * 4;
                const [r, g, b] = _depthColour(depthData[y][x], minD, maxD);
                imgData.data[i]     = r;
                imgData.data[i + 1] = g;
                imgData.data[i + 2] = b;
                imgData.data[i + 3] = 255;
            }
        }

        const offscreen = new OffscreenCanvas(W, H);
        offscreen.getContext("2d").putImageData(imgData, 0, 0);

        ctx.clearRect(0, 0, canvas.width, canvas.height);
        ctx.imageSmoothingEnabled = false;
        const scale = Math.min(canvas.width / W, canvas.height / H);
        const dx = (canvas.width - W * scale) / 2;
        const dy = (canvas.height - H * scale) / 2;
        ctx.drawImage(offscreen, dx, dy, W * scale, H * scale);
    }

    /**
     * Draw a label image with random colours per grain.
     * @param {string} canvasId
     * @param {number[][]} labelData - 2D array [H][W] of int32.
     */
    function drawLabels(canvasId, labelData) {
        const canvas = document.getElementById(canvasId);
        if (!canvas || !labelData || labelData.length === 0) return;
        _fitCanvas(canvas);

        const ctx = canvas.getContext("2d");
        const H = labelData.length;
        const W = labelData[0].length;
        const imgData = ctx.createImageData(W, H);

        for (let y = 0; y < H; y++) {
            for (let x = 0; x < W; x++) {
                const i = (y * W + x) * 4;
                const lbl = labelData[y][x];
                const [r, g, b] = _labelColour(lbl);
                imgData.data[i]     = r;
                imgData.data[i + 1] = g;
                imgData.data[i + 2] = b;
                imgData.data[i + 3] = 255;
            }
        }

        const offscreen = new OffscreenCanvas(W, H);
        offscreen.getContext("2d").putImageData(imgData, 0, 0);

        ctx.clearRect(0, 0, canvas.width, canvas.height);
        ctx.imageSmoothingEnabled = false;
        const scale = Math.min(canvas.width / W, canvas.height / H);
        const dx = (canvas.width - W * scale) / 2;
        const dy = (canvas.height - H * scale) / 2;
        ctx.drawImage(offscreen, dx, dy, W * scale, H * scale);
    }

    // -------------------------------------------------------------- //
    // PSD chart
    // -------------------------------------------------------------- //

    /**
     * Draw the PSD cumulative curve, histogram, and Dx markers.
     * @param {string} canvasId
     * @param {object} psd - PSD data from the backend.
     */
    function drawPSD(canvasId, psd, comparison) {
        const canvas = document.getElementById(canvasId);
        if (!canvas) return;
        _fitCanvas(canvas);

        const ctx = canvas.getContext("2d");
        const W = canvas.width;
        const H = canvas.height;
        ctx.clearRect(0, 0, W, H);

        if (!psd || !psd.sizes || psd.sizes.length === 0) {
            ctx.fillStyle = "#8b949e";
            ctx.font = "13px sans-serif";
            ctx.textAlign = "center";
            ctx.fillText("No PSD data -- generate a grain bed first", W / 2, H / 2);
            return;
        }

        const pad = { top: 20, right: 20, bottom: 40, left: 50 };
        const pw = W - pad.left - pad.right;
        const ph = H - pad.top - pad.bottom;

        const sizes = psd.sizes;
        const passing = psd.passing;
        const xMin = sizes[0];
        const xMax = sizes[sizes.length - 1];
        const yMin = 0;
        const yMax = 100;

        const xScale = (v) => pad.left + ((v - xMin) / (xMax - xMin || 1)) * pw;
        const yScale = (v) => pad.top + ph - ((v - yMin) / (yMax - yMin)) * ph;

        // Grid lines
        ctx.strokeStyle = "#30363d";
        ctx.lineWidth = 0.5;
        for (let yy = 0; yy <= 100; yy += 20) {
            ctx.beginPath();
            ctx.moveTo(pad.left, yScale(yy));
            ctx.lineTo(pad.left + pw, yScale(yy));
            ctx.stroke();
        }

        // Histogram (if available)
        if (psd.histogram && psd.histogram.bin_edges && psd.histogram.counts) {
            const edges = psd.histogram.bin_edges;
            const counts = psd.histogram.counts;
            const maxCount = Math.max(...counts, 1);

            ctx.fillStyle = "rgba(210, 153, 34, 0.25)";
            for (let i = 0; i < counts.length; i++) {
                const x0 = xScale(edges[i]);
                const x1 = xScale(edges[i + 1]);
                const barH = (counts[i] / maxCount) * ph * 0.4;
                ctx.fillRect(x0, pad.top + ph - barH, x1 - x0, barH);
            }
        }

        // Cumulative PSD curve
        ctx.strokeStyle = "#d29922";
        ctx.lineWidth = 2;
        ctx.beginPath();
        for (let i = 0; i < sizes.length; i++) {
            const x = xScale(sizes[i]);
            const y = yScale(passing[i]);
            if (i === 0) ctx.moveTo(x, y); else ctx.lineTo(x, y);
        }
        ctx.stroke();

        // Dx markers
        if (psd.percentiles) {
            const dxColors = { D10: "#58a6ff", D25: "#58a6ff", D50: "#3fb950", D75: "#f0883e", D80: "#f85149", D90: "#f85149" };
            for (const [key, val] of Object.entries(psd.percentiles)) {
                if (isNaN(val)) continue;
                const pct = parseInt(key.substring(1));
                const x = xScale(val);
                const y = yScale(pct);
                const color = dxColors[key] || "#8b949e";

                // Vertical dashed line
                ctx.strokeStyle = color;
                ctx.lineWidth = 1;
                ctx.setLineDash([3, 3]);
                ctx.beginPath();
                ctx.moveTo(x, pad.top);
                ctx.lineTo(x, pad.top + ph);
                ctx.stroke();
                ctx.setLineDash([]);

                // Marker dot
                ctx.fillStyle = color;
                ctx.beginPath();
                ctx.arc(x, y, 4, 0, Math.PI * 2);
                ctx.fill();

                // Label
                ctx.fillStyle = color;
                ctx.font = "10px monospace";
                ctx.textAlign = "center";
                ctx.fillText(`${key}=${val.toFixed(1)}`, x, pad.top - 4);
            }
        }

        // Ground truth overlay (sieve data comparison)
        if (comparison && comparison.true_sizes && comparison.true_passing) {
            const ts = comparison.true_sizes;
            const tp = comparison.true_passing;
            ctx.strokeStyle = "#f85149";
            ctx.lineWidth = 2;
            ctx.setLineDash([6, 3]);
            ctx.beginPath();
            for (let i = 0; i < ts.length; i++) {
                const x = xScale(ts[i]);
                const y = yScale(tp[i]);
                if (i === 0) ctx.moveTo(x, y); else ctx.lineTo(x, y);
            }
            ctx.stroke();
            ctx.setLineDash([]);

            // Legend label for ground truth
            ctx.fillStyle = "#f85149";
            ctx.font = "10px monospace";
            ctx.textAlign = "left";
            ctx.fillText("-- Ground truth (sieve)", pad.left + 6, pad.top + 14);
        }

        // Axes
        ctx.strokeStyle = "#8b949e";
        ctx.lineWidth = 1;
        ctx.beginPath();
        ctx.moveTo(pad.left, pad.top);
        ctx.lineTo(pad.left, pad.top + ph);
        ctx.lineTo(pad.left + pw, pad.top + ph);
        ctx.stroke();

        // Y-axis labels
        ctx.fillStyle = "#8b949e";
        ctx.font = "10px monospace";
        ctx.textAlign = "right";
        for (let yy = 0; yy <= 100; yy += 20) {
            ctx.fillText(`${yy}%`, pad.left - 4, yScale(yy) + 3);
        }

        // X-axis labels
        ctx.textAlign = "center";
        const nTicks = 6;
        for (let i = 0; i <= nTicks; i++) {
            const v = xMin + (i / nTicks) * (xMax - xMin);
            ctx.fillText(v.toFixed(1), xScale(v), pad.top + ph + 14);
        }

        // Axis titles
        ctx.fillStyle = "#8b949e";
        ctx.font = "11px sans-serif";
        ctx.textAlign = "center";
        ctx.fillText("Grain Size", pad.left + pw / 2, H - 4);

        ctx.save();
        ctx.translate(12, pad.top + ph / 2);
        ctx.rotate(-Math.PI / 2);
        ctx.fillText("Cumulative Passing %", 0, 0);
        ctx.restore();
    }

    return { drawRGB, drawDepth, drawLabels, drawPSD };
})();
