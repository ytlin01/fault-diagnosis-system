# V2-TASK016 -> V2-TASK017 bounce-back: re-freeze under a retained salt

## Identity

- From: `V2-TASK016_material_cad_independent_validation` (independent reviewer:
  `data_quality_reviewer`)
- To: `V2-TASK017_material_parser_integration` (implementation owner:
  `data_pipeline_kg_engineer`)
- Date: 2026-09-01
- Trigger: determinism reproduction of frozen run `material_cef539710b861b7d`
  failed; the data owner confirmed the run1 salt is lost and chose the
  re-freeze path over re-scoping the acceptance.
- Status: **bounce-back — new run and new handoff requested**

## Findings (full evidence in V2-TASK016 notes.md, 2026-09-01 entries)

- **F4 (blocking, determinism).** A fresh-dir rerun (`run2/`, run_id
  `material_d2cb8e547f07252a`) did not reproduce `material_cef539710b861b7d`.
  Input/config/schema/code digests were identical to run1; non-salted
  artifacts were byte-identical; all 52 node keys, 53 lineage anchors,
  merge-audit and review-queue contents were identical; only the salted `RP_`
  ids differed (0 of 52 in common). Root cause: run2 executed with a different
  `FAULTDX_MASKING_SALT`, and the run1 salt has since been confirmed lost, so
  `material_cef539710b861b7d` is permanently irreproducible (sha256 is
  one-way; the salt cannot be recovered from the frozen artifacts).
- **F1 (documentation).** The current handoff's `lineage.jsonl` sha256 line is
  a 62-hex transcription (missing `c0`); the authoritative manifest value
  matches the file. Fix rides along with the new handoff.
- **F2 (informational, no action).** `lineage.jsonl` is a JSON array, not
  line-delimited JSON, and lineage records carry no run_id; run-to-lineage
  binding is via the manifest's content digest. Change only if trivially
  bundled with other work; otherwise defer.
- **F3 (standing note).** The raw input digest is manifest-declared; TASK016
  cannot independently recompute it (raw access not granted). No action.

## Remediation requirements for the new freeze

1. Generate a new governed salt and **retain** it in the data owner's secret
   store. Settled by the data owner (2026-09-01): a **single shared salt** —
   one `FAULTDX_MASKING_SALT` for both masking tokenization and parser
   identity, matching the frozen config (`identity.salt_env`); a split
   identity salt is deferred as a possible future reviewed config change. The
   value must be high-entropy CSPRNG output (>= 32 bytes; a random token, not
   a passphrase — tokenized values are exposed and the salt is the
   dictionary-attack defense). Record the retention rule in the runbook and
   the masking subtask notes: set, run, clear from env, retain the value.
2. Record a non-reversible salt fingerprint (e.g. sha256 of the salt value) in
   the run manifest so future salt mismatches are detectable without exposing
   the secret. Consider whether `manifest_version` should bump for the
   additive field. The code change is in TASK017's write set; TASK016 does not
   implement it.
3. Produce the new candidate run and a byte-equivalence rerun **both under the
   retained salt**, into fresh output directories (e.g. `run3/` new candidate,
   `run4/` reproduction). `run2/` is retained as F4 evidence, and the builder
   refuses to overwrite existing artifacts in any case.
4. The new handoff declares: both run_ids, both manifests, all artifact
   digests, the shared salt fingerprint, the corrected lineage digest (F1),
   and a salt-provenance annotation that pre-existing masked derivatives
   predate the new salt (co-source, non-promoting; divergent provenance, not a
   violation).

## What TASK016 will verify on the new handoff

1. Digest re-computation for both runs against the new handoff and manifests.
2. run4 reproduces run3: identical run_id and all five artifact sha256s
   byte-for-byte; salt fingerprints equal across both manifests.
3. Standard gate battery on the new candidate: Schema 4.2 and semantic
   validation, counts, lineage anchors, leak report, rollback flags.
4. The determinism acceptance line closes only on that evidence.

## Constraints

- TASK016 does not modify candidate code, configuration, or artifacts; this
  request is the review output. The frozen `run1/` stays immutable; `run2/`
  stays as mismatch evidence until the finding is closed.
- Blocker 2 (independent domain labels) proceeds in parallel and is
  unaffected: the label scaffold anchors on source rows
  (`…#工作表1!r<N>`), not salted ids, so labels survive the re-freeze.
- This bounce-back is the designed failure path per the current handoff's
  reviewer instructions, not a defect in the review process.
