from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path, PurePosixPath


PROTECTED_EXACT = {
    "AGENTS.md",
    "HANDOFF_README.md",
    "HANDOFF_INTEGRATION.md",
    "docs/tasks/TASK_TEMPLATE.md",
    ".github/CODEOWNERS",
    ".github/pull_request_template.md",
    ".github/workflows/workflow-guard.yml",
    "scripts/check_workflow_guard.py",
}

PROTECTED_PREFIXES = (
    ".codex/agents/",
    "docs/agents/",
)

ACK_LINE = (
    "- [x] This PR intentionally changes protected workflow files and requires "
    "code owner review."
)

PLACEHOLDER_VALUES = {"", "tbd", "n/a", "na", "none", "unknown", "<fill me>"}
V2_TASK_ID = re.compile(r"^(?:R1-TASK\d{2}|V2-TASK\d{3})$")
V2_TASK_PATH = re.compile(r"^docs/tasks/(?:R1-TASK\d{2}|V2-TASK\d{3})_[^/]+/")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Fail when protected workflow files change without explicit PR intent."
    )
    parser.add_argument(
        "--changed-file",
        action="append",
        default=[],
        help="A changed file path. Can be passed multiple times.",
    )
    parser.add_argument(
        "--changed-files-file",
        help="A newline-delimited file containing changed file paths.",
    )
    parser.add_argument(
        "--pr-body-text",
        default="",
        help="Pull request body text.",
    )
    parser.add_argument(
        "--pr-body-file",
        help="A file containing the pull request body.",
    )
    return parser.parse_args()


def normalize_path(path: str) -> str:
    normalized = path.strip().replace("\\", "/")
    while normalized.startswith("./"):
        normalized = normalized[2:]
    return str(PurePosixPath(normalized))


def parse_changed_record(record: str) -> list[tuple[str, str]]:
    """Parse a plain path or one `git diff --name-status` record."""

    fields = record.strip().split("\t")
    if len(fields) >= 3 and fields[0].startswith(("R", "C")):
        return [("D", normalize_path(fields[1])), ("A", normalize_path(fields[2]))]
    if len(fields) >= 2 and re.fullmatch(r"[A-Z?][0-9]*", fields[0]):
        return [(fields[0][0], normalize_path(fields[1]))]
    return [("M", normalize_path(record))]


def load_changed_files(args: argparse.Namespace) -> list[tuple[str, str]]:
    records = [path for path in args.changed_file if path.strip()]

    if args.changed_files_file:
        content = Path(args.changed_files_file).read_text(encoding="utf-8")
        records.extend(line for line in content.splitlines() if line.strip())

    changed = [change for record in records for change in parse_changed_record(record)]

    seen: set[tuple[str, str]] = set()
    ordered: list[tuple[str, str]] = []
    for change in changed:
        if change not in seen:
            ordered.append(change)
            seen.add(change)
    return ordered


def load_pr_body(args: argparse.Namespace) -> str:
    if args.pr_body_file:
        return Path(args.pr_body_file).read_text(encoding="utf-8")
    return args.pr_body_text or ""


def is_protected(path: str) -> bool:
    if path in PROTECTED_EXACT:
        return True
    return any(path.startswith(prefix) for prefix in PROTECTED_PREFIXES)


def extract_field(body: str, field_name: str) -> str:
    pattern = rf"(?im)^\-\s*{re.escape(field_name)}\s*:\s*(.+?)\s*$"
    match = re.search(pattern, body)
    if not match:
        return ""
    return match.group(1).strip()


def is_meaningful(value: str) -> bool:
    return value.strip().lower() not in PLACEHOLDER_VALUES


def main() -> int:
    args = parse_args()
    changed_files = load_changed_files(args)
    pr_body = load_pr_body(args)
    protected_changed = [path for _, path in changed_files if is_protected(path)]
    problems: list[str] = []

    invalid_task_paths = [
        path
        for status, path in changed_files
        if status != "D"
        and path.startswith("docs/tasks/")
        and path not in {"docs/tasks/TASK_TEMPLATE.md", "docs/tasks/README.md"}
        and not V2_TASK_PATH.match(path)
    ]
    if invalid_task_paths:
        problems.append(
            "Active task paths must use docs/tasks/R1-TASK##_<name>/ (historical V2-TASK### accepted): "
            + ", ".join(invalid_task_paths)
        )

    if not protected_changed:
        if problems:
            for problem in problems:
                print(f"ERROR: {problem}")
            return 1
        print("workflow-guard: no protected workflow files changed.")
        return 0

    if ACK_LINE not in pr_body:
        problems.append(
            "Protected files changed but the workflow-guard acknowledgement checkbox is not checked."
        )

    governance_task = extract_field(pr_body, "Governance Task")
    if not is_meaningful(governance_task):
        problems.append(
            "Protected files changed but 'Governance Task' is missing or still a placeholder."
        )
    elif not V2_TASK_ID.fullmatch(governance_task):
        problems.append(
            "Protected workflow changes must name a Governance Task using R1-TASK## (or a historical V2-TASK###)."
        )

    impact_summary = extract_field(pr_body, "Impact Summary")
    if not is_meaningful(impact_summary):
        problems.append(
            "Protected files changed but 'Impact Summary' is missing or still a placeholder."
        )

    if problems:
        print("workflow-guard: protected workflow files were modified:")
        for path in protected_changed:
            print(f"  - {path}")
        print()
        for problem in problems:
            print(f"ERROR: {problem}")
        return 1

    print("workflow-guard: protected workflow change acknowledged.")
    for path in protected_changed:
        print(f"  - {path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

