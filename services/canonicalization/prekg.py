"""Minimal pre-KG canonicalization contract for TASK-011.

The module intentionally keeps runtime state small. It does not route,
retrieve, promote reviewed facts, or assemble `/api/diagnose` responses.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
import hashlib
import re
from typing import Any, Iterable, Mapping


CONTRACT_VERSION = "canonicalization_prekg_v0"

REVIEWED = "reviewed"
CANDIDATE = "candidate"
EVIDENCE_ONLY = "evidence_only"
NOT_AVAILABLE = "not_available"
VALID_STATUSES = {REVIEWED, CANDIDATE, EVIDENCE_ONLY, NOT_AVAILABLE}

HIGH = "high"
MEDIUM = "medium"
LOW = "low"
UNKNOWN = "unknown"
VALID_CONFIDENCE = {HIGH, MEDIUM, LOW, UNKNOWN}

_ERROR_CODE_RE = re.compile(
    r"\b(?:"
    r"EC[-_]?\d+"                              # EC-123 style
    r"|[A-Z]\d{2}[A-Z][A-Z0-9]+-\d{2}(?:-\d{2})?"  # W01RBRT-07-03 / M07LOM1-01-03 style
    r"|[A-Z]\d{5,6}-\d{2}"                    # V020441-01 style
    r"|[A-Z]{1,4}\d{2,}(?:[-_][A-Z0-9]+)+"   # generic alphanumeric-dash
    r")(?![-\d])",  # must not be followed by dash or digit (avoids partial matches)
    re.IGNORECASE,
)
_NG_RE = re.compile(r"\bng\b", re.IGNORECASE)


@dataclass(frozen=True)
class SourceReference:
    source_type: str
    source_id: str
    record_id: str | None = None
    anchor: str | None = None
    serving_safe: bool = False
    reviewed: bool = False
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "source_type": self.source_type,
            "source_id": self.source_id,
            "serving_safe": self.serving_safe,
            "reviewed": self.reviewed,
        }
        if self.record_id is not None:
            payload["record_id"] = self.record_id
        if self.anchor is not None:
            payload["anchor"] = self.anchor
        if self.metadata:
            payload["metadata"] = _to_plain(self.metadata)
        return payload


@dataclass(frozen=True)
class CanonicalEntitySlot:
    raw: str | None
    canonical: str | None
    confidence: str = UNKNOWN
    source_field: str | None = None
    source_ref: SourceReference | None = None

    def __post_init__(self) -> None:
        if self.confidence not in VALID_CONFIDENCE:
            raise ValueError(f"Unsupported confidence: {self.confidence}")

    def as_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "raw": self.raw,
            "canonical": self.canonical,
            "confidence": self.confidence,
        }
        if self.source_field is not None:
            payload["source_field"] = self.source_field
        if self.source_ref is not None:
            payload["source_ref"] = self.source_ref.as_dict()
        return payload


@dataclass(frozen=True)
class CanonicalQuery:
    text: str
    normalized_text: str
    language: str
    received_at: str
    tokens: tuple[str, ...] = ()

    def as_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "text": self.text,
            "normalized_text": self.normalized_text,
            "language": self.language,
            "received_at": self.received_at,
        }
        if self.tokens:
            payload["tokens"] = list(self.tokens)
        return payload


@dataclass(frozen=True)
class CanonicalMappingRecord:
    mapping_record_id: str
    error_code: CanonicalEntitySlot
    fault: CanonicalEntitySlot
    cause: CanonicalEntitySlot
    action: CanonicalEntitySlot
    evidence_refs: tuple[SourceReference, ...]
    status: str
    serving_safe: bool
    requires_review: bool
    action_steps: tuple[dict[str, Any], ...] = ()
    phenomenon_id: str | None = None
    asset_ref_id: str | None = None

    def __post_init__(self) -> None:
        _ensure_valid_status(self.status)
        if self.status in {CANDIDATE, EVIDENCE_ONLY} and not self.requires_review:
            raise ValueError(f"{self.status} mapping records must require review")

    def as_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "mapping_record_id": self.mapping_record_id,
            "error_code": self.error_code.as_dict(),
            "fault": self.fault.as_dict(),
            "cause": self.cause.as_dict(),
            "action": self.action.as_dict(),
            "evidence_refs": [source.as_dict() for source in self.evidence_refs],
            "status": self.status,
            "serving_safe": self.serving_safe,
            "requires_review": self.requires_review,
        }
        if self.action_steps:
            payload["action_steps"] = list(self.action_steps)
        if self.phenomenon_id is not None:
            payload["phenomenon_id"] = self.phenomenon_id
        if self.asset_ref_id is not None:
            payload["asset_ref_id"] = self.asset_ref_id
        return payload


@dataclass(frozen=True)
class CanonicalState:
    query: CanonicalQuery | None
    entities: Mapping[str, Any]
    mapping_records: tuple[CanonicalMappingRecord, ...] = ()
    source_refs: tuple[SourceReference, ...] = ()
    contract_version: str = CONTRACT_VERSION

    def as_dict(self) -> dict[str, Any]:
        return {
            "contract_version": self.contract_version,
            "query": self.query.as_dict() if self.query else {},
            "entities": _to_plain(self.entities),
            "mapping_records": [record.as_dict() for record in self.mapping_records],
            "source_refs": [source.as_dict() for source in self.source_refs],
        }

    def result_projection(self) -> dict[str, Any]:
        """Return the fields canonicalization may project to result API v1."""
        return {
            "query": self.query.as_dict() if self.query else {},
            "entities": _to_plain(self.entities),
        }


def canonicalize_query(
    query_text: str,
    *,
    received_at: str | None = None,
    language: str = "zh-CN",
    asset_index: dict | None = None,
) -> CanonicalState:
    """Build a minimal canonical state from user query text only."""
    text = str(query_text or "").strip()
    normalized = normalize_text(text)
    query = CanonicalQuery(
        text=text,
        normalized_text=normalized,
        language=language,
        received_at=received_at or datetime.now(timezone.utc).isoformat(),
        tokens=tuple(_query_tokens(normalized)),
    )
    return CanonicalState(query=query, entities=_entities_from_query(text, normalized, asset_index=asset_index))


def canonicalize_structured_record(
    record: Mapping[str, Any],
    *,
    source_id: str,
    status: str,
    source_type: str = "structured_catalog",
    record_id: str | None = None,
    anchor: str | None = None,
    serving_safe: bool = True,
) -> CanonicalState:
    """Canonicalize a reviewed or candidate structured aggregate record."""
    _ensure_valid_status(status)
    if status not in {REVIEWED, CANDIDATE}:
        raise ValueError("Structured records must be reviewed or candidate")
    source_ref = SourceReference(
        source_type=source_type,
        source_id=source_id,
        record_id=record_id,
        anchor=anchor,
        serving_safe=serving_safe,
        reviewed=status == REVIEWED,
        metadata=_source_boundary_metadata(record),
    )
    mapping = _mapping_record_from_source(
        record,
        source_ref=source_ref,
        status=status,
        serving_safe=serving_safe,
        requires_review=status != REVIEWED,
    )
    return CanonicalState(
        query=None,
        entities=_entities_from_mapping(mapping),
        mapping_records=(mapping,),
        source_refs=(source_ref,),
    )


def canonicalize_serving_document(
    document: Mapping[str, Any],
    *,
    source_id: str,
    source_type: str = "serving_document",
    record_id: str | None = None,
    anchor: str | None = None,
) -> CanonicalState:
    """Canonicalize serving-safe document evidence without creating mappings."""
    if not bool(document.get("serving_safe", document.get("serving_eligible", False))):
        raise ValueError("Document evidence must be serving-safe before canonicalization")
    text = _first_present(document, ("summary", "text", "content", "snippet"))[1]
    source_ref = SourceReference(
        source_type=source_type,
        source_id=source_id,
        record_id=record_id,
        anchor=anchor or _string_or_none(document.get("source_anchor") or document.get("anchor")),
        serving_safe=True,
        reviewed=False,
        metadata=_source_boundary_metadata(document),
    )
    entities = _empty_entities()
    entities["observation"]["phenomenon_text"] = _slot(
        raw=text,
        canonical=normalize_text(text),
        confidence=LOW if text is None else MEDIUM,
        source_ref=source_ref,
    )
    return CanonicalState(query=None, entities=entities, source_refs=(source_ref,))


def canonicalize_serving_document_batch(
    documents: Iterable[Mapping[str, Any]],
    *,
    source_id: str,
    source_type: str = "serving_document",
) -> dict[str, Any]:
    """Canonicalize a serving-safe document batch without file I/O.

    This is the v0 offline/batch surface available before reviewed
    structured/KG data arrives. It accepts only already serving-safe records.
    """
    records: list[dict[str, Any]] = []
    for index, document in enumerate(documents, start=1):
        record_id = _string_or_none(
            document.get("record_id")
            or document.get("chunk_id")
            or document.get("id")
            or f"record-{index}"
        )
        state = canonicalize_serving_document(
            document,
            source_id=_string_or_none(document.get("source_id")) or source_id,
            source_type=source_type,
            record_id=record_id,
            anchor=_string_or_none(document.get("anchor") or document.get("source_anchor")),
        )
        records.append(state.as_dict())

    return {
        "contract_version": CONTRACT_VERSION,
        "mode": "offline_batch_serving_document",
        "source_id": source_id,
        "record_count": len(records),
        "records": records,
        "summary": {
            "mapping_record_count": 0,
            "status": EVIDENCE_ONLY if records else NOT_AVAILABLE,
            "serving_safe_only": True,
        },
    }


def canonicalize_case_candidate(
    candidate: Mapping[str, Any],
    *,
    source_id: str,
    source_type: str = "structured_case_candidate",
    record_id: str | None = None,
    anchor: str | None = None,
    serving_safe: bool = True,
) -> CanonicalState:
    """Canonicalize a case/governance candidate as candidate-only material."""
    source_ref = SourceReference(
        source_type=source_type,
        source_id=source_id,
        record_id=record_id,
        anchor=anchor,
        serving_safe=serving_safe,
        reviewed=False,
        metadata=_source_boundary_metadata(candidate),
    )
    mapping = _mapping_record_from_source(
        candidate,
        source_ref=source_ref,
        status=CANDIDATE,
        serving_safe=serving_safe,
        requires_review=True,
    )
    return CanonicalState(
        query=None,
        entities=_entities_from_mapping(mapping),
        mapping_records=(mapping,),
        source_refs=(source_ref,),
    )


def normalize_text(value: Any) -> str:
    text = "" if value is None else str(value).strip()
    text = " ".join(text.split())
    text = _NG_RE.sub("NG", text)
    return text


def _mapping_record_from_source(
    record: Mapping[str, Any],
    *,
    source_ref: SourceReference,
    status: str,
    serving_safe: bool,
    requires_review: bool,
) -> CanonicalMappingRecord:
    ec_field, ec = _first_present(record, ("EC", "Error code", "error_code", "code"))
    fp_field, fp = _first_present(record, ("FP", "standard_fp", "fault", "Description", "異常描敘"))
    rc_field, rc = _first_present(record, ("RC", "cause", "原因"))
    action_field, action = _first_present(record, ("PA", "RA", "action", "維修動作", "维修动作"))
    mapping_id = str(record.get("mapping_record_id") or record.get("record_id") or _stable_id(ec, fp, rc, action))

    return CanonicalMappingRecord(
        mapping_record_id=mapping_id,
        error_code=_slot(ec, ec, _confidence(ec), source_field=ec_field, source_ref=source_ref),
        fault=_slot(fp, fp, _confidence(fp), source_field=fp_field, source_ref=source_ref),
        cause=_slot(rc, rc, _confidence(rc), source_field=rc_field, source_ref=source_ref),
        action=_slot(action, action, _confidence(action), source_field=action_field, source_ref=source_ref),
        action_steps=_action_steps(record.get("action_steps"), source_field=action_field),
        evidence_refs=(source_ref,),
        status=status,
        serving_safe=serving_safe,
        requires_review=requires_review,
    )


def _entities_from_query(text: str, normalized: str, *, asset_index: dict | None = None) -> dict[str, Any]:
    entities = _empty_entities()
    error_code = _detect_error_code(text)
    time_context = _detect_time_context(text)
    entities["diagnostic"]["error_code"] = _slot(error_code, error_code, HIGH if error_code else UNKNOWN)
    entities["diagnostic"]["fault"] = _slot(text or None, normalized or None, MEDIUM if normalized else UNKNOWN)
    entities["observation"]["phenomenon_text"] = _slot(text or None, normalized or None, MEDIUM if normalized else UNKNOWN)
    entities["observation"]["time_context"] = _slot(time_context[0], time_context[1], time_context[2])

    if asset_index is not None:
        hit = _detect_asset(text, asset_index)
        if hit is not None:
            label, node_id, matched_name = hit
            entities["asset"][label] = _slot(matched_name, node_id, MEDIUM)
    else:
        module = _detect_module(text)
        entities["asset"]["module"] = _slot(module, f"{module}模块" if module else None, MEDIUM if module else UNKNOWN)

    return entities


def _entities_from_mapping(mapping: CanonicalMappingRecord) -> dict[str, Any]:
    entities = _empty_entities()
    entities["diagnostic"]["error_code"] = mapping.error_code
    entities["diagnostic"]["fault"] = mapping.fault
    entities["diagnostic"]["cause"] = mapping.cause
    entities["diagnostic"]["action"] = mapping.action
    entities["observation"]["phenomenon_text"] = mapping.fault
    return entities


def _empty_entities() -> dict[str, Any]:
    return {
        "asset": {
            "station": _slot(None, None),
            "module": _slot(None, None),
            "component": _slot(None, None),
            "subcomponent": _slot(None, None),
        },
        "diagnostic": {
            "error_code": _slot(None, None),
            "fault": _slot(None, None),
            "cause": _slot(None, None),
            "action": _slot(None, None),
        },
        "observation": {
            "phenomenon_text": _slot(None, None),
            "time_context": _slot(None, None),
        },
    }


def _slot(
    raw: Any,
    canonical: Any,
    confidence: str = UNKNOWN,
    *,
    source_field: str | None = None,
    source_ref: SourceReference | None = None,
) -> CanonicalEntitySlot:
    raw_value = _string_or_none(raw)
    canonical_value = _string_or_none(canonical)
    return CanonicalEntitySlot(
        raw=raw_value,
        canonical=normalize_text(canonical_value) if canonical_value is not None else None,
        confidence=confidence,
        source_field=source_field,
        source_ref=source_ref,
    )


def _action_steps(value: Any, *, source_field: str | None) -> tuple[dict[str, Any], ...]:
    if not value:
        return ()
    items = value if isinstance(value, list) else [value]
    steps: list[dict[str, Any]] = []
    for index, item in enumerate(items, start=1):
        if isinstance(item, Mapping):
            raw = item.get("action") or item.get("instruction") or item.get("raw")
            step = int(item.get("step") or item.get("order") or index)
        else:
            raw = item
            step = index
        slot = _slot(raw, raw, _confidence(raw), source_field=source_field)
        steps.append({"step": step, "action": slot.as_dict()})
    return tuple(steps)


def _first_present(record: Mapping[str, Any], fields: tuple[str, ...]) -> tuple[str | None, Any]:
    for field in fields:
        if field in record and record[field] not in (None, ""):
            return field, record[field]
    return None, None


_SOURCE_BOUNDARY_METADATA_FIELDS = (
    "block_type",
    "retrieval_eligible",
    "graph_eligible",
    "derived_from_block_type",
    "raw_asset_included",
    "source_anchor",
    "route_target",
    "contract_scope",
    "publication_status",
    "field_allowlist",
    "promotion_rules",
    "source_marker",
    "kg_diagnosis_eligible",
    "review_status",
    "chain_status",
    "route_reason",
)


def _source_boundary_metadata(record: Mapping[str, Any]) -> dict[str, Any]:
    metadata: dict[str, Any] = {}
    for name in _SOURCE_BOUNDARY_METADATA_FIELDS:
        if name in record and record[name] not in (None, "", [], {}):
            metadata[name] = record[name]
    return metadata


def _confidence(value: Any) -> str:
    return MEDIUM if value not in (None, "", [], ()) else UNKNOWN


def _ensure_valid_status(status: str) -> None:
    if status not in VALID_STATUSES:
        raise ValueError(f"Unsupported governance status: {status}")


def _string_or_none(value: Any) -> str | None:
    if value in (None, ""):
        return None
    if isinstance(value, (list, tuple)):
        return " | ".join(str(item) for item in value if item not in (None, ""))
    return str(value)


def _to_plain(value: Any) -> Any:
    if isinstance(value, CanonicalEntitySlot):
        return value.as_dict()
    if isinstance(value, SourceReference):
        return value.as_dict()
    if isinstance(value, Mapping):
        return {key: _to_plain(item) for key, item in value.items()}
    if isinstance(value, tuple):
        return [_to_plain(item) for item in value]
    if isinstance(value, list):
        return [_to_plain(item) for item in value]
    return value


def _query_tokens(normalized: str) -> list[str]:
    tokens: list[str] = []
    if "cowling" in normalized.lower():
        tokens.append("cowling")
    if "NG" in normalized:
        tokens.append("NG")
    if "无" in normalized and ("报错" in normalized or "error code" in normalized.lower()):
        tokens.append("无报错")
    return tokens


def _detect_asset(
    text: str, index: dict
) -> tuple[str, str, str] | None:
    """Return (label, node_id, matched_name) for the best CAD asset hit in text.

    Searches module / component / subcomponent buckets. When multiple names
    match, returns the longest match (most specific name). Ties are broken by
    specificity: subcomponent > component > module.
    """
    _BUCKET_ORDER = ("subcomponent", "component", "module")
    best_label: str | None = None
    best_node_id: str | None = None
    best_name: str | None = None
    best_len = -1

    text_lower = text.lower()
    for label in _BUCKET_ORDER:
        bucket: dict = index.get(label, {})
        for name, node_id in bucket.items():
            if name.lower() in text_lower:
                if len(name) > best_len or (
                    len(name) == best_len and _BUCKET_ORDER.index(label) < _BUCKET_ORDER.index(best_label)
                ):
                    best_label = label
                    best_node_id = node_id
                    best_name = name
                    best_len = len(name)

    if best_label is None:
        return None
    return (best_label, best_node_id, best_name)  # type: ignore[return-value]


def _detect_module(text: str) -> str | None:
    lowered = text.lower()
    if "cowling" in lowered:
        return "cowling组装"
    if "上料仓" in text:
        return "上料仓"
    return None


def _detect_error_code(text: str) -> str | None:
    match = _ERROR_CODE_RE.search(text)
    return match.group(0) if match else None


def _detect_time_context(text: str) -> tuple[str | None, str | None, str]:
    if "昨天" in text or "一直" in text or "持续" in text:
        return ("昨天" if "昨天" in text else None, "持续多日", MEDIUM)
    return (None, None, UNKNOWN)


def _stable_id(*parts: Any) -> str:
    seed = "|".join(_string_or_none(part) or "" for part in parts)
    digest = hashlib.sha1(seed.encode("utf-8")).hexdigest()[:12]
    return f"mapping:{digest}"
