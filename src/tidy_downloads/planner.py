from __future__ import annotations

import shutil
from dataclasses import dataclass, field
from pathlib import Path, PurePosixPath
from typing import Callable

from tidy_downloads.llm_client import LocalLLMClient
from tidy_downloads.models import FileRecord, PlanOperation, PlanResult
from tidy_downloads.planner_compact import build_compact_plan
from tidy_downloads.planner_validate import (
    _sanitize_filename,
    _sanitize_relative_directory,
    files_are_identical,
    validate_operations,
)

ProgressCallback = Callable[[str], None]


@dataclass
class ApplyResult:
    applied_moves: int
    skipped: int
    applied_operations: list[PlanOperation] = field(default_factory=list)
    skipped_operations: list[dict[str, str]] = field(default_factory=list)


def build_plan(
    *,
    root: Path,
    files: list[FileRecord],
    existing_dirs: list[str],
    rules: dict[str, object],
    client: LocalLLMClient | None,
    batch_size: int,
    min_confidence: float,
    mock: bool,
    scan_truncated: bool,
    heuristic_directory_map: dict[str, str] | None = None,
    progress_callback: ProgressCallback | None = None,
) -> PlanResult:
    del batch_size
    return build_compact_plan(
        root=root,
        files=files,
        existing_dirs=existing_dirs,
        rules=rules,
        client=client,
        min_confidence=min_confidence,
        mock=mock,
        scan_truncated=scan_truncated,
        heuristic_directory_map=heuristic_directory_map,
        progress_callback=progress_callback,
    )


def apply_plan(root: Path, plan: PlanResult) -> ApplyResult:
    applied_moves = 0
    skipped = 0
    applied_operations: list[PlanOperation] = []
    skipped_operations: list[dict[str, str]] = []

    for operation in plan.operations:
        source_path = root / operation.source
        target_path = root / operation.target_path
        apply_issue = _validate_apply_operation(
            root=root, operation=operation, source_path=source_path, target_path=target_path
        )
        if apply_issue is not None:
            skipped += 1
            skipped_operations.append(
                {
                    "source": operation.source,
                    "target_path": operation.target_path,
                    "reason": apply_issue,
                }
            )
            continue
        if operation.action == "dedup":
            source_path.unlink()
        else:
            target_path.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(source_path), str(target_path))
        applied_moves += 1
        applied_operations.append(operation)

    return ApplyResult(
        applied_moves=applied_moves,
        skipped=skipped,
        applied_operations=applied_operations,
        skipped_operations=skipped_operations,
    )


def render_plan_markdown(plan: PlanResult) -> str:
    lines = [
        "# tidy-downloads Plan",
        "",
        f"Summary: {plan.summary}",
        "",
        "## Warnings",
    ]
    if plan.warnings:
        lines.extend([f"- {warning}" for warning in plan.warnings])
    else:
        lines.append("- none")
    lines.extend(
        [
            "",
            "## Operations",
            "",
            "| source | target | action | confidence | apply | reason |",
            "|---|---|---|---:|---|---|",
        ]
    )
    for operation in plan.operations:
        reason = operation.reason.replace("|", "/")
        apply_flag = "yes" if operation.can_apply else "no"
        lines.append(
            f"| `{operation.source}` | `{operation.target_path}` | {operation.action} "
            f"| {operation.confidence:.2f} | {apply_flag} | {reason} |"
        )
        if operation.issues:
            issue_text = "; ".join(operation.issues).replace("|", "/")
            lines.append(f"|  |  |  |  |  | issue: {issue_text} |")
    lines.append("")
    return "\n".join(lines)


def _validate_apply_operation(
    *,
    root: Path,
    operation: PlanOperation,
    source_path: Path,
    target_path: Path,
) -> str | None:
    if operation.action == "dedup":
        if not operation.can_apply:
            return "operation is marked as not applicable"
        if not source_path.exists():
            return "source file no longer exists"
        if not target_path.exists():
            return "dedup target no longer exists"
        if not files_are_identical(source_path, target_path):
            return "files are no longer identical; skipping dedup"
        return None

    if operation.action != "move":
        return "operation is not a move"
    if not operation.can_apply:
        return "operation is marked as not applicable"
    if not source_path.exists():
        return "source file no longer exists"

    cleaned_destination = _sanitize_relative_directory(operation.destination_dir)
    if cleaned_destination is None:
        return "destination_dir is no longer safe"

    cleaned_name = _sanitize_filename(operation.new_name)
    if cleaned_name is None:
        return "new_name is no longer safe"

    expected_target = str(PurePosixPath(cleaned_destination) / cleaned_name) if cleaned_destination else cleaned_name
    if expected_target != operation.target_path:
        return "target_path does not match destination_dir/new_name"

    if not target_path.is_relative_to(root):
        return "target path escapes target directory"
    if target_path.exists() and target_path != source_path:
        return "target already exists on disk"

    return None
