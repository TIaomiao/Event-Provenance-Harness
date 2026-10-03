"""Synthetic alias-routing and task-stability matrix.

The runner sends only synthetic evidence.  It records alias, returned model,
status, usage and body hashes.  Provider identity remains unknown unless the
gateway returns an explicit field.  The module does not read patient files.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import ssl
import time
import urllib.error
import urllib.request
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from outbound_guard import GuardConfig, build_request_body, inspect_request, request_body_bytes


ALIASES = [
    "[j]gemini-3-flash",
    "[j]gemini-3.1-flash-lite",
    "[j]gpt-5.6-sol",
]
REPEATS = 3
MAX_TOKENS = 128
TRANSIENT = {429, 500, 502, 503, 504}


SCENARIOS = [
    {
        "id": "C1",
        "task": "C",
        "evidence": "Project HGB; result 119; source anchor DOC-SYN:L3; collection role DOC-SYN:L5; report role DOC-SYN:L6; candidate unit is null as a processing state. The source observation is present and the time roles are explicit.",
        "question": "Return JSON {decision: supported|contradicted|insufficient|invalid_task}. Null unit is not a contradiction unless a unit declaration or conversion is required.",
        "expected": {"decision": "supported"},
    },
    {
        "id": "C2",
        "task": "C",
        "evidence": "Project HGB; source anchor DOC-SYN:L3; source result 119; candidate result 118; collection role DOC-SYN:L5; report role DOC-SYN:L6; unit g/L is explicitly present.",
        "question": "Return JSON {decision: supported|contradicted|insufficient|invalid_task}.",
        "expected": {"decision": "contradicted"},
    },
    {
        "id": "C3",
        "task": "C",
        "evidence": "Project HGB; source anchor DOC-SYN:L3; result 119 g/L; only report role DOC-SYN:L6 is present; collection role is absent. Do not substitute report time for collection time.",
        "question": "Return JSON {decision: supported|contradicted|insufficient|invalid_task}.",
        "expected": {"decision": "insufficient"},
    },
    {
        "id": "C4",
        "task": "C",
        "evidence": "Candidate record_id opaque-123; value 119; no project name and no source anchor; collection and report roles are otherwise present.",
        "question": "Return JSON {decision: supported|contradicted|insufficient|invalid_task}. Missing identity is an invalid task.",
        "expected": {"decision": "invalid_task"},
    },
    {
        "id": "B1",
        "task": "B",
        "evidence": "Frozen laboratory report contains record A: project HGB, value 110 g/L, collection 2024-01-02 08:00:00, report 2024-01-02 09:00:00; record B: project HGB, value 120 g/L, collection 2024-01-01 08:00:00, report 2024-01-03 09:00:00. Use collection time only.",
        "question": "Return JSON {status: ok|undetermined, record_ids: [...]}.",
        "expected": {"status": "ok", "record_ids": ["A"]},
    },
    {
        "id": "B2",
        "task": "B",
        "evidence": "Frozen laboratory report contains record A: project HGB, value 110 g/L, collection date 2024-01-02 with no time; record B: project HGB, value 120 g/L, collection date 2024-01-02 with no time. Do not use report time to break the tie.",
        "question": "Return JSON {status: ok|undetermined, record_ids: [...]} and keep all tied records.",
        "expected": {"status": "undetermined", "record_ids": ["A", "B"]},
    },
]


def prompt_for(scenario: dict[str, Any]) -> str:
    return (
        "You are a synthetic downstream evidence consumer. Use only the synthetic evidence below. "
        "Do not invent missing facts. Return JSON only.\n\n"
        f"SCENARIO={scenario['id']}\nTASK={scenario['task']}\n"
        f"EVIDENCE:\n{scenario['evidence']}\n\n"
        f"INSTRUCTION:\n{scenario['question']}\n"
    )


def _hash(value: str | bytes) -> str:
    raw = value if isinstance(value, bytes) else value.encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def _parse_json(text: str) -> dict[str, Any] | None:
    match = re.search(r"\{[\s\S]*\}", text or "")
    if not match:
        return None
    try:
        obj = json.loads(match.group(0))
    except json.JSONDecodeError:
        return None
    return obj if isinstance(obj, dict) else None


def _normal_answer(task: str, obj: dict[str, Any] | None) -> dict[str, Any] | None:
    if not obj:
        return None
    if task == "C":
        value = obj.get("decision") or obj.get("verdict") or obj.get("evaluation") or obj.get("conclusion")
        return {"decision": str(value).strip().lower()} if value is not None else None
    ids = obj.get("record_ids")
    if not isinstance(ids, list):
        ids = []
    return {"status": str(obj.get("status") or "").strip().lower(), "record_ids": [str(x) for x in ids]}


def _matches(expected: dict[str, Any], actual: dict[str, Any] | None) -> bool:
    if actual is None:
        return False
    if expected.keys() != actual.keys():
        return False
    return expected == actual


def _post(url: str, key: str, body: bytes, timeout: int = 120) -> dict[str, Any]:
    req = urllib.request.Request(
        url,
        data=body,
        method="POST",
        headers={"Authorization": "Bearer " + key, "Content-Type": "application/json"},
    )
    started = time.time()
    try:
        with urllib.request.urlopen(req, timeout=timeout, context=ssl.create_default_context()) as response:
            raw = response.read().decode("utf-8", "replace")
            server_id = response.headers.get("x-request-id") or response.headers.get("request-id")
            return {"http": response.status, "elapsed": round(time.time() - started, 3), "raw": raw, "server_request_id": server_id}
    except urllib.error.HTTPError as error:
        raw = error.read().decode("utf-8", "replace")
        server_id = error.headers.get("x-request-id") or error.headers.get("request-id")
        return {"http": error.code, "elapsed": round(time.time() - started, 3), "raw": raw, "server_request_id": server_id}
    except Exception as error:  # pragma: no cover - network dependent
        return {"http": 0, "elapsed": round(time.time() - started, 3), "raw": "", "server_request_id": None, "error_type": type(error).__name__}


def run_matrix(*, base_url: str, key: str, out: Path, aliases: list[str] | None = None, repeats: int = REPEATS) -> dict[str, Any]:
    aliases = aliases or ALIASES
    out.parent.mkdir(parents=True, exist_ok=True)
    endpoint = base_url.rstrip("/") + "/v1/chat/completions"
    guard_config = GuardConfig(
        code_version="model_matrix.py:v0.1",
        config_version="synthetic-matrix-v0.1",
        approved_destinations=frozenset({"synthetic-pool-probe"}),
        allow_external=True,
    )
    rows: list[dict[str, Any]] = []
    for repeat in range(1, repeats + 1):
        for scenario in SCENARIOS:
            for alias in aliases:
                logical_id = f"matrix-v0.1/{scenario['id']}/{alias}/r{repeat}"
                messages = [
                    {"role": "system", "content": "Return JSON only."},
                    {"role": "user", "content": prompt_for(scenario)},
                ]
                source = {
                    "source_version": "synthetic-evidence-v0.1",
                    "source_sha256": _hash(scenario["evidence"]),
                    "hash_matches": True,
                    "api_ready": True,
                    "raw_ocr": False,
                    "payload_mode": "synthetic",
                    "sensitivity": "SYNTHETIC_ONLY",
                    "review_scope": scenario["id"],
                    "purpose": "model-family-synthetic-probe",
                    "destination": "synthetic-pool-probe",
                    "unknown_state": False,
                }
                task_fields = {
                    "project_name": "synthetic HGB",
                    "value": "synthetic",
                    "unit": "synthetic",
                    "collection_time_role": "synthetic",
                    "report_time_role": "synthetic",
                    "source_anchor": "synthetic",
                }
                guard = inspect_request(
                    messages=messages,
                    model=alias,
                    max_tokens=MAX_TOKENS,
                    source=source,
                    task_fields=task_fields,
                    destination="synthetic-pool-probe",
                    purpose="model-family-synthetic-probe",
                    config=guard_config,
                )
                body = request_body_bytes(messages, alias, MAX_TOKENS)
                if guard.body_sha256 != _hash(body):
                    raise RuntimeError("BODY_HASH_MISMATCH_BEFORE_SEND")
                attempts: list[dict[str, Any]] = []
                for attempt_number in range(1, 3):
                    response = _post(endpoint, key, body)
                    raw = response.get("raw", "")
                    parsed = None
                    returned_model = None
                    usage: dict[str, Any] = {}
                    response_id_hash = None
                    try:
                        envelope = json.loads(raw) if raw else {}
                        parsed = _parse_json((envelope.get("choices") or [{}])[0].get("message", {}).get("content", ""))
                        returned_model = envelope.get("model")
                        usage = envelope.get("usage") or {}
                        response_id = envelope.get("id")
                        response_id_hash = _hash(str(envelope.get("id") or ""))[:12] if envelope.get("id") else None
                    except (TypeError, json.JSONDecodeError):
                        response_id = None
                    attempts.append({
                        "attempt_id": f"{logical_id}/a{attempt_number}",
                        "http": response.get("http"),
                        "elapsed": response.get("elapsed"),
                        "returned_model": returned_model,
                        "provider": None,
                        "provider_unknown": True,
                        "response_id_hash": response_id_hash,
                        "response_id": response_id,
                        "server_request_id": response.get("server_request_id"),
                        "usage": usage,
                        "finish_reason": ((json.loads(raw).get("choices") or [{}])[0].get("finish_reason") if raw and raw.startswith("{") else None),
                        "response_body_hash": _hash(raw),
                        "error_type": response.get("error_type"),
                    })
                    if response.get("http") not in TRANSIENT:
                        break
                final = attempts[-1]
                final_obj = parsed if attempts[-1].get("response_body_hash") == _hash(raw) else None
                actual = _normal_answer(scenario["task"], final_obj)
                format_ok = actual is not None
                correct = _matches(scenario["expected"], actual)
                rows.append({
                    "run_id": "model_matrix_v0.1",
                    "logical_request_id": logical_id,
                    "scenario": scenario["id"],
                    "task": scenario["task"],
                    "repeat": repeat,
                    "requested_alias": alias,
                    "actual_sent_model": alias,
                    "provider": None,
                    "provider_unknown": True,
                    "payload_mode": "synthetic",
                    "guard_decision": guard.decision,
                    "body_sha256": guard.body_sha256,
                    "expected": scenario["expected"],
                    "actual": actual,
                    "format_ok": format_ok,
                    "correct": correct,
                    "failure_class": None if correct else ("format_failure" if not format_ok else "content_error"),
                    "attempts": attempts,
                })
    out.write_text("\n".join(json.dumps(row, ensure_ascii=False, sort_keys=True) for row in rows) + "\n", encoding="utf-8")
    summary = summarize(rows, aliases)
    (out.with_suffix(".summary.json")).write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    return summary


def summarize(rows: list[dict[str, Any]], aliases: list[str]) -> dict[str, Any]:
    by_alias: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        by_alias[row["requested_alias"]].append(row)
    return {
        "run_id": "model_matrix_v0.1",
        "planned_logical_requests": len(SCENARIOS) * len(aliases) * REPEATS,
        "logical_requests": len(rows),
        "attempts": sum(len(r["attempts"]) for r in rows),
        "http_200_final": sum(r["attempts"][-1]["http"] == 200 for r in rows),
        "format_ok": sum(r["format_ok"] for r in rows),
        "correct": sum(r["correct"] for r in rows),
        "provider_unknown": True,
        "cost": {"status": "unknown", "currency": "unknown", "reason": "provider billing and price version not returned by probe"},
        "by_alias": {
            alias: {
                "logical_requests": len(items),
                "final_http": Counter(str(r["attempts"][-1]["http"]) for r in items),
                "format_ok": sum(r["format_ok"] for r in items),
                "correct": sum(r["correct"] for r in items),
                "returned_models": Counter(str(r["attempts"][-1].get("returned_model")) for r in items),
                "content_failures": sum(r["failure_class"] == "content_error" for r in items),
                "format_failures": sum(r["failure_class"] == "format_failure" for r in items),
            }
            for alias, items in by_alias.items()
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default=os.environ.get("LLM_BASE_URL", ""))
    parser.add_argument("--key", default=os.environ.get("LLM_API_KEY", ""))
    parser.add_argument("--out", required=True)
    parser.add_argument("--repeats", type=int, default=REPEATS)
    args = parser.parse_args()
    if not args.base_url or not args.key:
        raise SystemExit("MATRIX_CONFIG_MISSING")
    summary = run_matrix(base_url=args.base_url, key=args.key, out=Path(args.out), repeats=args.repeats)
    print(json.dumps(summary, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
