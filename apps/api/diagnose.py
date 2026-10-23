"""Thin `/api/diagnose` skeleton for TASK-013."""

from __future__ import annotations

from typing import Any, Mapping

from services.reasoning.route_graph import run_route_graph_dry_run


def diagnose(payload: Mapping[str, Any]) -> dict[str, Any]:
    """Execute the diagnosis route graph and return result_design_v1."""
    request = dict(payload)
    if "query_text" not in request and "text" in request:
        request["query_text"] = request["text"]
    state = run_route_graph_dry_run(request)
    return dict(state["api_response"])


try:  # pragma: no cover - depends on optional API runtime installation.
    from fastapi import FastAPI

    app = FastAPI(title="FaultDx API", version="0.1.0")

    @app.post("/api/diagnose")
    def post_diagnose(payload: dict[str, Any]) -> dict[str, Any]:
        return diagnose(payload)

except ImportError:  # pragma: no cover
    app = None
