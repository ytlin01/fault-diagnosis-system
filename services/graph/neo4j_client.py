"""Centralised Neo4j connection config for FaultDx_main.

Reads credentials once from .env on import. All service and script modules
should import from here instead of repeating os.getenv("FAULTDX_NEO4J_*").

Usage
-----
Service code (lazy singleton — reuses one driver across calls):
    from services.graph.neo4j_client import get_driver, NEO4J_DATABASE

CLI scripts (fresh driver per invocation, accepts CLI overrides):
    from services.graph.neo4j_client import NEO4J_HOST, NEO4J_USER, NEO4J_PASSWORD, NEO4J_DATABASE
    driver = make_driver(args.uri, args.user, args.password)
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

# Load .env once at import time.
try:
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).resolve().parent.parent.parent / ".env")
except ImportError:
    pass

NEO4J_HOST: str = os.getenv("FAULTDX_NEO4J_HOST", "bolt://127.0.0.1:7687")
NEO4J_USER: str = os.getenv("FAULTDX_NEO4J_USER", "neo4j")
NEO4J_PASSWORD: str = os.getenv("FAULTDX_NEO4J_PASSWORD", "")
NEO4J_DATABASE: str = os.getenv("FAULTDX_NEO4J_DATABASE", "neo4j")

_driver: Any = None


def get_driver() -> Any:
    """Return the module-level Neo4j driver, creating it on first use."""
    global _driver
    if _driver is None:
        _driver = make_driver(NEO4J_HOST, NEO4J_USER, NEO4J_PASSWORD)
    return _driver


def make_driver(host: str, user: str, password: str) -> Any:
    """Create and verify a new Neo4j driver. Caller owns the lifecycle."""
    try:
        from neo4j import GraphDatabase  # type: ignore[import]
    except ImportError as exc:
        raise RuntimeError(
            "neo4j driver is not installed. Add 'neo4j' to requirements."
        ) from exc
    driver = GraphDatabase.driver(host, auth=(user, password))
    driver.verify_connectivity()
    return driver
