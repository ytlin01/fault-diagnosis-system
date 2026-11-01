# Public AI workflow handoff: r1-data

## Plan and governance decision

The owner requested that reusable agent instructions and sanitized handoff
documents be committed alongside code to demonstrate AI-assisted development.
This replaces the blanket local-only harness rule. Private task packages,
transcripts, credentials, source payloads, and runtime output remain excluded.

## Changed files

AGENTS.md, HANDOFF_README.md, HANDOFF_INTEGRATION.md, docs/agents/README.md,
docs/agents/data_workflow_lead.md, .gitignore, this HANDOFF.md, and the restored
docs/agents/code_review_agent.md guide. These entry points must agree on public
documentation eligibility and branch authority. Executable wrappers are absent
from this snapshot and are not fabricated by this change.

## State and validation

- Planned: public, branch-specific AI workflow documentation.
- Implemented: documentation policy and branch-name alignment; no pipeline changes.
- Validated: text, links, staged paths, and whitespace are checked before commit.
- Independently reviewed: not claimed.
- Released: not claimed; this change does not push to GitHub.

No data contents or application tests are needed for this documentation change.
Existing task-renumbering and archive edits remain separate, uncommitted work.

## Handoff and risks

The data branch owns governed packages, contracts, and Data RC evidence. The
system branch owns UI and runtime. The integration scaffold may exist now, but
accepted data and recorded validation are required before activation or release.
Main contains release documentation and approved snapshots. Data history has
separate ancestry; import only reviewed files or explicitly approve a reviewed
unrelated-history merge. See HANDOFF_README.md for the durable reading order.