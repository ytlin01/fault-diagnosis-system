# V2-TASK004 acceptance

- [x] Historical task packages exist under `legacy/tasks/`.
- [x] Repository-owned legacy role guides and runbooks exist under
      `legacy/agents/` and `legacy/runbooks/`.
- [x] Retired root-level and onboarding material exists under `legacy/root/`
      and `legacy/onboarding/`.
- [x] Local diagnostic and vendor-inspection archive payloads remain ignored
      and are not included as versioned historical evidence.
- [x] No repository-owned nested directory named `legacy` remains outside the
      root archive; `.venv` package internals are explicitly excluded.
- [x] Active task packages use `V2-TASK###_<name>`.
- [x] Continuing tasks map to `V2-TASK001`, `V2-TASK002`, and `V2-TASK003`.
- [x] The migration itself is recorded as `V2-TASK004`.
- [x] Workflow entry points and the task template require the new convention.
- [x] Historical task evidence is preserved rather than deleted.
- [x] Reference scans and workflow-guard validation pass.
- [x] Scoped Git status and diff checks are recorded.
