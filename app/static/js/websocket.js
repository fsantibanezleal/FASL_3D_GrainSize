/**
 * GrainSight -- WebSocket connection manager.
 *
 * Maintains a persistent WebSocket connection to the FastAPI backend,
 * with automatic reconnection and heartbeat (ping/pong).  Incoming
 * state messages are dispatched to registered callbacks.
 *
 * @module websocket
 */

"use strict";

const GrainWS = (() => {
    let ws = null;
    let reconnectTimer = null;
    const RECONNECT_MS = 2000;
    const listeners = [];

    /**
     * Register a callback for incoming state messages.
     * @param {function} fn - Called with the parsed message object.
     */
    function onMessage(fn) {
        listeners.push(fn);
    }

    /** Dispatch a parsed message to all registered listeners. */
    function _dispatch(msg) {
        for (const fn of listeners) {
            try { fn(msg); } catch (e) { console.error("[WS] listener error:", e); }
        }
    }

    /** Update the status dot in the header. */
    function _setStatus(connected) {
        const dot = document.getElementById("ws-status");
        if (dot) {
            dot.classList.toggle("connected", connected);
            dot.setAttribute("data-tooltip", connected ? "Connected" : "Disconnected");
        }
    }

    /** Open the WebSocket connection. */
    function connect() {
        if (ws && (ws.readyState === WebSocket.OPEN || ws.readyState === WebSocket.CONNECTING)) {
            return;
        }

        const proto = location.protocol === "https:" ? "wss:" : "ws:";
        const url = `${proto}//${location.host}/ws`;
        ws = new WebSocket(url);

        ws.onopen = () => {
            console.log("[WS] connected");
            _setStatus(true);
            if (reconnectTimer) { clearTimeout(reconnectTimer); reconnectTimer = null; }
        };

        ws.onmessage = (evt) => {
            try {
                const msg = JSON.parse(evt.data);
                _dispatch(msg);
            } catch (e) {
                console.error("[WS] parse error:", e);
            }
        };

        ws.onclose = () => {
            console.log("[WS] disconnected");
            _setStatus(false);
            reconnectTimer = setTimeout(connect, RECONNECT_MS);
        };

        ws.onerror = (err) => {
            console.error("[WS] error:", err);
            ws.close();
        };
    }

    /** Send a JSON message to the server. */
    function send(obj) {
        if (ws && ws.readyState === WebSocket.OPEN) {
            ws.send(JSON.stringify(obj));
        }
    }

    return { connect, onMessage, send };
})();
