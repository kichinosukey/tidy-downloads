from __future__ import annotations

import unittest

from tidy_downloads.models import FileRecord
from tidy_downloads.presets import FAST_LANE_ALLOWED_EXTENSIONS, FAST_LANE_MAX_SIZE_BYTES, get_preset
from tidy_downloads.scanner import filter_fast_lane_files


class FastLanePresetTests(unittest.TestCase):
    def test_downloads_default_includes_notebook_and_legacy_office_extensions(self) -> None:
        preset = get_preset("downloads-default")
        for extension in (".ipynb", ".doc", ".pptx", ".nb"):
            self.assertIn(extension, preset.allowed_extensions)
            self.assertIn(extension, preset.destination_mapping)

    def test_only_downloads_default_preset_exists(self) -> None:
        from tidy_downloads.presets import list_presets

        self.assertEqual(list_presets(), ["downloads-default"])

    def test_filter_fast_lane_accepts_ipynb_and_large_installer_under_cap(self) -> None:
        files = [
            FileRecord(
                relative_path="lab.ipynb",
                parent_dir=".",
                name="lab.ipynb",
                extension=".ipynb",
                size_bytes=50_000,
                modified_at="2026-03-13T00:00:00+00:00",
            ),
            FileRecord(
                relative_path="Cursor.dmg",
                parent_dir=".",
                name="Cursor.dmg",
                extension=".dmg",
                size_bytes=260 * 1024 * 1024,
                modified_at="2026-03-13T00:00:00+00:00",
            ),
            FileRecord(
                relative_path="too-large.dmg",
                parent_dir=".",
                name="too-large.dmg",
                extension=".dmg",
                size_bytes=FAST_LANE_MAX_SIZE_BYTES + 1,
                modified_at="2026-03-13T00:00:00+00:00",
            ),
        ]
        result = filter_fast_lane_files(
            files,
            allowed_extensions=FAST_LANE_ALLOWED_EXTENSIONS,
            max_files=50,
            max_size_bytes=FAST_LANE_MAX_SIZE_BYTES,
        )
        selected_names = {record.name for record in result.selected_files}
        self.assertEqual(selected_names, {"lab.ipynb", "Cursor.dmg"})
        skipped_reasons = {record.name: reason for record, reason in result.skipped}
        self.assertIn("too-large.dmg", skipped_reasons)
        self.assertIn("large file", skipped_reasons["too-large.dmg"])


if __name__ == "__main__":
    unittest.main()
