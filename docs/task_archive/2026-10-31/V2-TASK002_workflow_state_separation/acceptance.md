# V2-TASK002_workflow_state_separation - Acceptance

- [x] `AGENTS.md` defines the durable authority chain.
- [x] Workflow files require explicit permission before reading `data/` contents.
- [x] `HANDOFF_README.md` contains no current priority or task-status ledger.
- [x] `HANDOFF_INTEGRATION.md` is policy, not a live integration ledger.
- [x] Active role guides and executable wrappers do not use the handoff as a
  source of current state.
- [x] Task packages are authoritative for operational state.
- [x] The workflow guard protects `.codex/agents/`.
- [x] Workflow scans and guard validation pass.
- [x] Final diff review confirms no unrelated user changes were overwritten.
