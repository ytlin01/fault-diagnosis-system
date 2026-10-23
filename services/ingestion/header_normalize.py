"""Header normalization and column alias resolution.

Solves real-world Excel header inconsistencies:
    - Full-width ↔ half-width characters  （ → (
    - Leading/trailing/embedded whitespace
    - Embedded newlines \\n \\r
    - Chinese/English bracket variants
    - Extra spaces around punctuation

Pipeline:
    raw header → normalize() → match against column_aliases → rule name
"""

from __future__ import annotations

import re
import unicodedata
from typing import Any


# ── Character normalization tables ───────────────────────────────────────────

# Full-width → half-width mapping for common punctuation / ASCII
_FULLWIDTH_OFFSET = 0xFEE0  # ord('Ａ') - ord('A')

_BRACKET_MAP = {
    "\uff08": "(",   # （ → (
    "\uff09": ")",   # ） → )
    "\u3010": "[",   # 【 → [
    "\u3011": "]",   # 】 → ]
    "\u300a": "<",   # 《 → <
    "\u300b": ">",   # 》 → >
    "\uff1a": ":",   # ： → :
    "\uff0c": ",",   # ， → ,
    "\uff1b": ";",   # ； → ;
}


def _fullwidth_to_halfwidth(ch: str) -> str:
    """Convert a single full-width character to half-width if possible."""
    cp = ord(ch)
    # Full-width ASCII range: U+FF01 ~ U+FF5E → U+0021 ~ U+007E
    if 0xFF01 <= cp <= 0xFF5E:
        return chr(cp - _FULLWIDTH_OFFSET)
    # Full-width space
    if cp == 0x3000:
        return " "
    # Known bracket / punctuation overrides
    if ch in _BRACKET_MAP:
        return _BRACKET_MAP[ch]
    return ch


# ── Core normalization ───────────────────────────────────────────────────────

def normalize_header(raw: str) -> str:
    """Normalize a single column header string.

    Steps:
        1. Strip leading/trailing whitespace
        2. Replace embedded newlines (\\n \\r) with spaces
        3. Collapse multiple consecutive spaces into one
        4. Convert full-width characters to half-width
        5. NFKC unicode normalization
        6. Remove leading required-field markers such as *
        7. Final strip
    """
    if not isinstance(raw, str):
        raw = str(raw) if raw is not None else ""

    # Step 1-2: strip + preserve word boundaries across embedded newlines
    s = raw.strip()
    s = s.replace("\r\n", " ").replace("\r", " ").replace("\n", " ")

    # Step 3: collapse spaces
    s = re.sub(r"\s+", " ", s)

    # Step 4: full-width → half-width
    s = "".join(_fullwidth_to_halfwidth(ch) for ch in s)

    # Step 5: NFKC normalization (handles remaining compatibility forms)
    s = unicodedata.normalize("NFKC", s)

    # Step 6: remove required-field markers used by data dictionaries
    s = re.sub(r"^[*]\s*", "", s)

    # Step 7: final strip
    return s.strip()


def normalize_headers(raw_headers: list[str]) -> list[str]:
    """Normalize a list of column headers."""
    return [normalize_header(h) for h in raw_headers]


# ── Column alias resolution ─────────────────────────────────────────────────

class HeaderResolver:
    """Resolves normalized headers against rule names + aliases.

    Given:
        - column_rules: dict of {rule_name: rule_config} from masking_rules.yaml
        - column_aliases: dict of {rule_name: [alias1, alias2, ...]}

    Produces:
        - mapping: {normalized_header → rule_name}
        - matched / alias_matched / unmatched / unused_rules
    """

    def __init__(
        self,
        column_rules: dict[str, Any],
        column_aliases: dict[str, list[str]] | None = None,
    ):
        self.column_rules = column_rules
        self.column_aliases = column_aliases or {}

        # Build lookup: normalized(alias_or_name) → rule_name
        self._lookup: dict[str, str] = {}
        for rule_name in column_rules:
            norm = normalize_header(rule_name)
            self._lookup[norm] = rule_name

        for rule_name, aliases in self.column_aliases.items():
            for alias in aliases:
                norm = normalize_header(alias)
                self._lookup[norm] = rule_name

    def resolve(
        self, raw_headers: list[str]
    ) -> "HeaderResolution":
        """Resolve raw headers against rules.

        Returns a HeaderResolution with full diagnostic info.
        """
        normalized = normalize_headers(raw_headers)

        mapping: dict[str, str] = {}           # normalized → rule_name
        matched: dict[str, str] = {}           # raw → rule_name (direct match)
        alias_matched: dict[str, str] = {}     # raw → rule_name (via alias)
        unmatched: list[str] = []              # raw headers with no rule
        raw_to_normalized: dict[str, str] = {} # raw → normalized

        matched_rule_names: set[str] = set()

        for raw, norm in zip(raw_headers, normalized):
            raw_to_normalized[raw] = norm

            if norm in self._lookup:
                rule_name = self._lookup[norm]
                mapping[norm] = rule_name
                matched_rule_names.add(rule_name)

                # Was it a direct match or alias?
                rule_norm = normalize_header(rule_name)
                if norm == rule_norm:
                    matched[raw] = rule_name
                else:
                    alias_matched[raw] = rule_name
            else:
                unmatched.append(raw)

        # Rules defined in config but not found in file headers
        unused_rules = [
            name for name in self.column_rules
            if name not in matched_rule_names
        ]

        return HeaderResolution(
            raw_headers=raw_headers,
            normalized=normalized,
            raw_to_normalized=raw_to_normalized,
            mapping=mapping,
            matched=matched,
            alias_matched=alias_matched,
            unmatched=unmatched,
            unused_rules=unused_rules,
        )


class HeaderResolution:
    """Result of header resolution — carries all diagnostic info."""

    def __init__(
        self,
        *,
        raw_headers: list[str],
        normalized: list[str],
        raw_to_normalized: dict[str, str],
        mapping: dict[str, str],
        matched: dict[str, str],
        alias_matched: dict[str, str],
        unmatched: list[str],
        unused_rules: list[str],
    ):
        self.raw_headers = raw_headers
        self.normalized = normalized
        self.raw_to_normalized = raw_to_normalized
        self.mapping = mapping               # normalized → rule_name
        self.matched = matched               # raw → rule_name (direct)
        self.alias_matched = alias_matched   # raw → rule_name (alias)
        self.unmatched = unmatched           # raw headers with no rule
        self.unused_rules = unused_rules     # rules not in file

    @property
    def has_issues(self) -> bool:
        return bool(self.unmatched) or bool(self.unused_rules)

    def get_rule_name(self, raw_header: str) -> str | None:
        """Get the rule name for a raw header, or None if unmatched."""
        norm = self.raw_to_normalized.get(raw_header)
        if norm is None:
            norm = normalize_header(raw_header)
        return self.mapping.get(norm)

    def print_report(self) -> None:
        """Print a human-readable header normalization report to stdout."""
        print()
        print("=" * 80)
        print("  Header Normalization Report")
        print("=" * 80)
        print()
        print(f"{'Raw Header':<32} {'Normalized':<24} {'Rule Match':<24} Status")
        print("-" * 100)

        for raw in self.raw_headers:
            norm = self.raw_to_normalized[raw]
            rule_name = self.mapping.get(norm)

            # Determine status
            if raw in self.matched:
                status = "  matched"
            elif raw in self.alias_matched:
                status = "  alias"
            else:
                status = "  NO RULE"

            # Truncate display
            raw_disp = repr(raw)[:30]
            norm_disp = repr(norm)[:22]
            rule_disp = (rule_name or "-")[:22]
            print(f"{raw_disp:<32} {norm_disp:<24} {rule_disp:<24} {status}")

        print()
        if self.unmatched:
            print(f"  Unmatched columns ({len(self.unmatched)}): "
                  f"{self.unmatched}")
        if self.unused_rules:
            print(f"  Unused rules ({len(self.unused_rules)}):    "
                  f"{self.unused_rules}")
        if not self.has_issues:
            print("  All headers matched. No issues.")
        print()

    def to_dict(self) -> dict:
        """Serialize for manifest embedding."""
        return {
            "mapped": {k: v for k, v in self.matched.items()},
            "alias_matched": {k: v for k, v in self.alias_matched.items()},
            "unmatched": self.unmatched,
            "unused_rules": self.unused_rules,
        }
