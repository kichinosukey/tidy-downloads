from __future__ import annotations

import hashlib
import unicodedata
from pathlib import Path, PurePosixPath

from tidy_downloads.models import FileRecord, PlanOperation


def validate_operations(
    *,
    root: Path,
    files: list[FileRecord],
    raw_operations: list[dict[str, object]],
    min_confidence: float,
) -> tuple[list[PlanOperation], list[str]]:
    files_by_source = {record.relative_path: record for record in files}
    nfc_to_source = {unicodedata.normalize("NFC", k): k for k in files_by_source}
    operations_by_source: dict[str, dict[str, object]] = {}
    warnings: list[str] = []

    for item in raw_operations:
        source = item.get("source")
        if isinstance(source, str):
            matched = files_by_source.get(source) or files_by_source.get(
                nfc_to_source.get(unicodedata.normalize("NFC", source), "")
            )
            if matched is not None:
                operations_by_source[matched.relative_path] = item

    for source in files_by_source:
        if source not in operations_by_source:
            warnings.append(f"missing LLM operation for {source}; keeping file in place")

    operations: list[PlanOperation] = []
    target_to_source: dict[str, str] = {}
    for source, record in files_by_source.items():
        raw = operations_by_source.get(source)
        if raw is None:
            operation = _make_operation(
                record=record,
                destination_dir=record.parent_dir if record.parent_dir != "." else "",
                new_name=record.name,
                reason="no LLM proposal received",
                confidence=0.0,
                min_confidence=min_confidence,
            )
        else:
            operation = _make_operation(
                record=record,
                destination_dir=str(raw.get("destination_dir", "")),
                new_name=str(raw.get("new_name", record.name)),
                reason=str(raw.get("reason", "no reason provided")),
                confidence=_coerce_confidence(raw.get("confidence")),
                min_confidence=min_confidence,
            )

        existing_source = target_to_source.get(operation.target_path)
        if existing_source and existing_source != operation.source:
            operation.can_apply = False
            operation.issues.append(f"target collision with {existing_source}")
        else:
            target_to_source[operation.target_path] = operation.source

        absolute_target = root / operation.target_path
        absolute_source = root / operation.source
        if absolute_target.exists() and absolute_target != absolute_source and operation.action == "move":
            if _files_are_identical(absolute_source, absolute_target):
                operation.action = "dedup"
                operation.reason = f"identical to existing {operation.target_path}; remove source"
            else:
                unique = _find_unique_target(root, operation.target_path)
                operation.target_path = unique
                operation.new_name = PurePosixPath(unique).name

        operations.append(operation)

    return operations, warnings


def _make_operation(
    *,
    record: FileRecord,
    destination_dir: str,
    new_name: str,
    reason: str,
    confidence: float,
    min_confidence: float,
) -> PlanOperation:
    issues: list[str] = []
    cleaned_destination = _sanitize_relative_directory(destination_dir)
    if cleaned_destination is None:
        cleaned_destination = record.parent_dir if record.parent_dir != "." else ""
        issues.append("invalid destination_dir; kept original directory")

    cleaned_name = _sanitize_filename(new_name)
    if cleaned_name is None:
        cleaned_name = record.name
        issues.append("invalid new_name; kept original filename")

    if record.extension:
        candidate_suffix = Path(cleaned_name).suffix.lower()
        if candidate_suffix != record.extension.lower():
            cleaned_name = f"{Path(cleaned_name).stem}{record.extension}"
            issues.append("extension change was blocked")

    target_path = str(PurePosixPath(cleaned_destination) / cleaned_name) if cleaned_destination else cleaned_name
    action = "noop" if target_path == record.relative_path else "move"
    can_apply = action == "move" and confidence >= min_confidence and not issues

    if confidence < min_confidence and action == "move":
        issues.append(f"confidence below threshold {min_confidence:.2f}")
        can_apply = False

    if action == "noop":
        can_apply = False

    return PlanOperation(
        source=record.relative_path,
        destination_dir=cleaned_destination,
        new_name=cleaned_name,
        target_path=target_path,
        action=action,
        confidence=confidence,
        reason=reason,
        can_apply=can_apply,
        issues=issues,
    )


def _sanitize_relative_directory(value: str) -> str | None:
    candidate = value.strip().strip("/")
    if candidate in {"", "."}:
        return ""
    path = PurePosixPath(candidate)
    if path.is_absolute():
        return None
    if any(part in {"..", "."} for part in path.parts):
        return None
    return path.as_posix()


def _sanitize_filename(value: str) -> str | None:
    candidate = value.strip()
    if not candidate:
        return None
    path = PurePosixPath(candidate)
    if path.is_absolute():
        return None
    if len(path.parts) != 1:
        return None
    if path.name in {".", ".."}:
        return None
    return path.name


def _coerce_confidence(value: object) -> float:
    if isinstance(value, (int, float)):
        return max(0.0, min(1.0, float(value)))
    return 0.0


def _file_hash(path: Path) -> str:
    hasher = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            hasher.update(chunk)
    return hasher.hexdigest()


def files_are_identical(a: Path, b: Path) -> bool:
    try:
        if a.stat().st_size != b.stat().st_size:
            return False
        return _file_hash(a) == _file_hash(b)
    except OSError:
        return False


def _find_unique_target(root: Path, target_path: str) -> str:
    p = PurePosixPath(target_path)
    stem = p.stem
    suffix = p.suffix
    parent = p.parent.as_posix()
    for i in range(1, 100):
        candidate_name = f"{stem}_{i}{suffix}"
        candidate = str(PurePosixPath(parent) / candidate_name) if parent != "." else candidate_name
        if not (root / candidate).exists():
            return candidate
    return target_path


def _files_are_identical(a: Path, b: Path) -> bool:
    return files_are_identical(a, b)
