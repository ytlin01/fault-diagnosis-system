"""FaultDx v2 Data-Line — Ingestion & Masking Service.

Provides a code-driven masking pipeline that transforms raw data into three
views: immutable raw → governed internal canonical → serving candidate.
Masking success does not by itself grant serving or promotion approval.

Modules:
    field_actions       — Atomic masking operations (redact, hash, tokenize, mask, …)
    header_normalize    — Header normalization + column alias resolution
    masking_engine      — Orchestrates per-source, per-column masking
    name_mapping        — Local pre-masking name normalization from sensitive workbook
    structured_masking  — Full structured (Excel/CSV) masking processor
    manifest            — Dataset manifest generation (input/output metadata)
    lineage             — Per-row field-level audit log
    unstructured        — MinerU extraction output masking (regex-based)
"""
