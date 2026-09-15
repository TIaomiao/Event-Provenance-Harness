"""Hand-authored SYNTHETIC DEVELOPMENT material, not a held-out reference set.

Evidence text and reference annotations are explicit editorial fixtures. No B
implementation, parser, model response, or scorer creates the expected answers.
"""
from copy import deepcopy

PROTOCOL = "research-card-v0.3/shared-synthetic-v0.1"
CASE = "SYNTHETIC-ONLY"

# Human-readable source material, distinct from the reference annotations below.
SOURCE_MATERIAL = [
    ("D1", 1, "T1", "采样 day 0；报告 day 1；X 4.2 U；Y 7 U。坐标 C1。"),
    ("D2", 1, "T2", "重新采样 day 3；报告 day 4；X 4.2 U。坐标 C1。"),
    ("D3", 1, "T3", "明确副本：复述 D1 的 X 检验，采样 day 0；报告 day 1；X 4.2 U。坐标 C1。"),
    ("D4", 1, "T4", "仅报告 day 2；X 5.1 U。坐标 C1。未写采样日期。"),
    ("D5", 1, "T5", "文档 day 2；X 6 U。坐标 C1。未写检验日期。"),
    ("D6", 1, "T6", "采样 day 0；X 8 U。独立文档坐标 C2，与 C1 无锚点映射。"),
    ("D1", 1, "T7", "另一独立表格：采样 day 2；X 9 U。坐标 C1。"),
    ("D8", 1, "T8", "同一 X 1 U 行有两条明确采样日期：day 0 和 day 1。坐标 C1，未裁决。"),
    ("D9", 1, "T9", "无角色日期 day 0；X 2 U。坐标 C1，日期到行归属未决。"),
    ("D10", 1, "T10", "明确是另一份重新采样：采样 day 0；X 4.2 U。坐标 C1，非 D1 副本。"),
    ("D11", 1, "T11", "采样 day 5 表头仅支持本页；坐标 C1。"),
    ("D11", 2, "T12", "X 3 U；未提供上一页表头作用于本页的证据。"),
]


def assertion(role, day=None, coordinate=None, date=None, label=None, scope=None, status="explicit"):
    # Identical printed labels in distinct tables still have distinct source IDs.
    if label in {"ls", "lr", "ld"} and scope is not None:
        label = f"{label}-{scope}"
    return dict(role=role, relative_day=day, coordinate_id=coordinate, date_ref=date,
                role_ref=label, scope_ref=scope, binding_status=status)


def unknown(status="unknown"):
    return assertion("sampling", status=status)


def obs(number, item, value, assertions):
    return dict(observation_id=f"expected-{number}", case_token=CASE, item=item,
                value=value, unit="U", source_refs=[f"r{number}"], time_assertions=assertions)


# Independently specified expected records: original rows, including the copy,
# remain in this layer. Identity decisions are scored separately below.
EXPECTED = [
    obs(1, "X", "4.2", [assertion("sampling", 0, "C1", "d1s", "ls", "t1"), assertion("report", 1, "C1", "d1r", "lr", "t1")]),
    obs(2, "Y", "7", [assertion("sampling", 0, "C1", "d1s", "ls", "t1"), assertion("report", 1, "C1", "d1r", "lr", "t1")]),
    obs(3, "X", "4.2", [assertion("sampling", 3, "C1", "d2s", "ls", "t2"), assertion("report", 4, "C1", "d2r", "lr", "t2")]),
    obs(4, "X", "4.2", [assertion("sampling", 0, "C1", "d3s", "ls", "t3"), assertion("report", 1, "C1", "d3r", "lr", "t3")]),
    obs(5, "X", "5.1", [unknown(), assertion("report", 2, "C1", "d4r", "lr", "t4")]),
    obs(6, "X", "6", [unknown(), assertion("document", 2, "C1", "d5", "ld", "t5")]),
    obs(7, "X", "8", [assertion("sampling", 0, "C2", "d6", "ls", "t6")]),
    obs(8, "X", "9", [assertion("sampling", 2, "C1", "d7", "ls", "t7")]),
    obs(9, "X", "1", [assertion("sampling", 0, "C1", "d8a", "ls", "t8", "conflicting"), assertion("sampling", 1, "C1", "d8b", "ls", "t8", "conflicting")]),
    obs(10, "X", "2", [unknown("unresolved"), assertion("unknown", 0, "C1", "d9", None, None, "unresolved")]),
    obs(11, "X", "4.2", [assertion("sampling", 0, "C1", "d10", "ls", "t10")]),
    obs(12, "X", "3", [unknown("unresolved")]),
]

# The evidence registry is an authored source inventory, not inferred from gold.
ROW_LOCATIONS = [
    ("r1", "D1", 1, "T1"), ("r2", "D1", 1, "T1"), ("r3", "D2", 1, "T2"),
    ("r4", "D3", 1, "T3"), ("r5", "D4", 1, "T4"), ("r6", "D5", 1, "T5"),
    ("r7", "D6", 1, "T6"), ("r8", "D1", 1, "T7"), ("r9", "D8", 1, "T8"),
    ("r10", "D9", 1, "T9"), ("r11", "D10", 1, "T10"), ("r12", "D11", 2, "T12"),
]


def gold_fixture():
    evidence = [dict(evidence_id=r, kind="row", case_token=CASE,
                     document_token=d, page_number=p, table_id=t, source_version="synthetic-v1")
                for r, d, p, t in ROW_LOCATIONS]
    for kind, identifiers in (
        ("date", "d1s d1r d2s d2r d3s d3r d4r d5 d6 d7 d8a d8b d9 d10 d11"),
        ("role", "ls-t1 lr-t1 ls-t2 lr-t2 ls-t3 lr-t3 lr-t4 ld-t5 ls-t6 ls-t7 ls-t8 ls-t10 ls-t11"),
        ("scope", "t1 t2 t3 t4 t5 t6 t7 t8 t9 t10 t11"),
    ):
        evidence.extend(dict(evidence_id=r, kind=kind, case_token=CASE,
                             source_version="synthetic-v1") for r in identifiers.split())
    return dict(protocol=PROTOCOL, split="synthetic_development", evidence=evidence,
                observations=deepcopy(EXPECTED), identity_pairs=[
                    {"rows": ["r1", "r4"], "relation": "same"},
                    {"rows": ["r1", "r3"], "relation": "different"},
                    {"rows": ["r1", "r11"], "relation": "different"},
                    {"rows": ["r1", "r7"], "relation": "unresolved"},
                ])


def correct_prediction():
    # An oracle-shaped development submission used to test the scorer itself.
    # It is not a B output or an experiment result.
    return dict(protocol=PROTOCOL, observations=deepcopy(EXPECTED),
                event_groups=[["r1", "r4"], ["r3"], ["r11"]])
