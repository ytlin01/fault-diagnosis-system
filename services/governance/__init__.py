"""Data governance layer for FaultDx.

Canonical Phase 2 storage lives under data/governance/:
- source_inventory.csv for editable artifact inventory
- masking_log.jsonl, annotation_log.jsonl, index_registry.jsonl, eval_run_log.jsonl
  for append-only operational records

The legacy data/data_governance.xlsx workbook is a review/export artifact, not the
primary mutation target.
"""
