# V2-TASK016 independent review-label guide (material + CAD)

## Purpose

This is the fill-in guide for blocker 2: the independent, maturity-tagged,
leakage-checked review sets that `V2-TASK016` needs before it can score the
frozen material candidate (`V2-TASK017`, run `material_cef539710b861b7d`) and
the frozen CAD candidate (`V2-TASK015`, Phase 3 r10).

The guide defines the label record format, the maturity vocabulary, the
independence and leakage rules, and the applicability/exclusion rules. The
domain reviewer supplies the labels themselves; this document and its companion
schema (`review_labels.schema.json`) only define how they are recorded. No
label in this package is a domain label until a domain reviewer records one.

## Who supplies what

- **Domain reviewer (human):** the actual `expected` values for material and
  CAD surfaces, the reviewer decision, and the independence/leakage
  attestations. This is domain expertise and cannot be synthesized by an agent.
- **`data_quality_reviewer`:** the format, maturity/leakage vocabulary,
  applicability rules, and the downstream scoring that consumes the labels.
  The quality reviewer does not author domain labels.

## Maturity vocabulary

Reuse the branch vocabulary from `V2-TASK001`:

| `label_maturity` | Meaning | Eligible for domain-correctness scoring? |
|---|---|---|
| `provisional` | development / calibration only | no |
| `assumed_label_provisional` | carried assumed status (not independently established) | no |
| `reviewed` | independent evidence + at least one review record | yes |
| `adjudicated` | adjudicator resolved a disagreement with anchored evidence | yes |

Only `reviewed` and `adjudicated` labels may back a domain-correctness claim in
the final `V2-TASK016` scorecards. `provisional` labels may support calibration
or applicability work only.

## Independence rules

1. A label's `expected` value must come from independent domain evidence — the
   domain reviewer's governed knowledge and/or a separately governed reference —
   never from the candidate under review (`derived_from_candidate` must be
   `false`).
2. Do not label by reading the candidate's output and transcribing it as ground
   truth. Do not label by reading the candidate's input source
   (`L_ReplacementList`) alone: that source is co-source with the candidate, so
   labels read back from it are not independent and must be declared with
   `overlap: true` and a co-source note. A label that only re-states the
   candidate or its co-source workbook cannot be counted as independent
   corroboration.
3. Every label records `labels_source` (who/what supplied the domain truth) and
   `overlap` (whether the labeling basis overlaps the candidate's source).
4. Where paired old/new comparison is intended, the split must be assigned
   before scoring; a blind/hold-out subset must remain unavailable to graph
   construction, retrieval, and calibration.

## Leakage rules

The label set itself must not leak sensitive values. The material sensitive
columns (from `configs/pipelines/replacement_extract.yaml`) are:

`廠商`, `廠商代碼`, `品牌`, `設備名稱`, `設備型號`, `聯繫人`, `備註`, `專案`,
`製程`, `物料`, `廠商 PN`, `單價`, `耗材QPL`.

Before a label record is published:

- No value from the sensitive columns above may appear in `anchor`, `expected`,
  `source_basis`, or `note`.
- `canonical_name` / `specification` / classification / field / BOM values that
  are legitimate material identifiers are allowed; contact, vendor, price, and
  project/process free text are not.
- Set `leakage.status = checked_clean` once the record has been checked against
  the sensitive list; use `checked_with_note` if a residual risk is recorded;
  `not_applicable` only when the record carries no free text; `unchecked` is
  never a publishable state.

## Label record format

One JSON object per label, matching `review_labels.schema.json`. Required
fields:

- `label_id` — stable id, `MAT-…` for material, `CAD-…` for CAD.
- `surface` — `material` or `cad`.
- `scope` — the candidate surface being labeled (see applicability below).
- `anchor` — the candidate/source anchor the label judges (e.g. a source
  anchor `raw__C1STN_bom_material__L_ReplacementList#工作表1!r<N>`, a
  `replacement_part_id`, a drawing index key, or a BOM row reference).
- `expected` — the domain-truth value(s) for that anchor.
- `decision` — `accept` / `reject` / `replace` / `abstain` (see `V2-TASK001`
  annotation guide).
- `label_maturity` — one of the four states above.
- `label_independence` — `{labels_source, derived_from_candidate: false,
  overlap}`.
- `leakage` — `{status, note?}`.
- `reviewer` — the domain reviewer identity.
- `source_basis` — list of anchors/evidence supporting the label.
- optional `applicability` — `{in_scope, reason?}` and `note`.

## Applicability and exclusions (preregister before scoring)

Material surfaces in scope:

- node identity: `canonical_name` and `specification` correctness, and whether
  the one exact name+spec merge was correct;
- identity/join coverage: missingness (spec-missing, blank-name skips) and
  alias/collision handling;
- review-queue correctness: `consumable_station_usage_unsupported` entries are
  queue-only, never edges.

Material surfaces out of scope until a later decision: relationships
(`REPLACEMENT_FOR`, `REQUIRES_PART`) are node-only by decision 5, so there is
nothing to label.

CAD surfaces in scope:

- A01 classification authority and duplicate handling;
- A02 field extraction (title/template profiles, empty-field preservation);
- A03 drawing index and field-only-key join behavior;
- B01/B02 ASM BOM extraction and audit (extraction, classification, sequence,
  duplicate, quantity, suspicious-identifier, pending-source-review findings);
- manual BOM/audit overrides (source anchor, reviewer, reason, decision state);
- C01 relationships (parent ASM / child / confirmed-PRT / unknown-child) and
  C02 final-output correctness.

Anything not listed is excluded from scoring until the domain reviewer records
an `applicability` entry stating why.

## Fill workflow

1. The domain reviewer produces label records in the JSONL file named by this
   task (see `review_labels.schema.json`), one object per line.
2. `data_quality_reviewer` validates each record against the schema, checks
   independence (`derived_from_candidate == false`) and leakage status, and
   rejects any record that re-states the candidate or embeds a sensitive value.
3. Only `reviewed` / `adjudicated` labels flow into the domain-correctness
   scorecards; `provisional` labels are reported separately and never offset a
   safety or provenance failure.
