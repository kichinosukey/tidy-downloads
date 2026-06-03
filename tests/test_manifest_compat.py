from __future__ import annotations

import json
import unittest
from pathlib import Path

from tidy_downloads.models import PlanOperation, PlanResult

FIXTURE = Path(__file__).resolve().parent / "fixtures" / "manifest_v2_sample.json"

MINIMAL_MANIFEST_FIELDS = {
    "version",
    "created_at",
    "target_dir",
    "mode",
    "fast_lane",
    "preset",
    "rules",
    "planner",
    "summary",
    "counts",
    "warnings",
    "timings",
    "operations",
}


class ManifestCompatTests(unittest.TestCase):
    def test_manifest_v2_round_trips_operations(self) -> None:
        manifest = json.loads(FIXTURE.read_text(encoding="utf-8"))
        self.assertEqual(manifest["version"], 2)
        self.assertEqual(set(manifest.keys()) & MINIMAL_MANIFEST_FIELDS, MINIMAL_MANIFEST_FIELDS)

        plan = PlanResult.from_dict(
            {
                "summary": manifest.get("summary", ""),
                "warnings": manifest.get("warnings", []),
                "operations": manifest.get("operations", []),
            }
        )
        self.assertEqual(len(plan.operations), 1)
        first = plan.operations[0]
        self.assertIsInstance(first, PlanOperation)
        restored = PlanOperation.from_dict(first.as_dict())
        self.assertEqual(restored.source, first.source)
        self.assertEqual(restored.target_path, first.target_path)
        self.assertEqual(restored.can_apply, first.can_apply)

    def test_planner_section_shape(self) -> None:
        manifest = json.loads(FIXTURE.read_text(encoding="utf-8"))
        planner = manifest["planner"]
        for key in ("provider", "transport", "api_mode", "model", "batch_size", "strategy", "llm_request_count"):
            self.assertIn(key, planner)
        self.assertEqual(planner["strategy"], "compact_hybrid")


if __name__ == "__main__":
    unittest.main()
