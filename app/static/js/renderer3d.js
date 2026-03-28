/**
 * GrainSight -- 3D surface renderer placeholder.
 *
 * This module provides a lightweight 3D surface visualisation of the
 * depth map using an isometric projection rendered onto a 2D canvas.
 * For a full Three.js implementation, this module can be extended.
 *
 * Currently the primary visualisation uses the 2D renderers in
 * renderer2d.js.  This module is reserved for future expansion with
 * Three.js or similar WebGL libraries.
 *
 * @module renderer3d
 */

"use strict";

const Renderer3D = (() => {

    /**
     * Draw a simple wireframe isometric projection of a depth map.
     * (Placeholder -- can be replaced with Three.js in the future.)
     *
     * @param {string} canvasId - Target canvas element id.
     * @param {number[][]} depthData - 2D array [H][W] of float.
     * @param {number} step - Sampling step (every N-th pixel).
     */
    function drawIsometric(canvasId, depthData, step) {
        const canvas = document.getElementById(canvasId);
        if (!canvas || !depthData || depthData.length === 0) return;

        const ctx = canvas.getContext("2d");
        const H = depthData.length;
        const W = depthData[0].length;
        step = step || Math.max(2, Math.floor(Math.max(H, W) / 60));

        // Find depth range
        let maxD = 0;
        for (let y = 0; y < H; y += step) {
            for (let x = 0; x < W; x += step) {
                if (depthData[y][x] > maxD) maxD = depthData[y][x];
            }
        }
        if (maxD === 0) maxD = 1;

        const cw = canvas.width;
        const ch = canvas.height;
        ctx.clearRect(0, 0, cw, ch);

        // Simple isometric: x' = (x - y) * cos30, y' = (x + y) * sin30 - z
        const cos30 = 0.866;
        const sin30 = 0.5;
        const scale = Math.min(cw, ch) / (W + H) * 1.2;
        const zScale = scale * 1.5;
        const ox = cw / 2;
        const oy = ch * 0.7;

        ctx.strokeStyle = "rgba(210, 153, 34, 0.3)";
        ctx.lineWidth = 0.5;

        // Draw grid lines along X
        for (let y = 0; y < H; y += step) {
            ctx.beginPath();
            for (let x = 0; x < W; x += step) {
                const z = depthData[y][x] / maxD;
                const px = ox + (x - y) * cos30 * scale * 0.5;
                const py = oy + (x + y) * sin30 * scale * 0.5 - z * zScale * 20;
                if (x === 0) ctx.moveTo(px, py); else ctx.lineTo(px, py);
            }
            ctx.stroke();
        }

        // Draw grid lines along Y
        for (let x = 0; x < W; x += step) {
            ctx.beginPath();
            for (let y = 0; y < H; y += step) {
                const z = depthData[y][x] / maxD;
                const px = ox + (x - y) * cos30 * scale * 0.5;
                const py = oy + (x + y) * sin30 * scale * 0.5 - z * zScale * 20;
                if (y === 0) ctx.moveTo(px, py); else ctx.lineTo(px, py);
            }
            ctx.stroke();
        }
    }

    return { drawIsometric };
})();
