# V2-TASK005 acceptance

- [x] Every pre-migration `docs/data/` file exists at either its retained path
      or its mapped `legacy/data/docs/` path.
- [x] Retained files have an explicit active-v2 relationship or are the
      V2-TASK003 Route B schema-boundary decision.
- [x] Historical files are preserved under `legacy/data/docs/`.
- [ ] V2-TASK001 outputs exist under `docs/outputs/` with current identifiers.
- [x] The former root `outputs/` subtree is absent after the move.
- [x] Explicit stale paths are repaired.
- [ ] Scoped validation and Git review pass against the current worktree.
