"""Generate a fully synthetic E1 event-table submission."""
import json
from pathlib import Path
from temporal_roles import materialize_event_table

SCOPE = {"case_token": "CASE-SYNTHETIC", "document_token": "DOC-001", "page_number": 1}

def build_submission():
    headers = [
        SCOPE | {"date": "2026-01-04", "text": "采样时间：2026-01-04", "role_label": "采样时间", "evidence_id": "E-H-SAMPLE", "bbox": [[0, 0], [500, 0], [500, 24], [0, 24]]},
        SCOPE | {"date": "2026-01-05", "text": "报告时间：2026-01-05", "role_label": "报告时间", "evidence_id": "E-H-REPORT", "bbox": [[0, 100], [500, 100], [500, 124], [0, 124]]},
    ]
    rows = [
        SCOPE | {"row_id": "ROW-GLU", "test_name": "X", "value": "4.2", "unit": "U", "evidence_id": "E-R-GLU", "bbox": [[20, 30], [480, 30], [480, 48], [20, 48]]},
        SCOPE | {"row_id": "ROW-ALT", "test_name": "Y", "value": "18", "unit": "U/L", "evidence_id": "E-R-ALT", "bbox": [[20, 55], [480, 55], [480, 73], [20, 73]]},
        SCOPE | {"row_id": "ROW-HGB", "test_name": "Z", "value": "132", "unit": "g/L", "evidence_id": "E-R-HGB", "bbox": [[20, 130], [480, 130], [480, 148], [20, 148]]},
    ]
    events = materialize_event_table(headers, rows)
    observations = []
    for i, event in enumerate(events, 1):
        ref = event["evidence"][1] if len(event["evidence"]) > 1 else None
        role = event["temporal_role"]
        assertions = [{"role": "sampling", "relative_day": 0 if role == "sampling" else None,
              "coordinate_id": "C1" if role == "sampling" else None, "date_ref": ref if role == "sampling" else None,
              "role_ref": ref if role == "sampling" else None, "scope_ref": "synthetic-table" if role == "sampling" else None,
              "binding_status": event["binding_status"] if role == "sampling" else "unknown"}]
        if role == "report":
            assertions.append({"role": "report", "relative_day": 1, "coordinate_id": "C1", "date_ref": ref,
              "role_ref": ref, "scope_ref": "synthetic-table", "binding_status": "explicit"})
        observations.append({"observation_id": f"obs-{i}", "case_token": SCOPE["case_token"], "item": rows[i-1]["test_name"],
            "value": event["value"], "unit": event["unit"], "source_refs": [event["evidence"][0]],
            "time_assertions": assertions})
    return {"protocol": "research-card-v0.3/shared-synthetic-v0.1", "observations": observations,
            "summary": {"event_count": len(events), "resolved_count": sum(e["binding_status"] == "explicit" for e in events), "source": "synthetic_only"}}

if __name__ == "__main__":
    out = Path(__file__).with_name("synthetic_submission.json")
    out.write_text(json.dumps(build_submission(), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(out)
