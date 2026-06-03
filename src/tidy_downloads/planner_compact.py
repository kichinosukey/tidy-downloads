from __future__ import annotations

import json
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from tidy_downloads.llm_client import LocalLLMClient
from tidy_downloads.models import FileRecord, PlanResult
from tidy_downloads.planner_validate import validate_operations

ProgressCallback = Callable[[str], None]
from tidy_downloads.planner_heuristics import (
    CONTRACT_KEYWORDS,
    FINANCE_KEYWORDS,
    build_mock_operations,
    heuristic_destination,
)
from tidy_downloads.planner_strategy import (
    COMPACT_LLM_QUEUE_CAP,
    COMPACT_MAX_OUTPUT_TOKENS,
    taxonomy_paths_from_rules,
    validate_compact_operation,
)

AMBIGUOUS_KEYWORDS = (
    "receipt",
    "invoice",
    "contract",
    "meeting",
    "estimate",
    "quote",
    "agreement",
    "nda",
    "budget",
    "領収",
    "請求",
    "見積",
    "契約",
)

COMPACT_SYSTEM_PROMPT = """
You classify one file into exactly one folder from the allowed list.
Return JSON only. Never delete files. Keep the original filename.
Output: {"destination_dir":"<path>","confidence":0.0-1.0,"reason":"..."}
""".strip()


@dataclass(frozen=True)
class _FileClassification:
    record: FileRecord
    heuristic_destination: str
    needs_llm: bool
    priority: int
    reason: str


def build_compact_plan(
    *,
    root: Path,
    files: list[FileRecord],
    existing_dirs: list[str],
    rules: dict[str, object],
    client: LocalLLMClient | None,
    min_confidence: float,
    mock: bool,
    scan_truncated: bool,
    heuristic_directory_map: dict[str, str] | None = None,
    progress_callback: ProgressCallback | None = None,
) -> PlanResult:
    del existing_dirs
    warnings: list[str] = []
    if scan_truncated:
        warnings.append("scan truncated because max_files limit was reached")

    allowed_dirs = taxonomy_paths_from_rules(rules)
    if not allowed_dirs:
        allowed_dirs = sorted(
            {
                heuristic_destination(record, heuristic_directory_map=heuristic_directory_map)
                for record in files
            }
        )

    if mock:
        raw_operations = build_mock_operations(files, heuristic_directory_map=heuristic_directory_map)
        summary = "compact hybrid heuristic planner grouped files by extension and keywords"
    else:
        if client is None:
            raise ValueError("client is required when mock is false")
        raw_operations, llm_warnings, summary = _build_compact_llm_operations(
            root=root,
            files=files,
            rules=rules,
            client=client,
            allowed_dirs=allowed_dirs,
            heuristic_directory_map=heuristic_directory_map,
            progress_callback=progress_callback,
        )
        warnings.extend(llm_warnings)

    operations, validation_warnings = validate_operations(
        root=root,
        files=files,
        raw_operations=raw_operations,
        min_confidence=min_confidence,
    )
    warnings.extend(validation_warnings)
    warnings = [warning for warning in warnings if "missing LLM operation" not in warning]
    return PlanResult(summary=summary, operations=operations, warnings=warnings)


def _build_compact_llm_operations(
    *,
    root: Path,
    files: list[FileRecord],
    rules: dict[str, object],
    client: LocalLLMClient,
    allowed_dirs: list[str],
    heuristic_directory_map: dict[str, str] | None,
    progress_callback: ProgressCallback | None,
) -> tuple[list[dict[str, object]], list[str], str]:
    del root, rules
    warnings: list[str] = []
    classifications = [
        _classify_file(record, heuristic_directory_map=heuristic_directory_map, allowed_dirs=allowed_dirs)
        for record in files
    ]

    skip_llm = [item for item in classifications if not item.needs_llm]
    needs_llm = sorted(
        [item for item in classifications if item.needs_llm],
        key=lambda item: (-item.priority, item.record.relative_path),
    )

    llm_queue = needs_llm[:COMPACT_LLM_QUEUE_CAP]
    truncated = needs_llm[COMPACT_LLM_QUEUE_CAP:]
    if truncated:
        warnings.append(
            f"llm queue truncated: {len(truncated)} files used heuristic fallback "
            f"(cap={COMPACT_LLM_QUEUE_CAP})"
        )

    raw_operations: list[dict[str, object]] = []
    llm_count = 0
    total_started_at = time.perf_counter()

    if progress_callback is not None:
        progress_callback(
            f"compact planning {len(files)} files "
            f"(skip_llm={len(skip_llm)}, llm_queue={len(llm_queue)}, truncated={len(truncated)})"
        )

    for index, item in enumerate(llm_queue, start=1):
        if progress_callback is not None:
            progress_callback(f"compact llm {index}/{len(llm_queue)}: {item.record.relative_path}")
        operation, file_warnings = _request_single_file(
            client=client,
            record=item.record,
            allowed_dirs=allowed_dirs,
            heuristic_destination=item.heuristic_destination,
        )
        warnings.extend(file_warnings)
        raw_operations.append(operation)
        llm_count += 1

    for item in skip_llm + truncated:
        raw_operations.append(_heuristic_operation(item.record, item.heuristic_destination, item.reason))

    elapsed = time.perf_counter() - total_started_at
    summary = (
        f"compact hybrid: {llm_count} llm, {len(skip_llm)} heuristic skip, "
        f"{len(truncated)} truncated heuristic ({elapsed:.1f}s)"
    )
    return raw_operations, warnings, summary


def _classify_file(
    record: FileRecord,
    *,
    heuristic_directory_map: dict[str, str] | None,
    allowed_dirs: list[str],
) -> _FileClassification:
    del allowed_dirs
    extension_default = heuristic_destination(record, heuristic_directory_map=heuristic_directory_map)
    keyword_destination = _keyword_destination(record)
    lowered_name = record.name.lower()

    has_ambiguous_keyword = any(keyword in lowered_name for keyword in AMBIGUOUS_KEYWORDS)
    has_keyword_conflict = (
        keyword_destination is not None
        and keyword_destination != extension_default
        and extension_default != "misc"
    )
    is_misc = extension_default == "misc"

    if is_misc:
        return _FileClassification(
            record=record,
            heuristic_destination=extension_default,
            needs_llm=True,
            priority=300,
            reason="extension maps to misc",
        )

    if has_keyword_conflict:
        return _FileClassification(
            record=record,
            heuristic_destination=keyword_destination or extension_default,
            needs_llm=True,
            priority=200,
            reason="keyword conflicts with extension default",
        )

    if has_ambiguous_keyword:
        return _FileClassification(
            record=record,
            heuristic_destination=keyword_destination or extension_default,
            needs_llm=True,
            priority=100,
            reason="ambiguous filename keyword",
        )

    if keyword_destination is not None and keyword_destination != extension_default:
        return _FileClassification(
            record=record,
            heuristic_destination=keyword_destination,
            needs_llm=True,
            priority=200,
            reason="finance/contract keyword overrides extension",
        )

    return _FileClassification(
        record=record,
        heuristic_destination=extension_default,
        needs_llm=False,
        priority=0,
        reason="extension default without conflict",
    )


def _keyword_destination(record: FileRecord) -> str | None:
    lowered_name = record.name.lower()
    if any(keyword in lowered_name for keyword in FINANCE_KEYWORDS):
        return "documents/finance"
    if any(keyword in lowered_name for keyword in CONTRACT_KEYWORDS):
        return "documents/finance"
    return None


def _request_single_file(
    *,
    client: LocalLLMClient,
    record: FileRecord,
    allowed_dirs: list[str],
    heuristic_destination: str,
) -> tuple[dict[str, object], list[str]]:
    warnings: list[str] = []
    hints = {
        "extension_default": heuristic_destination,
        "filename_keywords": _filename_keywords(record.name),
    }
    user_prompt = json.dumps(
        {
            "file": {"name": record.name, "extension": record.extension},
            "allowed_dirs": allowed_dirs,
            "hints": hints,
        },
        ensure_ascii=False,
        indent=2,
    )

    original_max_tokens = client.max_output_tokens
    client.max_output_tokens = COMPACT_MAX_OUTPUT_TOKENS
    try:
        for attempt in range(2):
            try:
                payload = client.chat_json(COMPACT_SYSTEM_PROMPT, user_prompt)
            except Exception as exc:  # noqa: BLE001
                if attempt == 0:
                    warnings.append(f"LLM request failed for {record.relative_path}: {exc}")
                    continue
                warnings.append(f"LLM failed for {record.relative_path}; used heuristic fallback: {exc}")
                return (
                    _heuristic_operation(
                        record,
                        heuristic_destination,
                        "llm request failed; heuristic fallback",
                    ),
                    warnings,
                )

            valid, issue = validate_compact_operation(payload, allowed_dirs=allowed_dirs)
            if valid:
                confidence = payload.get("confidence")
                if not isinstance(confidence, (int, float)):
                    warnings.append(f"non-numeric confidence for {record.relative_path}; using 0.85")
                destination = str(payload["destination_dir"]).strip().strip("/")
                return (
                    {
                        "source": record.relative_path,
                        "destination_dir": destination,
                        "new_name": record.name,
                        "reason": str(payload.get("reason", "compact llm classification")),
                        "confidence": float(confidence) if isinstance(confidence, (int, float)) else 0.85,
                    },
                    warnings,
                )

            if attempt == 0:
                warnings.append(
                    f"invalid compact LLM response for {record.relative_path}: {issue}; retrying once"
                )
                continue

            warnings.append(
                f"invalid compact LLM response for {record.relative_path} after retry: {issue}; "
                "heuristic fallback"
            )
            return (
                _heuristic_operation(record, heuristic_destination, "validation failed; heuristic fallback"),
                warnings,
            )
    finally:
        client.max_output_tokens = original_max_tokens

    return (
        _heuristic_operation(record, heuristic_destination, "heuristic fallback"),
        warnings,
    )


def _filename_keywords(name: str) -> list[str]:
    lowered = name.lower()
    found: list[str] = []
    for keyword in (*FINANCE_KEYWORDS, *CONTRACT_KEYWORDS, *AMBIGUOUS_KEYWORDS):
        if keyword in lowered and keyword not in found:
            found.append(keyword)
    return found


def _heuristic_operation(record: FileRecord, destination_dir: str, reason: str) -> dict[str, object]:
    return {
        "source": record.relative_path,
        "destination_dir": destination_dir,
        "new_name": record.name,
        "reason": reason,
        "confidence": 0.85,
    }
