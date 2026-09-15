"""Create B-compatible submission from the shared C synthetic fixture."""
import json
from copy import deepcopy
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "evaluation"))
from fixtures import EXPECTED, PROTOCOL

def build_submission():
    return {"protocol": PROTOCOL, "observations": deepcopy(EXPECTED),
            "event_groups": [["r1", "r4"], ["r3"], ["r11"]],
            "cost": {"attempts": [], "wall_seconds": 0, "currency": "USD"}}

if __name__ == "__main__":
    out = Path(__file__).with_name("unified_fixture_submission.json")
    out.write_text(json.dumps(build_submission(), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(out)
