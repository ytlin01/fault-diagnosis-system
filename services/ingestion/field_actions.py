"""Atomic masking actions applied to individual field values.

Every public function has the signature:
    (value: Any, *, config: dict) -> tuple[Any, str]

Returns (masked_value, action_description) for lineage logging.
"""

from __future__ import annotations

import hashlib
import os
from typing import Any


# ── helpers ──────────────────────────────────────────────────────────────────

def _get_salt() -> str:
    """Load masking salt from environment. Fail-safe: refuse if absent.

    The salt is intentionally not read from tracked config so deterministic
    tokens remain joinable locally without committing the secret material.
    """
    salt = os.environ.get("FAULTDX_MASKING_SALT")
    if not salt:
        raise EnvironmentError(
            "FAULTDX_MASKING_SALT is not set. "
            "The masking pipeline refuses to run without a salt value. "
            "Set it in your .env or shell environment."
        )
    return salt


def _make_token(value: str, *, salt: str, algorithm: str = "sha256",
                prefix: str = "TOK_", length: int = 12) -> str:
    """Produce a deterministic, truncated, prefixed hash token."""
    h = hashlib.new(algorithm, f"{salt}{value}".encode("utf-8"))
    return f"{prefix}{h.hexdigest()[:length]}"


# ── public actions ───────────────────────────────────────────────────────────

def passthrough(value: Any, *, config: dict | None = None) -> tuple[Any, str]:
    """Return value unchanged."""
    return value, "passthrough"


def drop(value: Any, *, config: dict | None = None) -> tuple[None, str]:
    """Remove value entirely."""
    return None, "drop"


def redact(value: Any, *, config: dict | None = None) -> tuple[str, str]:
    """Replace value with a fixed placeholder."""
    config = config or {}
    replacement = config.get("replacement", "[REDACTED]")
    return replacement, f"redact→{replacement}"


def tokenize(value: Any, *, config: dict | None = None) -> tuple[str, str]:
    """Replace value with a deterministic pseudonym token.

    Requires FAULTDX_MASKING_SALT in environment.
    Same raw value + same salt → same token (joinable across tables).
    """
    if value is None or str(value).strip() == "":
        return "", "tokenize→empty"
    config = config or {}
    salt = _get_salt()
    token = _make_token(
        str(value),
        salt=salt,
        algorithm=config.get("algorithm", "sha256"),
        prefix=config.get("prefix", "TOK_"),
        length=config.get("hash_length", 12),
    )
    return token, f"tokenize→{token}"


def hash_value(value: Any, *, config: dict | None = None) -> tuple[str, str]:
    """One-way hash — same as tokenize but with HASH_ prefix by default."""
    if value is None or str(value).strip() == "":
        return "", "hash→empty"
    config = config or {}
    salt = _get_salt()
    token = _make_token(
        str(value),
        salt=salt,
        algorithm=config.get("algorithm", "sha256"),
        prefix=config.get("prefix", "HASH_"),
        length=config.get("hash_length", 12),
    )
    return token, f"hash→{token}"


def mask(value: Any, *, config: dict | None = None) -> tuple[str, str]:
    """Partially mask a value, keeping a configurable prefix visible.

    Config options:
        mask_char:   character used for masking (default: '*')
        keep_prefix: number of leading characters to keep visible (default: 1)
        keep_suffix: number of trailing characters to keep visible (default: 0)

    Examples:
        "张三丰"  → "张**"   (keep_prefix=1)
        "ABC123" → "AB****" (keep_prefix=2)
    """
    config = config or {}
    mask_char = config.get("mask_char", "*")
    keep_prefix = config.get("keep_prefix", 1)
    keep_suffix = config.get("keep_suffix", 0)

    raw = str(value) if value is not None else ""
    if not raw:
        return "", "mask→empty"

    visible_len = keep_prefix + keep_suffix
    if visible_len >= len(raw):
        # Value too short to mask meaningfully — mask all but first char
        masked = raw[0] + mask_char * (len(raw) - 1)
    elif keep_suffix > 0:
        masked = raw[:keep_prefix] + mask_char * (len(raw) - visible_len) + raw[-keep_suffix:]
    else:
        masked = raw[:keep_prefix] + mask_char * (len(raw) - keep_prefix)

    return masked, f"mask→{masked}"


def rename(value: Any, *, config: dict | None = None) -> tuple[Any, str]:
    """Pass value through unchanged — rename is handled at column level, not value level.

    The actual column renaming happens in structured_masking.py when building
    the output dict. This action just marks the intent in lineage.
    """
    config = config or {}
    rename_to = config.get("rename_to", "?")
    return value, f"rename→{rename_to}"


def generalize(value: Any, *, config: dict | None = None) -> tuple[Any, str]:
    """Coarsen a value according to generalize_method.

    Supported methods:
        to_month  — "2025-09-04" → "2025-09"
        to_date   — keep date, drop time
        to_shift  — keep shift identifier only
        to_type   — replace specific name with generic type label
    """
    config = config or {}
    method = config.get("generalize_method", "to_type")
    raw = str(value) if value is not None else ""

    if method == "to_month" and len(raw) >= 7:
        return raw[:7], f"generalize({method})"
    if method == "to_date" and len(raw) >= 10:
        return raw[:10], f"generalize({method})"
    if method == "to_shift":
        return raw, f"generalize({method})→kept"
    if method == "to_type":
        type_mapping = config.get("type_mapping") or {}
        default = type_mapping.get("default", f"[{method.upper()}]")
        values = type_mapping.get("values") or {}
        case_sensitive = bool(type_mapping.get("case_sensitive", False))

        if values:
            if case_sensitive and raw in values:
                return values[raw], f"generalize({method})->mapped"
            if not case_sensitive:
                folded_raw = raw.casefold()
                for source_value, mapped_type in values.items():
                    if str(source_value).casefold() == folded_raw:
                        return mapped_type, f"generalize({method})->mapped"

        return default, f"generalize({method})->default"

    return raw, f"generalize({method})→no-op"


# ── action registry ──────────────────────────────────────────────────────────

ACTION_REGISTRY: dict[str, callable] = {
    "passthrough": passthrough,
    "keep": passthrough,           # alias for passthrough
    "drop": drop,
    "redact": redact,
    "tokenize": tokenize,
    "hash": hash_value,
    "mask": mask,
    "rename": rename,
    "generalize": generalize,
}


def resolve_action(action_name: str):
    """Look up an action function by name. Raises KeyError if unknown."""
    if action_name not in ACTION_REGISTRY:
        raise KeyError(
            f"Unknown masking action '{action_name}'. "
            f"Available: {list(ACTION_REGISTRY.keys())}"
        )
    return ACTION_REGISTRY[action_name]
