import sys
from pathlib import Path
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from model_matrix import ALIASES, REPEATS, SCENARIOS, prompt_for, summarize


class ModelMatrixTests(unittest.TestCase):
    def test_fixed_six_synthetic_scenarios(self):
        self.assertEqual([s["id"] for s in SCENARIOS], ["C1", "C2", "C3", "C4", "B1", "B2"])
        self.assertEqual(len(ALIASES), 3)
        self.assertEqual(len(SCENARIOS) * len(ALIASES) * REPEATS, 54)

    def test_prompts_are_synthetic_only(self):
        for scenario in SCENARIOS:
            prompt = prompt_for(scenario)
            self.assertNotIn("姓名", prompt)
            self.assertNotIn("病历号", prompt)
            self.assertNotIn("/home/", prompt)

    def test_summary_keeps_service_failure_out_of_content_score(self):
        rows = [
            {"requested_alias": "a", "scenario": "C1", "attempts": [{"http": 503}], "format_ok": False, "correct": False, "failure_class": "format_failure"},
            {"requested_alias": "a", "scenario": "C2", "attempts": [{"http": 200}], "format_ok": True, "correct": True, "failure_class": None},
        ]
        summary = summarize(rows, ["a"])
        self.assertEqual(summary["http_200_final"], 1)
        self.assertEqual(summary["correct"], 1)
        self.assertEqual(summary["cost"]["status"], "unknown")


if __name__ == "__main__":
    unittest.main()
