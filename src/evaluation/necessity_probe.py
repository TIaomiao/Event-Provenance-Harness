"""baseline v1: run the A/B comparison over a frozen bundle, resumable and cost-aware.

One entry point with two subcommands:

    run      make the calls for every task and arm, skipping anything already done,
             refusing to spend past the budget, and never overwriting a response
    rescore  rebuild the same summary from the saved responses, with no network

The module is data-source agnostic: it reads a bundle produced under control and
therefore holds no patient material itself.  The bundle carries, per task, the two arms'
contexts, the reference and the task contract, plus the scorer fingerprint the bundle was
frozen against.  The fingerprint is checked before any request is made, so a bundle built
for a different scorer is refused instead of silently scored with the wrong one.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import time
from pathlib import Path

from task_selection import SelectionError, check_contract, score

VERSION = "necessity_probe v1"
ARMS = ("A_raw_tools", "B_extracted_sql")
REQUIRED_BUNDLE_KEYS = ("task_id", "contract", "reference", "context")
INSTRUCTION = ("请只输出 JSON：{\"status\": \"ok\" | \"empty\" | \"undetermined\", "
               "\"selected\": [{\"record_id\": null, \"project_name\": \"<项目>\", "
               "\"value\": <数字>, \"unit\": \"<单位>\", "
               "\"collection_day_offset\": <整数>, \"report_day_offset\": <整数或 null>, "
               "\"source_refs\": [\"<行号>\"]}], \"reason\": \"<可选>\"}")


class ProbeError(RuntimeError):
    """A configuration or provenance failure that must stop the run."""


def scorer_fingerprint():
    """Fingerprint the scorer that is actually imported, not a same-named file."""
    import task_selection as loaded
    path = Path(loaded.__file__).resolve()
    return {"path": str(path),
            "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}


def check_bundle(bundle, fp):
    """Refuse a bundle frozen against a different scorer, before any request."""
    declared = bundle.get("scorer_sha256")
    if not declared:
        raise ProbeError("BUNDLE_MISSING_SCORER_FINGERPRINT")
    if declared != fp["sha256"]:
        raise ProbeError("SCORER_MISMATCH bundle=%s loaded=%s" % (declared, fp["sha256"]))
    version = bundle.get("probe_version")
    if version and version != VERSION:
        raise ProbeError("PROBE_VERSION_MISMATCH bundle=%s loaded=%s" % (version, VERSION))
    for task in bundle.get("tasks", []):
        missing = [key for key in REQUIRED_BUNDLE_KEYS if key not in task]
        if missing:
            raise ProbeError("TASK_MISSING_%s" % "_".join(missing).upper())
        check_contract({"contract": task["contract"]})  # loud on a partial contract


def load_bundle(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def estimate_cost(tokens_in, tokens_out, price_per_million):
    rate_in, rate_out = price_per_million
    return tokens_in * rate_in / 1e6 + tokens_out * rate_out / 1e6


def average_context_tokens(bundle, chars_per_token=1.6):
    """A rough planning figure, used only by the dry run."""
    total = sum(len(t["context"].get(arm, "")) for t in bundle["tasks"] for arm in ARMS)
    return int(total / max(1, len(bundle["tasks"]) * len(ARMS)) / chars_per_token)


def plan(bundle, price_per_million, planned_output_tokens=900, chars_per_token=1.6):
    jobs = []
    for task in bundle["tasks"]:
        for arm in ARMS:
            text = task["context"].get(arm, "")
            tokens_in = int(len(text) / chars_per_token)
            jobs.append({"task_id": task["task_id"], "arm": arm,
                         "tokens_in_estimate": tokens_in,
                         "cost_estimate": round(estimate_cost(
                             tokens_in, planned_output_tokens, price_per_million), 6)})
    return jobs


def response_path(responses, task_id, arm):
    return Path(responses) / ("%s__%s.json" % (task_id, arm))


def load_ledger(ledger):
    rows = []
    path = Path(ledger)
    if path.is_file():
        for line in path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                rows.append(json.loads(line))
    return rows


def done_keys(rows):
    return {(row["task_id"], row["arm"]) for row in rows if row.get("status") == "ok"}


def append_ledger(ledger, row):
    path = Path(ledger)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(row, ensure_ascii=False) + "\n")


def run(bundle_path, responses, ledger, transport, *, model, price_per_million,
        max_usd=2.0, dry_run=False, limit=None, attempts=1):
    """Run both arms over the bundle.  Resumable, budgeted, never overwrites."""
    bundle = load_bundle(bundle_path)
    fp = scorer_fingerprint()
    check_bundle(bundle, fp)
    rows = load_ledger(ledger)
    done = done_keys(rows)
    spent = sum(row.get("cost_usd") or 0 for row in rows)
    jobs = [j for j in plan(bundle, price_per_million)
            if (j["task_id"], j["arm"]) not in done]
    if limit is not None:
        jobs = jobs[:limit]
    planned = round(sum(j["cost_estimate"] for j in jobs), 6)
    report = {"scorer": fp, "model": model, "already_done": len(done),
              "planned_calls": len(jobs), "planned_cost": planned,
              "spent_before": round(spent, 6), "max_usd": max_usd, "runs": []}
    if dry_run:
        report["dry_run"] = True
        return report
    for job in jobs:
        if spent + job["cost_estimate"] > max_usd:
            report["stopped"] = "BUDGET"
            break
        task = next(t for t in bundle["tasks"] if t["task_id"] == job["task_id"])
        messages = [{"role": "system", "content": "你是严谨的临床数据取数助手，只依据材料作答。"},
                    {"role": "user", "content": "%s\n\n任务：%s\n\n%s" % (
                        task["context"][job["arm"]], task["instruction"], INSTRUCTION)}]
        target = response_path(responses, job["task_id"], job["arm"])
        started = time.time()
        last = None
        for attempt in range(1, attempts + 1):
            try:
                last = transport(model=model, messages=messages)
                break
            except Exception as error:  # a transport failure is a status, not a crash
                last = {"status": "transport_error", "error": str(error)[:200],
                        "tokens_in": 0, "tokens_out": 0, "raw": ""}
        tokens_in = last.get("tokens_in") or 0
        tokens_out = last.get("tokens_out") or 0
        cost = estimate_cost(tokens_in, tokens_out, price_per_million)
        if not target.exists():
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(json.dumps(
                {"messages": messages, "raw": last.get("raw", ""),
                 "model_returned": last.get("model_returned"),
                 "tokens_in": tokens_in, "tokens_out": tokens_out},
                ensure_ascii=False), encoding="utf-8")
            os.chmod(target, 0o600)
        row = {"task_id": job["task_id"], "arm": job["arm"], "model_requested": model,
               "model_returned": last.get("model_returned"),
               "status": last.get("status", "ok"), "attempts": attempt,
               "tokens_in": tokens_in, "tokens_out": tokens_out,
               "cost_usd": round(cost, 7), "latency_s": round(time.time() - started, 2),
               "response_file": str(target)}
        append_ledger(ledger, row)
        rows.append(row)
        spent += cost
        report["runs"].append(row)
    report["spent_after"] = round(spent, 6)
    return report


def rescore(bundle_path, responses, out, *, tasks_without_response_count_as_failure=True):
    """Rebuild the summary from saved responses.  No network, no cost."""
    bundle = load_bundle(bundle_path)
    fp = scorer_fingerprint()
    check_bundle(bundle, fp)
    items = []
    for task in bundle["tasks"]:
        for arm in ARMS:
            path = response_path(responses, task["task_id"], arm)
            if not path.is_file():
                if tasks_without_response_count_as_failure:
                    items.append({"task_id": task["task_id"], "arm": arm,
                                  "status": "missing_response", "task_success": False})
                continue
            saved = json.loads(path.read_text(encoding="utf-8"))
            answer = _parse_answer(saved.get("raw", ""))
            scored = score({"task_id": task["task_id"], "time_role": task["contract"]["time_role"],
                            "spec": {"window": task["contract"]["window"],
                                     "selection": task["contract"]["selection"],
                                     "contract": task["contract"]}},
                           answer, task["records"], task["reference"])
            items.append({"task_id": task["task_id"], "arm": arm,
                          "status": saved.get("status", "ok"),
                          "set_exact_match": scored["set_exact_match"],
                          "status_ok": scored["status_ok"],
                          "fields_match": scored["fields_match"],
                          "task_success": scored["task_success"],
                          "field_mismatches": scored["field_mismatches"]})
    summary = {"probe_version": VERSION, "scorer": fp,
               "tasks": len(bundle["tasks"]), "items": len(items),
               "by_arm": {}, "failures": [i for i in items if not i.get("task_success")],
               "missing_responses": [i for i in items if i.get("status") == "missing_response"]}
    for arm in ARMS:
        group = [i for i in items if i["arm"] == arm]
        summary["by_arm"][arm] = {
            "n": len(group),
            "task_success": sum(1 for i in group if i.get("task_success")),
            "set_exact": sum(1 for i in group if i.get("set_exact_match")),
            "fields_match": sum(1 for i in group if i.get("fields_match") is True),
        }
    if out:
        Path(out).write_text(json.dumps(summary, ensure_ascii=False, indent=2),
                             encoding="utf-8")
    return summary


def _parse_answer(raw):
    """Parse a saved response body without raising on malformed content."""
    text = raw or ""
    start, end = text.find("{"), text.rfind("}")
    if start < 0 or end <= start:
        return {"status": None, "selected_records": None}
    try:
        payload = json.loads(text[start:end + 1])
    except (ValueError, TypeError):
        return {"status": None, "selected_records": None}
    if not isinstance(payload, dict):
        return {"status": None, "selected_records": None}
    items = payload.get("selected")
    selected = []
    if isinstance(items, list):
        for item in items:
            # keep the whole item, not only its id: the field checks need the claims
            if isinstance(item, dict):
                selected.append(item)
            elif isinstance(item, str):
                selected.append(item)
    return {"status": payload.get("status"), "selected_records": selected,
            "raw_answer": payload}


def main(argv=None):
    parser = argparse.ArgumentParser(description="baseline v1 A/B probe")
    sub = parser.add_subparsers(dest="command", required=True)
    for name in ("run", "rescore"):
        node = sub.add_parser(name)
        node.add_argument("--bundle", required=True)
        node.add_argument("--responses", required=True)
    sub.choices["run"].add_argument("--ledger", required=True)
    sub.choices["run"].add_argument("--model", required=True)
    sub.choices["run"].add_argument("--price", required=True,
                                    help="in,out per million tokens, e.g. 0.3,1.5")
    sub.choices["run"].add_argument("--max-usd", type=float, default=2.0)
    sub.choices["run"].add_argument("--dry-run", action="store_true")
    sub.choices["run"].add_argument("--limit", type=int)
    sub.choices["rescore"].add_argument("--out")
    args = parser.parse_args(argv)
    if args.command == "run":
        rate = tuple(float(x) for x in args.price.split(","))
        transport = None
        if not args.dry_run:
            # the transport needs credentials, so a dry run must not import it
            from necessity_transport import openai_transport
            transport = openai_transport()
        report = run(args.bundle, args.responses, args.ledger, transport,
                     model=args.model, price_per_million=rate,
                     max_usd=args.max_usd, dry_run=args.dry_run, limit=args.limit)
    else:
        report = rescore(args.bundle, args.responses, args.out)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
