"""Tests for the /api/health and /api/version system endpoints.

These endpoints are used by deployment tooling (nginx / systemd / cPanel
Passenger) for liveness probes and to verify that the deployed build matches
the expected commit. The version is sourced from ``app.__version__`` so the
HTTP surface and the package metadata stay in sync.
"""

from fastapi.testclient import TestClient

from app import __version__
from app.main import app, state


client = TestClient(app)


class TestHealthEndpoint:
    """Coverage for GET /api/health."""

    def test_health_returns_200(self):
        response = client.get("/api/health")
        assert response.status_code == 200

    def test_health_payload_shape(self):
        payload = client.get("/api/health").json()
        assert set(payload.keys()) == {"status", "version", "sim_initialized"}
        assert payload["status"] == "ok"
        assert payload["version"] == __version__
        assert isinstance(payload["sim_initialized"], bool)

    def test_health_reflects_sim_state(self):
        # Baseline: no scene loaded => sim_initialized is False.
        original_rgb = state["rgb"]
        state["rgb"] = None
        try:
            payload = client.get("/api/health").json()
            assert payload["sim_initialized"] is False
        finally:
            state["rgb"] = original_rgb


class TestVersionEndpoint:
    """Coverage for GET /api/version."""

    def test_version_returns_200(self):
        response = client.get("/api/version")
        assert response.status_code == 200

    def test_version_payload_matches_package(self):
        payload = client.get("/api/version").json()
        assert payload == {"version": __version__}
