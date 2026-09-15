"""Print anonymous diagnostic examples; these are authored mutations, not B runs."""
from copy import deepcopy
import json

from fixtures import correct_prediction, gold_fixture
from scorer import score


def demo_reports():
    good = correct_prediction()
    submissions = {"correct": good}
    wrong = deepcopy(good)
    a, b = wrong["observations"][0]["time_assertions"]
    a["role"], b["role"] = b["role"], a["role"]
    submissions["wrong_time_role"] = wrong
    missing = deepcopy(good)
    missing["observations"].pop(2)
    submissions["missing_repeat"] = missing
    merge = deepcopy(good)
    merge["event_groups"] = [["r1", "r4", "r3", "r11"]]
    submissions["false_merge"] = merge
    extra = deepcopy(good)
    row = deepcopy(extra["observations"][0])
    row["observation_id"] = "extra-output"
    extra["observations"].append(row)
    submissions["extra_output"] = extra
    return {"kind": "synthetic_scorer_self_check", "model_calls_executed": 0,
            "real_cases_processed": 0,
            "reports": {name: score(gold_fixture(), pred) for name, pred in submissions.items()}}


if __name__ == "__main__":
    print(json.dumps(demo_reports(), ensure_ascii=False, indent=2, sort_keys=True))
