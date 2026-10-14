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

from task_selection import (SelectionError, _finite, _norm_unit, check_contract,
                            score)

VERSION = "necessity_probe v1"
ARMS = ("A_raw_tools", "B_extracted_sql")
PLANNED_OUTPUT_TOKENS = 900
REQUIRED_BUNDLE_KEYS = ("task_id", "contract", "reference", "context")
INSTRUCTION = ("请只输出 JSON：{\"status\": \"ok\" | \"empty\" | \"undetermined\", "
               "\"selected\": [{\"record_id\": null, \"project_name\": \"<项目>\", "
               "\"value\": <数字>, \"unit\": \"<单位>\", "
               "\"collection_day_offset\": <整数>, \"report_day_offset\": <整数或 null>, "
               "\"source_refs\": [\"<行号>\"]}], \"reason\": \"<可选>\"}")


PAGE_MARK = "=== PAGE "


def split_pages(context):
    """Parse a page-indexed context into [(page_label, [lines])]."""
    pages, current = [], None
    for line in (context or "").splitlines():
        if line.startswith(PAGE_MARK):
            current = (line[len(PAGE_MARK):].rstrip(" ="), [])
            pages.append(current)
            continue
        if current is None:
            current = ("?", [])
            pages.append(current)
        current[1].append(line)
    return pages


def join_pages(pages):
    out = []
    for label, lines in pages:
        out.append("%s%s ===" % (PAGE_MARK, label))
        out.extend(lines)
    return "\n".join(out)


def _question_terms(question):
    return {part for part in str(question).lower().split() if part} or set(question or "")


def retrieve_pages(context, question, *, max_pages=None, include_adjacent=True,
                   min_hits=1, allow_more=True, hard_page_cap=64):
    """Find where the question lands, then return the whole page there.

    Location uses only the page index, the line text and the question.  The reference and
    the extracted table take no part in deciding what to expand.  Whole pages are returned
    rather than a few neighbouring lines, because a record's value, its unit and the page
    header times sit in different rows.
    """
    pages = split_pages(context)
    if not pages:
        return context or "", {"pages": 0, "expanded": [], "hits": 0}
    terms = _question_terms(question)
    scored = []
    for index, (label, lines) in enumerate(pages):
        hits = sum(1 for line in lines if any(term in line.lower() for term in terms))
        scored.append((hits, index, label))
    hits_total = sum(item[0] for item in scored)
    ranked = sorted([item for item in scored if item[0] >= min_hits],
                    key=lambda item: (-item[0], item[1]))
    if max_pages is None:
        # no cap: every page the question lands on is read, so the answer is never cut off
        chosen = [item[1] for item in ranked]
    else:
        chosen = [item[1] for item in ranked[:max_pages]]
    if include_adjacent:
        for index in list(chosen):
            for neighbour in (index - 1, index + 1):
                if 0 <= neighbour < len(pages) and neighbour not in chosen:
                    chosen.append(neighbour)
    chosen = sorted(set(chosen)) or list(range(min(1, len(pages))))
    remaining = len(pages) - len(chosen)
    if max_pages is not None:
        chosen = chosen[:max_pages + (2 if include_adjacent else 0)]
    else:
        chosen = chosen[:hard_page_cap]
    expanded = [pages[index][0] for index in chosen]
    return join_pages([pages[index] for index in chosen]), {
        "pages": len(pages), "expanded": expanded, "hits": hits_total,
        "truncated": bool(max_pages is not None and remaining > 0),
        "can_read_more": allow_more and (len(chosen) < len(pages))}


def retrieve_lines(context, question, top_k=40, window=1):
    """Deprecated line-level retrieval, kept only as a diagnostic contrast."""
    lines = [line for line in (context or "").splitlines() if line.strip()]
    terms = {ch for ch in question if ch.isalnum()}
    if not lines or not terms:
        return context or "", len(lines)
    scored = sorted(((sum(1 for ch in set(line) if ch in terms), index)
                     for index, line in enumerate(lines)), key=lambda item: (-item[0], item[1]))
    keep = set()
    for hits, index in scored[:top_k]:
        if hits == 0:
            break
        for offset in range(-window, window + 1):
            if 0 <= index + offset < len(lines):
                keep.add(index + offset)
    if not keep:
        return context or "", len(lines)
    return "\n".join(lines[i] for i in sorted(keep)), len(keep)


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


def plan(bundle, price_per_million, planned_output_tokens=PLANNED_OUTPUT_TOKENS, chars_per_token=1.6):
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
        max_usd=2.0, dry_run=False, limit=None, attempts=1, params=None, tools=None,
        run_dir=None, price_snapshot=None):
    """Run both arms over the bundle: identified, resumable, budgeted, durable.

    The run directory carries an identity manifest.  A resume whose identity differs is
    refused before any request, because task id and arm alone do not say which model,
    prompt, tools, code or scorer produced the saved answers.
    """
    bundle = load_bundle(bundle_path)
    fp = scorer_fingerprint()
    check_bundle(bundle, fp)
    run_dir = Path(run_dir) if run_dir else Path(responses).parent
    identity = run_identity(bundle_path, bundle, model=model,
                            params=dict(params or {"max_output_tokens":
                                                   PLANNED_OUTPUT_TOKENS}),
                            tools=dict(tools or {}))
    identity_state = require_identity(run_dir, identity)

    plan_jobs = plan(bundle, price_per_million)
    recovered, rows = recover_ledger(ledger, responses, plan_jobs)
    # Anything with a usable saved response counts as done, and an attempted-but-unsaved
    # request is not retried automatically: it may already have been paid for.
    done = {(row["task_id"], row["arm"]) for row in rows
            if row.get("status") in ("ok", "recovered_from_response", "result_unknown")
            or (row.get("response_file") and Path(row["response_file"]).is_file())}
    known_spend = sum(row["cost_usd"] for row in rows
                      if isinstance(row.get("cost_usd"), (int, float)))
    unknown_rows = [r for r in rows if r.get("cost_usd") is None]
    jobs = [j for j in plan_jobs if (j["task_id"], j["arm"]) not in done]
    if limit is not None:
        jobs = jobs[:limit]
    report = {"scorer": fp, "identity": identity, "identity_digest":
              identity_digest(identity), "identity_state": identity_state,
              "model": model, "already_done": len(done), "recovered_from_response":
              recovered, "planned_calls": len(jobs),
              "planned_cost": round(sum(j["cost_estimate"] for j in jobs), 6),
              "known_spend_before": round(known_spend, 6),
              "unknown_cost_rows": len(unknown_rows), "max_usd": max_usd,
              "price_snapshot": price_snapshot, "runs": []}
    if dry_run:
        report["dry_run"] = True
        return report
    spent = known_spend
    for job in jobs:
        if spent + job["cost_estimate"] > max_usd:
            report["stopped"] = "BUDGET"
            break
        task = next(t for t in bundle["tasks"] if t["task_id"] == job["task_id"])
        context = task["context"][job["arm"]]
        retrieved = None
        if job["arm"].startswith("A") and bundle.get("a_retrieval_tool"):
            context, retrieved = retrieve_pages(context, task["instruction"] + " " + str(
                (task.get("contract") or {}).get("project", "")))
        messages = [{"role": "system", "content": "你是严谨的临床数据取数助手，只依据材料作答。"},
                    {"role": "user", "content": "%s\n\n任务：%s\n\n%s" % (
                        context, task["instruction"], INSTRUCTION)}]
        cap = (params or {}).get("max_output_tokens", PLANNED_OUTPUT_TOKENS)
        started = time.time()
        last, used_attempt, sent = None, 1, False
        for used_attempt in range(1, attempts + 1):
            sent = True
            try:
                last = transport(model=model, messages=messages,
                                 max_output_tokens=cap)
                break
            except Exception as error:  # a transport failure is a status, not a crash
                last = {"status": "transport_error", "error": str(error)[:200],
                        "tokens_in": None, "tokens_out": None, "raw": ""}
        saved_ok = bool(last and last.get("status") == "ok")
        target = attempt_path(responses, job["task_id"], job["arm"], used_attempt)
        if saved_ok:
            atomic_write_text(target, json.dumps(
                {"task_id": job["task_id"], "arm": job["arm"], "model_requested": model,
                 "model_returned": last.get("model_returned"), "messages": messages,
                 "raw": last.get("raw", ""), "tokens_in": last.get("tokens_in"),
                 "tokens_out": last.get("tokens_out"), "cost_usd": None,
                 "price_per_million": list(price_per_million),
                 "attempt": used_attempt, "latency_s": round(time.time() - started, 2)},
                ensure_ascii=False))
            os.chmod(target, 0o600)
        tokens_in = last.get("tokens_in") if last else None
        tokens_out = last.get("tokens_out") if last else None
        if isinstance(tokens_in, int) and isinstance(tokens_out, int):
            cost = round(estimate_cost(tokens_in, tokens_out, price_per_million), 7)
        else:
            # A request may have been sent without a usable result.  That is not free,
            # so its cost stays unknown instead of being recorded as zero.
            cost = None
        status = last.get("status", "ok") if last else "result_unknown"
        if sent and not saved_ok:
            status = "result_unknown"
        if saved_ok:
            saved = json.loads(target.read_text(encoding="utf-8"))
            saved["cost_usd"] = cost
            atomic_write_text(target, json.dumps(saved, ensure_ascii=False))
        row = {"task_id": job["task_id"], "arm": job["arm"], "model_requested": model,
               "model_returned": last.get("model_returned") if last else None,
               "status": status, "attempts": used_attempt,
               "tokens_in": tokens_in, "tokens_out": tokens_out, "cost_usd": cost,
               "latency_s": round(time.time() - started, 2),
               "retrieved_lines": retrieved, "response_file": str(target),
               "identity_digest": report["identity_digest"]}
        append_ledger(ledger, row)
        rows.append(row)
        if cost is not None:
            spent += cost
        report["runs"].append(row)
    report["known_spend_after"] = round(spent, 6)
    report["unknown_cost_rows"] += sum(1 for r in report["runs"]
                                       if r.get("cost_usd") is None)
    return report


def rescore(bundle_path, responses, out, *, tasks_without_response_count_as_failure=True,
            ledger=None, allow_scorer_change=False):
    """Rebuild the summary from saved responses.  No network, no cost.

    Each item is scored from the very file its ledger row points at, so a retry can never
    leave the ledger describing one answer while scoring reads another.
    """
    bundle = load_bundle(bundle_path)
    fp = scorer_fingerprint()
    scorer_changed = None
    if allow_scorer_change and bundle.get("scorer_sha256") != fp["sha256"]:
        # A post-hoc rescore of answers produced under an earlier scorer is allowed only
        # when asked for explicitly, and it is recorded.  run() keeps the hard refusal.
        scorer_changed = {"bundle": bundle.get("scorer_sha256"), "loaded": fp["sha256"]}
        bundle = dict(bundle, scorer_sha256=fp["sha256"])
    check_bundle(bundle, fp)
    by_key = {}
    if ledger and Path(ledger).is_file():
        for row in load_ledger(ledger):
            by_key[(row["task_id"], row["arm"])] = row
    items = []
    for task in bundle["tasks"]:
        for arm in ARMS:
            row = by_key.get((task["task_id"], arm))
            if row and row.get("response_file") and Path(row["response_file"]).is_file():
                path = Path(row["response_file"])
            else:
                saved_files = saved_attempts(responses, task["task_id"], arm)
                path = saved_files[-1] if saved_files else response_path(responses,
                                                                        task["task_id"], arm)
            if not path.is_file():
                if tasks_without_response_count_as_failure:
                    items.append({"task_id": task["task_id"], "arm": arm,
                                  "status": "missing_response", "task_success": False})
                continue
            saved = json.loads(path.read_text(encoding="utf-8"))
            answer = _parse_answer(saved.get("raw", ""))
            unresolved = ambiguous = 0
            if answer.get("selected_records"):
                resolved_items, unresolved, ambiguous = resolve_items(
                    answer["selected_records"], task["records"],
                    task["contract"]["time_role"])
                answer = {"status": answer["status"], "selected_records": resolved_items,
                          "_unresolved": unresolved, "_ambiguous": ambiguous}
            scored = score({"task_id": task["task_id"],
                            "time_role": task["contract"]["time_role"],
                            "spec": {"window": task["contract"]["window"],
                                     "selection": task["contract"]["selection"],
                                     "contract": task["contract"]}},
                           answer, task["records"], task["reference"])
            items.append({"task_id": task["task_id"], "arm": arm,
                          "status": saved.get("status", "ok"),
                          "model_returned": saved.get("model_returned"),
                          "unresolved_items": unresolved, "ambiguous_items": ambiguous,
                          "set_exact_match": scored["set_exact_match"],
                          "status_ok": scored["status_ok"],
                          "fields_match": scored["fields_match"],
                          "task_success": scored["task_success"],
                          "field_mismatches": scored["field_mismatches"]})
    summary = {"probe_version": VERSION, "scorer": fp,
               "post_hoc": bool(scorer_changed), "scorer_changed": scorer_changed,
               "tasks": len(bundle["tasks"]), "items": len(items),
               "by_arm": {}, "failures": [i for i in items if not i.get("task_success")],
               "missing_responses": [i for i in items if i.get("status") == "missing_response"],
               "ambiguous_items": sum(i.get("ambiguous_items") or 0 for i in items),
               "unresolved_items": sum(i.get("unresolved_items") or 0 for i in items)}
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


class ProbeError(RuntimeError):
    """A configuration or provenance failure that must stop the run."""


class RunIdentityMismatch(ProbeError):
    """A run directory belongs to a different experiment."""


def atomic_write_text(target, text):
    """Write beside the target and replace it, so a reader never sees a half file."""
    target = Path(target)
    target.parent.mkdir(parents=True, exist_ok=True)
    tmp = target.with_name(target.name + ".tmp")
    tmp.write_text(text, encoding="utf-8")
    os.replace(tmp, target)


def _sha256_text(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def run_identity(bundle_path, bundle, *, model, params, tools):
    """Everything that makes one run that run, so a resume can be checked against it.

    Resuming used to look only at task id and arm, so swapping the model in the same
    directory silently reused the old answers.
    """
    prompt_material = json.dumps([[t.get("task_id"), t.get("instruction"), t.get("contract")]
                                  for t in bundle.get("tasks", [])], ensure_ascii=False,
                                 sort_keys=True)
    return {"bundle_sha256": hashlib.sha256(Path(bundle_path).read_bytes()).hexdigest(),
            "prompt_sha256": _sha256_text(INSTRUCTION + prompt_material),
            "model": model, "params": dict(params or {}), "tools": dict(tools or {}),
            "code_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
            "scorer_sha256": scorer_fingerprint()["sha256"]}


def identity_digest(identity):
    return _sha256_text(json.dumps(identity, ensure_ascii=False, sort_keys=True))


def require_identity(run_dir, identity):
    """Create the manifest once, then refuse any run whose identity differs."""
    run_dir = Path(run_dir)
    manifest = run_dir / "run_identity.json"
    record = {"identity": identity, "digest": identity_digest(identity)}
    if not manifest.is_file():
        atomic_write_text(manifest, json.dumps(record, ensure_ascii=False, indent=2))
        return "created"
    existing = json.loads(manifest.read_text(encoding="utf-8"))
    if existing.get("identity") != identity:
        differing = sorted(key for key in set(existing.get("identity", {})) | set(identity)
                           if existing.get("identity", {}).get(key) != identity.get(key))
        raise RunIdentityMismatch(
            "RUN_IDENTITY_MISMATCH differing=%s expected_digest=%s got_digest=%s"
            % (",".join(differing), existing.get("digest"), record["digest"]))
    return "matched"


def attempt_path(responses, task_id, arm, attempt):
    return Path(responses) / ("%s__%s__attempt%d.json" % (task_id, arm, attempt))


def saved_attempts(responses, task_id, arm):
    return sorted(Path(responses).glob("%s__%s__attempt*.json" % (task_id, arm)))


def recover_ledger(ledger, responses, jobs):
    """Rebuild ledger rows from saved responses.  No call is made for them."""
    rows = load_ledger(ledger)
    known = {(row["task_id"], row["arm"]) for row in rows}
    recovered = 0
    for job in jobs:
        key = (job["task_id"], job["arm"])
        if key in known:
            continue
        saved = saved_attempts(responses, job["task_id"], job["arm"])
        if not saved:
            continue
        last = saved[-1]
        try:
            payload = json.loads(last.read_text(encoding="utf-8"))
        except (ValueError, OSError):
            continue
        row = {"task_id": job["task_id"], "arm": job["arm"],
               "model_requested": payload.get("model_requested"),
               "model_returned": payload.get("model_returned"),
               "status": "recovered_from_response", "attempts": len(saved),
               "tokens_in": payload.get("tokens_in") or 0,
               "tokens_out": payload.get("tokens_out") or 0,
               "cost_usd": payload.get("cost_usd"),
               "latency_s": payload.get("latency_s"),
               "response_file": str(last), "recovered": True}
        append_ledger(ledger, row)
        rows.append(row)
        recovered += 1
    return recovered, rows


def _value_unit_match(item, record):
    try:
        expected = _finite(record.get("value"))
        got = _finite(item.get("value"))
    except Exception:
        return False
    if expected is None or got is None:
        return False
    if abs(got - expected) > 1e-6 * max(1.0, abs(expected)):
        return False
    return _norm_unit(item.get("unit")) == _norm_unit(record.get("unit"))


def _day_match(item, record, role):
    day = item.get("day_offset")
    if day is None:
        day = item.get("%s_day_offset" % role)
    if day is None:
        return True
    number = _finite(day)
    if number is None or not float(number).is_integer():
        return False
    expected = record.get("%s_day_offset" % role)
    return expected is None or int(number) == int(expected)


def _source_overlap(item, record):
    claimed = item.get("source_refs") or []
    if not isinstance(claimed, (list, tuple)) or not claimed:
        return True
    own = {str(record.get(field)) for field in
           ("project_ref", "result_ref", "unit_ref", "collection_ref", "report_ref")
           if record.get(field)}
    own |= {str(ref) for ref in (record.get("alias_refs") or [])}
    return bool({str(ref) for ref in claimed} & own)


def resolve_items(items, records, role):
    """Decide which record an answer item refers to.  The program does not guess.

    No candidate by value and unit means the item is unmatched and stays as a wrong
    answer.  Exactly one candidate is linked and then field-checked.  Several candidates
    are narrowed by the answer's own day and then by its own source lines.  Several still
    means the answer is ambiguous and is NOT silently turned into the first candidate.
    """
    resolved, unresolved, ambiguous = [], 0, 0
    for item in items or []:
        if isinstance(item, str):
            resolved.append(item)
            continue
        if not isinstance(item, dict):
            unresolved += 1
            continue
        identifier = item.get("record_id") or item.get("id")
        if isinstance(identifier, str):
            resolved.append(item)
            continue
        candidates = [record for record in records if _value_unit_match(item, record)]
        if not candidates:
            unresolved += 1
            resolved.append(item)
            continue
        if len(candidates) > 1:
            narrowed = [record for record in candidates if _day_match(item, record, role)]
            if narrowed:
                candidates = narrowed
        if len(candidates) > 1:
            narrowed = [record for record in candidates if _source_overlap(item, record)]
            if narrowed:
                candidates = narrowed
        if len(candidates) != 1:
            ambiguous += 1
            resolved.append(item)
            continue
        filled = dict(item)
        filled["record_id"] = candidates[0]["record_id"]
        resolved.append(filled)
    return resolved, unresolved, ambiguous


def _parse_answer(raw):
    """Parse a saved response body without raising on malformed content.

    A saved body is the provider envelope, so the assistant text is unwrapped first and
    the answer object is then located inside it.  A fenced code block is stripped too.
    """
    text = raw or ""
    try:
        envelope = json.loads(text)
    except (ValueError, TypeError):
        envelope = None
    if isinstance(envelope, dict):
        choices = envelope.get("choices")
        if isinstance(choices, list) and choices:
            message = choices[0].get("message") if isinstance(choices[0], dict) else None
            if isinstance(message, dict) and isinstance(message.get("content"), str):
                text = message["content"]
    text = text.replace("```json", "```")
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
