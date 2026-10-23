"""Explicit old-TP-DX mappings for the C1STN expert-ranking candidate supply.

Maps exported old-KG cause/action texts to the reviewed canonical
vocabulary using *normalized exact text matches only*: Unicode NFKC
presentation-form folding plus casefold, whitespace collapse — never fuzzy
or semantic matching. A proposed mapping is deliberately unusable for
scored evaluation until a reviewer marks it approved. Graph element IDs
never leave this artifact.
"""

from __future__ import annotations

import hashlib
import json
import unicodedata
from typing import Any, Mapping, Sequence

SCHEMA_VERSION = "route_a_expert_ranking_mapping_v1"
MAPPING_ID = "old_tpdx_canonical_mapping_v1"


def normalize_text(text: str) -> str:
    """Presentation-only normalization: NFKC, casefold, whitespace collapse.

    Never use fuzzy semantics: two texts match only if they are the same
    text after Unicode presentation folding.
    """
    folded = unicodedata.normalize("NFKC", str(text)).casefold()
    return " ".join(folded.split())


def graph_snapshot_id(chain_rows: Sequence[Mapping[str, Any]]) -> str:
    """Content digest over deterministically ordered chain rows."""
    canonical = json.dumps(
        sorted(chain_rows, key=lambda row: json.dumps(row, ensure_ascii=False, sort_keys=True)),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    return "sha256:" + hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _match_catalog(
    graph_values: dict[str, list[str]],
    catalog: Sequence[Mapping[str, Any]],
    text_key: str,
    id_key: str,
) -> tuple[list[dict[str, Any]], int]:
    """Match graph values against catalog display names.

    ``graph_values`` maps normalized graph text -> list of raw graph texts
    (duplicates possible). Returns (matches, unmatched_graph_text_count).
    """
    display_by_normalized: dict[str, str] = {}
    for entry in catalog:
        normalized = normalize_text(entry[text_key])
        if normalized:
            # First catalog entry wins on collision; collisions are surfaced
            # by the caller through match counts.
            display_by_normalized.setdefault(normalized, str(entry[id_key]))
    matches: list[dict[str, Any]] = []
    unmatched = 0
    for normalized in sorted(graph_values):
        catalog_id = display_by_normalized.get(normalized)
        if catalog_id is None:
            unmatched += 1
            continue
        matches.append(
            {
                "catalog_id": catalog_id,
                "basis": "exact_normalized_text",
                "graph_texts": sorted(set(graph_values[normalized])),
            }
        )
    return matches, unmatched


def build_mapping(
    chain_rows: Sequence[Mapping[str, Any]],
    gold_v3: Mapping[str, Any],
    *,
    gold_v3_path: str,
    gold_v3_sha256: str,
    graph_version: str,
    approved: bool = False,
) -> dict[str, Any]:
    """Build the proposed (or approved) old-TP-DX canonical mapping.

    ``chain_rows`` are the frozen exported rows with ``cause_text`` and
    ``action_text`` fields. Only normalized exact matches are proposed;
    everything else stays explicitly unmatched and counted.
    """
    cause_values: dict[str, list[str]] = {}
    action_values: dict[str, list[str]] = {}
    for row in chain_rows:
        cause_text = str(row.get("cause_text") or "").strip()
        action_text = str(row.get("action_text") or "").strip()
        if not cause_text or not action_text:
            raise ValueError(
                "chain row is missing cause_text/action_text; export is incomplete"
            )
        cause_values.setdefault(normalize_text(cause_text), []).append(cause_text)
        action_values.setdefault(normalize_text(action_text), []).append(action_text)
    cause_matches, unmatched_causes = _match_catalog(
        cause_values, gold_v3.get("cause_catalog", []), "display_name", "cause_id"
    )
    action_matches, unmatched_actions = _match_catalog(
        action_values, gold_v3.get("repair_action_catalog", []), "display_name", "action_id"
    )
    return {
        "schema_version": SCHEMA_VERSION,
        "mapping_id": MAPPING_ID,
        "graph_version": graph_version,
        "snapshot_id": graph_snapshot_id(chain_rows),
        "approved": approved,
        "derived_from": {
            "gold_queue_id": gold_v3.get("queue_id"),
            "gold_path": gold_v3_path,
            "gold_sha256": gold_v3_sha256,
        },
        "review_gate": (
            "Proposal only until approved. Exact normalized text matches "
            "are proposed automatically; a proposed mapping is unusable for "
            "scored evaluation until the data owner approves it."
        ),
        "cause_matches": cause_matches,
        "action_matches": action_matches,
        "unmatched_graph_counts": {
            "distinct_causes": len(cause_values),
            "unmatched_causes": unmatched_causes,
            "distinct_actions": len(action_values),
            "unmatched_actions": unmatched_actions,
        },
    }


def mapping_lookup(mapping: Mapping[str, Any]) -> tuple[dict[str, str], dict[str, str]]:
    """Return (normalized_text -> catalog_id) lookup tables for ranked-supply use.

    Raises if the mapping is not approved: unapproved mappings must never
    feed scored evaluation.
    """
    if not mapping.get("approved"):
        raise ValueError("mapping is not approved; scored evaluation is not allowed")
    causes = {
        normalize_text(text): match["catalog_id"]
        for match in mapping.get("cause_matches", [])
        for text in match["graph_texts"]
    }
    actions = {
        normalize_text(text): match["catalog_id"]
        for match in mapping.get("action_matches", [])
        for text in match["graph_texts"]
    }
    return causes, actions
