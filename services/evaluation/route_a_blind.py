"""Query-only blind execution support for the Route A evaluator."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from services.canonicalization.prekg import canonicalize_query
from services.graph.text2cypher.templates import INTENT_DIAGNOSTIC_CHAIN
from services.retrieval.route_a_executor import execute_text2cypher


BLIND_VALIDATION_INPUT_SCHEMA = Path("contracts/evaluation/route_a_blind_validation_input_v1.schema.json")
BLIND_QUERY_BANK_SCHEMA_VERSION = "tpdx_blind_query_bank_v1"


class BlindValidationInputError(ValueError):
    """Raised when a blind-validation input violates its governed contract."""


def validate_blind_validation_input(payload: dict[str, Any]) -> None:
    """Enforce the executable invariants of the versioned blind input contract.

    The JSON Schema is the interchange contract. This check keeps the loader
    safe when the optional ``jsonschema`` package is unavailable.
    """
    governance, source, cases = payload.get("governance"), payload.get("source"), payload.get("cases")
    if (payload.get("schema_version") != BLIND_QUERY_BANK_SCHEMA_VERSION or payload.get("partition") != "blind"
            or not isinstance(payload.get("dataset_id"), str) or not payload["dataset_id"]
            or not isinstance(governance, dict) or governance.get("source_classification") != "masked_validation_only"
            or governance.get("serving_eligible") is not False or governance.get("kg_ingestion_eligible") is not False
            or governance.get("label_maturity") != "assumed_label_provisional" or not isinstance(governance.get("blind_key_policy"), str)
            or not isinstance(source, dict) or not isinstance(source.get("workbook"), str) or not isinstance(source.get("sheet"), str)
            or not isinstance(source.get("source_row_count"), int) or source["source_row_count"] < 1
            or not isinstance(payload.get("query_template"), str) or "{phenomenon}" not in payload["query_template"]
            or not isinstance(cases, list) or len(cases) != source["source_row_count"]):
        raise BlindValidationInputError(f"invalid governed blind query bank for {BLIND_VALIDATION_INPUT_SCHEMA}")
    seen_ids: set[str] = set()
    seen_rows: set[int] = set()
    prohibited = ("expected", "expected_causes", "expected_actions", "cause", "action", "answer", "resolution", "diagnosis")
    for case in cases:
        if (not isinstance(case, dict) or set(case) != {"case_id", "source_row", "phenomenon"}
                or not isinstance(case.get("case_id"), str) or not case["case_id"].startswith("C1STN-BLIND-")
                or not isinstance(case.get("source_row"), int) or case["source_row"] < 1
                or not isinstance(case.get("phenomenon"), str) or not case["phenomenon"].strip()):
            raise BlindValidationInputError("invalid blind query case")
        if case["case_id"] in seen_ids or case["source_row"] in seen_rows:
            raise BlindValidationInputError("duplicate blind case ID or source row")
        if any(key in case for key in prohibited):
            raise BlindValidationInputError("blind query bank contains answer-key material")
        seen_ids.add(case["case_id"])
        seen_rows.add(case["source_row"])


def load_query_bank(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    validate_blind_validation_input(payload)
    return payload


def run_query_bank(bank: dict[str, Any]) -> dict[str, Any]:
    template = str(bank.get("query_template") or "")
    if "{phenomenon}" not in template:
        raise ValueError("blind query_template must contain {phenomenon}")
    results = []
    for case in bank["cases"]:
        query = template.format(phenomenon=case["phenomenon"])
        canonical = canonicalize_query(query).as_dict()
        results.append({"case_id": case["case_id"], "source_row": case["source_row"], "query_text": query,
                        "retrieval": execute_text2cypher(canonical, intent=INTENT_DIAGNOSTIC_CHAIN)})
    return {"schema_version": "tpdx_blind_retrieval_run_v1", "dataset_id": bank["dataset_id"],
            "run_at": datetime.now(timezone.utc).isoformat(),
            "execution": "canonicalize_query + execute_text2cypher(diagnostic_chain)",
            "claim_boundary": "Retrieval output is for human review only and does not establish domain correctness or reviewed KG truth.",
            "results": results}


def run_query_bank_ollama(bank: dict[str, Any], provider_type: str = "ollama") -> dict[str, Any]:
    """Run the full Route A graph with a local generation provider.

    The provider sees only the query and graph retrieval output.  The source
    workbook?s expected causes/actions are never loaded by this function.
    """
    from services.providers.llm import build_provider
    from services.reasoning.route_graph import run_route_graph
    from services.routing.query_router import RoutingContext

    if provider_type != "ollama":
        raise ValueError("blind ollama mode requires provider_type='ollama'")
    template = str(bank.get("query_template") or "")
    if "{phenomenon}" not in template:
        raise ValueError("blind query_template must contain {phenomenon}")
    provider = build_provider({"type": provider_type})
    context = RoutingContext(available_sources=("reviewed_diagnostic_chain_v1",))
    results = []
    for case in bank["cases"]:
        query = template.format(phenomenon=case["phenomenon"])
        state = run_route_graph({"query_text": query, "_provider": provider}, routing_context=context)
        response = state.get("api_response", {})
        results.append({"case_id": case["case_id"], "source_row": case["source_row"], "query_text": query,
                        "answer": dict(response) if isinstance(response, dict) else {"raw_api_response": response}})
    return {"schema_version": "tpdx_blind_ollama_run_v1", "dataset_id": bank["dataset_id"],
            "run_at": datetime.now(timezone.utc).isoformat(), "provider": provider_type,
            "execution": "run_route_graph + local Ollama answer synthesis",
            "claim_boundary": "Answers are for human review only and do not establish domain correctness or reviewed KG truth.",
            "results": results}


def build_review_key(bank: dict[str, Any], workbook_path: Path) -> dict[str, Any]:
    """Create a local-only provisional review key from an authorized workbook."""
    from openpyxl import load_workbook

    workbook = load_workbook(workbook_path, read_only=True, data_only=True)
    sheet = workbook[str(bank["source"]["sheet"])]
    cases = []
    for case in bank["cases"]:
        source_row = int(case["source_row"])
        values = [cell.value for cell in sheet[source_row + 1]][:5]
        if values[0] != source_row or str(values[2] or "").strip() != case["phenomenon"].strip():
            raise ValueError(f"workbook row mismatch for source_row={source_row}")
        cases.append({
            "case_id": case["case_id"],
            "source_row": source_row,
            "expected_source_causes": [line.strip() for line in str(values[3] or "").splitlines() if line.strip()],
            "expected_source_actions": [line.strip() for line in str(values[4] or "").splitlines() if line.strip()],
            "human_review": {"state": "unreviewed", "reviewer": None, "decision": None, "notes": None},
        })
    return {
        "schema_version": "tpdx_blind_human_review_key_v1",
        "dataset_id": bank["dataset_id"],
        "key_policy": {"masked_validation_only": True, "must_not_be_used_for_kg_ingestion": True,
                       "must_not_be_used_for_prompt_or_retrieval_tuning": True,
                       "label_maturity": "assumed_label_provisional"},
        "source": {"workbook": str(workbook_path), "sheet": str(bank["source"]["sheet"])},
        "cases": cases,
    }