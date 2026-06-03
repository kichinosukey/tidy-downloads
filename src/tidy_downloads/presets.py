from __future__ import annotations

import copy
from dataclasses import dataclass


@dataclass(frozen=True)
class PresetConfig:
    name: str
    rules: dict[str, object]
    destination_mapping: dict[str, str]
    allowed_extensions: frozenset[str]
    min_confidence: float
    batch_size: int
    max_files: int
    max_depth: int
    max_size_bytes: int
    skip_unknown_extensions: bool = True

    def copy_rules(self) -> dict[str, object]:
        return copy.deepcopy(self.rules)


DEFAULT_PRESET_NAME = "downloads-default"
FAST_LANE_ALLOWED_EXTENSIONS = frozenset(
    {
        ".pdf",
        ".doc",
        ".docx",
        ".txt",
        ".md",
        ".ppt",
        ".pptx",
        ".xlsx",
        ".csv",
        ".tsv",
        ".numbers",
        ".jpg",
        ".jpeg",
        ".png",
        ".gif",
        ".webp",
        ".mov",
        ".mp4",
        ".m4v",
        ".avi",
        ".mkv",
        ".mp3",
        ".m4a",
        ".wav",
        ".ipynb",
        ".nb",
        ".py",
        ".json",
        ".yaml",
        ".yml",
        ".zip",
        ".tar.gz",
        ".7z",
        ".dmg",
        ".pkg",
        ".hex",
    }
)
FAST_LANE_MAX_SIZE_BYTES = 300 * 1024 * 1024
FAST_LANE_MAX_FILES = 50

PRESETS: dict[str, PresetConfig] = {
    "downloads-default": PresetConfig(
        name="downloads-default",
        rules={
            "goal": "散らかったファイルを少数の安定したフォルダに整理する。",
            "taxonomy": [
                {"path": "documents/notes", "description": "Markdown, text, PDF のメモや資料"},
                {"path": "documents/finance", "description": "請求書、領収書、見積書、契約関連"},
                {"path": "documents/spreadsheets", "description": "CSV, XLSX, Numbers, TSV"},
                {"path": "media/images", "description": "画像, スクリーンショット, 写真"},
                {"path": "media/audio", "description": "音声ファイル"},
                {"path": "media/video", "description": "動画ファイル"},
                {"path": "projects/code", "description": "スクリプト、設定ファイル、ソースコード"},
                {"path": "archives", "description": "zip, tar.gz, 7z などの圧縮ファイル"},
                {"path": "installers", "description": "dmg, pkg, app のインストーラ類"},
                {"path": "misc", "description": "上記に当てはまらないファイル"},
            ],
            "rename_style": "元のファイル名を維持し、曖昧さが大きい場合のみ最小限の rename を行う。",
            "additional_instructions": [
                "削除提案はしない",
                "既存ディレクトリが適切なら優先する",
                "相対パスのみを使う",
                "ファイル拡張子は変えない",
            ],
        },
        destination_mapping={
            ".pdf": "documents/notes",
            ".doc": "documents/notes",
            ".docx": "documents/notes",
            ".txt": "documents/notes",
            ".md": "documents/notes",
            ".ppt": "documents/notes",
            ".pptx": "documents/notes",
            ".xlsx": "documents/spreadsheets",
            ".csv": "documents/spreadsheets",
            ".tsv": "documents/spreadsheets",
            ".numbers": "documents/spreadsheets",
            ".jpg": "media/images",
            ".jpeg": "media/images",
            ".png": "media/images",
            ".gif": "media/images",
            ".webp": "media/images",
            ".ipynb": "projects/code",
            ".nb": "projects/code",
            ".py": "projects/code",
            ".json": "projects/code",
            ".yaml": "projects/code",
            ".yml": "projects/code",
            ".zip": "archives",
            ".tar.gz": "archives",
            ".7z": "archives",
            ".dmg": "installers",
            ".pkg": "installers",
            ".mov": "media/video",
            ".mp4": "media/video",
            ".m4v": "media/video",
            ".avi": "media/video",
            ".mkv": "media/video",
            ".mp3": "media/audio",
            ".m4a": "media/audio",
            ".wav": "media/audio",
            ".hex": "misc",
        },
        allowed_extensions=FAST_LANE_ALLOWED_EXTENSIONS,
        min_confidence=0.80,
        batch_size=15,
        max_files=FAST_LANE_MAX_FILES,
        max_depth=0,
        max_size_bytes=FAST_LANE_MAX_SIZE_BYTES,
    ),
}


def get_preset(name: str) -> PresetConfig:
    try:
        return PRESETS[name]
    except KeyError as exc:
        supported = ", ".join(sorted(PRESETS))
        raise ValueError(f"unknown preset: {name}. Supported presets: {supported}") from exc


def list_presets() -> list[str]:
    return sorted(PRESETS)
