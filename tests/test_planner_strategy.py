from __future__ import annotations

import unittest

from tidy_downloads.planner_strategy import PLANNER_STRATEGY, planner_strategy_for


class PlannerStrategyTests(unittest.TestCase):
    def test_always_compact_hybrid(self) -> None:
        self.assertEqual(planner_strategy_for("apple-foundationmodel", None), PLANNER_STRATEGY)
        self.assertEqual(planner_strategy_for("any-model", None), PLANNER_STRATEGY)

    def test_rejects_batch_json(self) -> None:
        with self.assertRaises(ValueError):
            planner_strategy_for("apple-foundationmodel", "batch_json")


if __name__ == "__main__":
    unittest.main()
