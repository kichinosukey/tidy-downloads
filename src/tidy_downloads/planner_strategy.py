from __future__ import annotations

import re
from pathlib import PurePosixPath

EXTENSION_SEGMENT_PATTERN = re.compile(
    r"\.(pdf|docx?|txt|md|xlsx|csv|tsv|numbers|png|jpe?g|gif|webp|svg|"
    r"mp3|wav|m4a|aac|mp4|mov|mkv|m4v|avi|"
    r"ipynb|pptx?|docx?|nb|"
    r"py|js|ts|tsx|jsx|json|ya?ml|toml|sh|"
    r"zip|tar|gz|7z|dmg|pkg|hex)$",
    re.IGNORECASE,
)

PLANNER_STRATEGY = "compact_hybrid"
COMPACT_LLM_QUEUE_CAP = 10
COMPACT_MAX_OUTPUT_TOKENS = 256


def planner_strategy_for(model: str, explicit: str | None = None) -> str:
    if explicit is not None:
        normalized = explicit.strip()
        if normalized != PLANNER_STRATEGY:
            raise ValueError(
                f"unknown planner strategy: {normalized!r}. "
                f"tidy-downloads only supports: {PLANNER_STRATEGY}"
            )
    return PLANNER_STRATEGY


def taxonomy_paths_from_rules(rules: dict[str, object]) -> list[str]:
    taxonomy = rules.get("taxonomy")
    if not isinstance(taxonomy, list):
        return []
    paths: list[str] = []
    for item in taxonomy:
        if isinstance(item, dict):
            path = item.get("path")
            if isinstance(path, str) and path.strip():
                paths.append(path.strip())
    return paths


def validate_compact_operation(
    payload: dict[str, object],
    *,
    allowed_dirs: list[str],
) -> tuple[bool, str | None]:
    destination = payload.get("destination_dir")
    if not isinstance(destination, str) or not destination.strip():
        return False, "destination_dir missing or not a string"

    cleaned = destination.strip().strip("/")
    if cleaned not in allowed_dirs:
        return False, f"destination_dir not in allowed list: {cleaned!r}"

    path = PurePosixPath(cleaned)
    for part in path.parts:
        if EXTENSION_SEGMENT_PATTERN.search(part):
            return False, f"destination_dir contains extension-like segment: {part!r}"

    confidence = payload.get("confidence")
    if confidence is not None and not isinstance(confidence, (int, float)):
        return False, "confidence is not numeric"

    return True, None
