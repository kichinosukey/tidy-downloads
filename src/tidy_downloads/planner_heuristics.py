from __future__ import annotations

from tidy_downloads.models import FileRecord, PlanOperation

HEURISTIC_DIRECTORY_MAP = {
    ".png": "media/images",
    ".jpg": "media/images",
    ".jpeg": "media/images",
    ".gif": "media/images",
    ".webp": "media/images",
    ".svg": "media/images",
    ".mp3": "media/audio",
    ".wav": "media/audio",
    ".m4a": "media/audio",
    ".aac": "media/audio",
    ".mp4": "media/video",
    ".mov": "media/video",
    ".mkv": "media/video",
    ".m4v": "media/video",
    ".avi": "media/video",
    ".pdf": "documents/notes",
    ".md": "documents/notes",
    ".txt": "documents/notes",
    ".doc": "documents/notes",
    ".docx": "documents/notes",
    ".ppt": "documents/notes",
    ".pptx": "documents/notes",
    ".csv": "documents/spreadsheets",
    ".tsv": "documents/spreadsheets",
    ".xlsx": "documents/spreadsheets",
    ".numbers": "documents/spreadsheets",
    ".ipynb": "projects/code",
    ".nb": "projects/code",
    ".py": "projects/code",
    ".js": "projects/code",
    ".ts": "projects/code",
    ".tsx": "projects/code",
    ".jsx": "projects/code",
    ".json": "projects/code",
    ".yaml": "projects/code",
    ".yml": "projects/code",
    ".toml": "projects/code",
    ".sh": "projects/code",
    ".zip": "archives",
    ".tar": "archives",
    ".gz": "archives",
    ".7z": "archives",
    ".dmg": "installers",
    ".pkg": "installers",
    ".hex": "misc",
}

FINANCE_KEYWORDS = ("invoice", "receipt", "estimate", "quote", "請求", "領収", "見積")
CONTRACT_KEYWORDS = ("contract", "agreement", "nda", "契約")


def heuristic_destination(
    record: FileRecord, *, heuristic_directory_map: dict[str, str] | None = None
) -> str:
    lowered_name = record.name.lower()
    if any(keyword in lowered_name for keyword in FINANCE_KEYWORDS):
        return "documents/finance"
    if any(keyword in lowered_name for keyword in CONTRACT_KEYWORDS):
        return "documents/finance"
    directory_map = heuristic_directory_map or HEURISTIC_DIRECTORY_MAP
    return directory_map.get(record.extension, "misc")


def build_mock_operations(
    files: list[FileRecord], *, heuristic_directory_map: dict[str, str] | None = None
) -> list[dict[str, object]]:
    operations = []
    for record in files:
        destination_dir = heuristic_destination(
            record, heuristic_directory_map=heuristic_directory_map
        )
        operations.append(
            {
                "source": record.relative_path,
                "destination_dir": destination_dir,
                "new_name": record.name,
                "reason": "heuristic classification based on extension and filename",
                "confidence": 0.85,
            }
        )
    return operations


def build_skipped_operation(record: FileRecord, reason: str, *, issue: str | None = None) -> PlanOperation:
    cleaned_parent = record.parent_dir if record.parent_dir != "." else ""
    issues = [issue or reason]
    return PlanOperation(
        source=record.relative_path,
        destination_dir=cleaned_parent,
        new_name=record.name,
        target_path=record.relative_path,
        action="noop",
        confidence=0.0,
        reason=reason,
        can_apply=False,
        issues=issues,
    )
