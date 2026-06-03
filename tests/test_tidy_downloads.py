from __future__ import annotations

import io
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from tidy_downloads.cli import _build_planner_manifest_section, build_client, main, parse_args, resolve_output_root
from tidy_downloads.env_loader import load_dotenv
from tidy_downloads.planner_strategy import PLANNER_STRATEGY


REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = REPO_ROOT / "src"


class FakeTTY(io.StringIO):
    def isatty(self) -> bool:
        return True


class TidyDownloadsTests(unittest.TestCase):
    def run_cli(self, *args: str) -> subprocess.CompletedProcess[str]:
        env = os.environ.copy()
        env["PYTHONPATH"] = str(SRC_ROOT)
        return subprocess.run(
            [sys.executable, "-m", "tidy_downloads", *args],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            env=env,
            check=False,
        )

    @staticmethod
    def extract_run_dir(stdout: str) -> Path:
        for line in stdout.splitlines():
            if line.startswith("[RESULT]") and "run_dir=" in line:
                for token in line.split():
                    if token.startswith("run_dir="):
                        return Path(token.split("=", 1)[1])
        raise AssertionError(f"run_dir not found in stdout: {stdout}")

    def test_plan_mode_writes_manifest_v2_and_keeps_files_in_place(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "messy"
            root.mkdir()
            (root / "receipt-2026.pdf").write_text("finance", encoding="utf-8")
            (root / "notes.txt").write_text("notes", encoding="utf-8")

            result = self.run_cli("plan", "--target-dir", str(root), "--mock")

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("planned_moves=2", result.stdout)
            self.assertTrue((root / "receipt-2026.pdf").exists())
            self.assertTrue((root / "notes.txt").exists())

            run_dir = self.extract_run_dir(result.stdout)
            manifest = json.loads((run_dir / "manifest.json").read_text(encoding="utf-8"))
            self.assertEqual(manifest["version"], 2)
            self.assertEqual(manifest["mode"], "plan")
            self.assertFalse(manifest["fast_lane"])
            self.assertEqual(manifest["counts"]["planned_moves"], 2)
            self.assertEqual(manifest["planner"]["strategy"], PLANNER_STRATEGY)

            plan = json.loads((run_dir / "plan.json").read_text(encoding="utf-8"))
            operations = {item["source"]: item for item in plan["operations"]}
            self.assertEqual(operations["receipt-2026.pdf"]["target_path"], "documents/finance/receipt-2026.pdf")
            self.assertEqual(operations["notes.txt"]["target_path"], "documents/notes/notes.txt")

    def test_plan_manifest_includes_planner_section_and_extended_timings(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "messy"
            root.mkdir()
            (root / "notes.txt").write_text("notes", encoding="utf-8")

            result = self.run_cli("plan", "--target-dir", str(root), "--mock")
            self.assertEqual(result.returncode, 0, result.stderr)

            run_dir = self.extract_run_dir(result.stdout)
            manifest = json.loads((run_dir / "manifest.json").read_text(encoding="utf-8"))
            self.assertEqual(manifest["planner"]["provider"], "mock")
            self.assertEqual(manifest["planner"]["transport"], "heuristic")
            self.assertEqual(manifest["planner"]["llm_request_count"], 0)
            self.assertIn("llm_seconds", manifest["timings"])
            self.assertIn("validation_seconds", manifest["timings"])

    def test_run_fast_lane_yes_uses_same_manifest_for_apply(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "downloads"
            root.mkdir()
            (root / "photo.png").write_bytes(b"png")

            result = self.run_cli(
                "run",
                "--target-dir",
                str(root),
                "--fast-lane",
                "--mock",
                "--yes",
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            run_dir = self.extract_run_dir(result.stdout)
            manifest = json.loads((run_dir / "manifest.json").read_text(encoding="utf-8"))
            self.assertTrue(manifest["fast_lane"])
            self.assertEqual(manifest["counts"]["planned_moves"], 1)
            self.assertEqual(manifest["counts"]["applied_moves"], 1)
            self.assertFalse((root / "photo.png").exists())
            self.assertTrue((root / "media/images/photo.png").exists())

    def test_planner_manifest_section_uses_compact_strategy(self) -> None:
        planner = _build_planner_manifest_section(client=None, batch_size=15, mock=True)
        self.assertEqual(planner["strategy"], PLANNER_STRATEGY)

    def test_resolve_output_root_defaults_to_repo_runs_dir(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "Downloads"
            target.mkdir()
            output_root = resolve_output_root(None, target)
            self.assertEqual(output_root, REPO_ROOT / ".tidy-downloads-runs")

    def test_main_entry(self) -> None:
        stdout = io.StringIO()
        with self.assertRaises(SystemExit) as ctx:
            main(["plan", "--help"], stdout=stdout)
        self.assertEqual(ctx.exception.code, 0)


if __name__ == "__main__":
    unittest.main()
