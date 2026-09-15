"""Conservative binding of recovered dates to laboratory rows.

Only explicit role labels and links supplied upstream are accepted. Source scope
is checked; this module never infers clinical roles or associations from geometry.
"""
from __future__ import annotations

from copy import deepcopy

ROLES = {"sampling", "report", "record", "document", "unknown"}
VERSION = "temporal-row-binding-draft-v0.1"
ROLE_LABELS = {"采样时间": "sampling", "报告时间": "report", "记录时间": "record", "文档时间": "document"}


def _scope(item):
    for field in ("case_token", "document_token"):
        if not isinstance(item.get(field), str) or not item[field]:
            raise ValueError("MISSING_SOURCE_SCOPE")
    if type(item.get("page_number")) is not int or item["page_number"] < 1:
        raise ValueError("INVALID_PAGE_NUMBER")
    return tuple(item[k] for k in ("case_token", "document_token", "page_number"))


def bind_candidates(candidates, rows):
    """Return candidates annotated with row ids and explicit temporal roles.

    Both inputs carry case_token, document_token and page_number. Rows additionally
    contain row_id, candidate_ordinals (indices into this candidate list), and an
    optional temporal_role. Ambiguous links are rejected; missing links or roles
    remain unresolved. Input roles are assertions, not independently verified facts.
    A header spanning several rows needs a future scope-aware interface.
    """
    out = deepcopy(candidates)
    scopes = [_scope(item) for item in out]
    by_ord = {}
    seen_rows = set()
    for row in rows:
        scope = _scope(row)
        role = row.get("temporal_role", "unknown")
        if role not in ROLES:
            raise ValueError("INVALID_TEMPORAL_ROLE")
        rid = row.get("row_id")
        if not isinstance(rid, str) or not rid:
            raise ValueError("INVALID_ROW_ID")
        if (scope, rid) in seen_rows:
            raise ValueError("DUPLICATE_ROW_ID")
        seen_rows.add((scope, rid))
        ordinals = row.get("candidate_ordinals", [])
        if not isinstance(ordinals, list):
            raise ValueError("INVALID_CANDIDATE_ORDINALS")
        for ordinal in ordinals:
            if type(ordinal) is not int or not 0 <= ordinal < len(out):
                raise ValueError("INVALID_CANDIDATE_ORDINAL")
            if ordinal in by_ord:
                raise ValueError("AMBIGUOUS_ROW_BINDING")
            if scopes[ordinal] != scope:
                raise ValueError("SOURCE_SCOPE_MISMATCH")
            by_ord[ordinal] = (rid, role)
    for i, item in enumerate(out):
        link = by_ord.get(i)
        item["lab_row_id"] = link[0] if link else None
        item["temporal_role"] = link[1] if link else "unknown"
        item["binding_status"] = "explicit" if link and link[1] != "unknown" else "unresolved"
        item["api_ready"] = False
        item["clinical_time_roles_validated"] = False
    return out


def materialize_event_table(headers, rows, *, evidence_prefix="EVIDENCE"):
    """Materialize one event per lab row, allowing a header date to span rows.

    Header: ``date``, ``text``, ``role_label``, ``evidence_id``, ``bbox``.
    Row: ``row_id``, ``value``, ``unit``, ``bbox``, optional ``role_label`` and
    ``evidence_id``. Layout links a header to rows below it on the same page when
    no explicit role label exists; ties remain unresolved.
    """
    events = []
    for row in rows:
        role = ROLE_LABELS.get(row.get("role_label", ""), "unknown")
        matches = [h for h in headers if h.get("page_number") == row.get("page_number")
                   and h.get("date") is not None and h.get("bbox")
                   and h.get("bbox")[0][1] <= row.get("bbox", [[0, 0]])[0][1]]
        # The nearest preceding header defines a layout scope; ties at the same
        # vertical position remain ambiguous.
        nearest = max((h.get("bbox")[0][1] for h in matches), default=None)
        scoped = [h for h in matches if h.get("bbox")[0][1] == nearest] if nearest is not None else []
        if role == "unknown" and len(scoped) == 1:
            role = ROLE_LABELS.get(scoped[0].get("role_label", ""), "unknown")
        header = scoped[0] if len(scoped) == 1 else None
        events.append({"event_type": "laboratory", "lab_row_id": row.get("row_id"),
                       "value": row.get("value"), "unit": row.get("unit"),
                       "event_time": header.get("date") if header and role != "unknown" else None,
                       "temporal_role": role, "binding_status": "explicit" if header and role != "unknown" else "unresolved",
                       "evidence": [row.get("evidence_id") or f"{evidence_prefix}:row:{row.get('row_id')}"] + ([header.get("evidence_id")] if header else [])})
    return events
