"""Post-run, read-only telemetry attribution; never drives the robot or a model.

Codex exec JSON exposes turn totals. Its local rollout additionally exposes model
response usage. Only a response containing exactly one tool call is attributable
to that call; shared/missing usage is never divided or guessed.
"""

from __future__ import annotations

import argparse
from collections import defaultdict
import hashlib
import json
import math
import os
from pathlib import Path
import re

TOKEN_FIELDS = (
    "input_tokens",
    "cached_input_tokens",
    "cache_write_input_tokens",
    "output_tokens",
    "reasoning_output_tokens",
    "total_tokens",
)


def arguments_hash(arguments):
    return hashlib.sha256(
        json.dumps(arguments, sort_keys=True, ensure_ascii=False, separators=(",", ":"), allow_nan=False).encode()
    ).hexdigest()


def read_records(path, warnings):
    if not path.is_file():
        return []
    records = []
    try:
        with path.open(encoding="utf-8") as stream:
            for line in stream:
                try:
                    row = json.loads(line)
                    if not isinstance(row, dict):
                        raise ValueError()
                    records.append(row)
                except (ValueError, UnicodeError):
                    warnings.append("invalid_record:" + path.name)
    except (OSError, UnicodeError):
        warnings.append("unreadable:" + path.name)
    return records


def usage_fields(value):
    if not isinstance(value, dict):
        return None
    result = {k: value.get(k) for k in TOKEN_FIELDS}
    for v in result.values():
        if v is not None and (type(v) is not int or v < 0):
            return None
    if result["input_tokens"] is None or result["output_tokens"] is None:
        return None
    total = result["input_tokens"] + result["output_tokens"]
    if result["total_tokens"] is not None and result["total_tokens"] != total:
        return None
    result["total_tokens"] = total
    return result


def find_rollout(thread_id, home, warnings):
    # Do not inspect unrelated sessions or expose their content in artifacts.
    if not isinstance(thread_id, str) or not re.fullmatch(r"[a-fA-F0-9-]{36}", thread_id):
        return None
    matches = []
    try:
        for directory in ("sessions", "archived_sessions"):
            matches.extend((home / directory).rglob("rollout-*-" + thread_id + ".jsonl"))
    except OSError:
        warnings.append("rollout_discovery_failed")
    if len(matches) != 1:
        warnings.append("rollout_missing_or_ambiguous")
        return None
    return matches[0]


def rollout_calls(records):
    """Use one usage stream, never count both modern records and token_count."""
    modern = any(r.get("type") == "token_usage_record" for r in records)
    pending, calls = [], []
    seen_responses = set()
    previous_total = None
    for record in records:
        payload = record.get("payload") or {}
        if not isinstance(payload, dict):
            continue
        kind = payload.get("type")
        if record.get("type") == "response_item" and kind in ("function_call", "custom_tool_call"):
            arguments = payload.get("arguments")
            try:
                arguments = json.loads(arguments) if isinstance(arguments, str) else arguments
                fingerprint = arguments_hash(arguments) if isinstance(arguments, dict) else None
            except (ValueError, TypeError):
                fingerprint = None
            call = dict(
                call_id=payload.get("call_id"),
                name=payload.get("name"),
                arguments_sha256=fingerprint,
                token_usage=None,
                token_usage_status="missing_response_usage",
                token_usage_source=None,
                response_id=None,
            )
            calls.append(call)
            pending.append(call)
        if modern:
            if record.get("type") != "token_usage_record":
                continue
            response_id = payload.get("response_id")
            if response_id and response_id in seen_responses:
                continue
            if response_id:
                seen_responses.add(response_id)
            usage = usage_fields(payload.get("usage"))
            source = "codex_rollout.token_usage_record"
        else:
            if record.get("type") != "event_msg" or kind != "token_count":
                continue
            info = payload.get("info") or {}
            if not isinstance(info, dict):
                continue
            total = usage_fields(info.get("total_token_usage"))
            # Rate-limit notifications can repeat an unchanged token count.
            if total is None or total == previous_total:
                continue
            usage = usage_fields(info.get("last_token_usage"))
            if previous_total is not None and usage is not None:
                if any(total[k] - previous_total[k] != usage[k] for k in ("input_tokens", "output_tokens")):
                    usage = None  # Missing response boundary or compaction/reset.
            previous_total = total
            response_id = None
            source = "codex_rollout.token_count.last_token_usage"
        for call in pending:
            call.update(response_id=response_id, token_usage_source=source)
            if usage is None:
                call["token_usage_status"] = "invalid_response_usage"
            elif len(pending) != 1:
                call["token_usage_status"] = "shared_response_usage"
            else:
                call.update(token_usage=usage, token_usage_status="available")
        pending = []
    return calls


def seconds(value):
    return value if type(value) in (int, float) and math.isfinite(value) and value >= 0 else None


def build_report(output, codex_home=None):
    output = Path(output)
    warnings = []
    events = read_records(output / "codex_events.jsonl", warnings)
    metrics = read_records(output / "mcp_metrics.jsonl", warnings)
    host_executions = defaultdict(list)
    for event in read_records(output / "history.jsonl", warnings):
        if event.get("event") == "execution" and isinstance(event.get("request_id"), str):
            host_executions[event["request_id"]].append(event)
    thread_ids = {
        r["thread_id"] for r in events if r.get("type") == "thread.started" and isinstance(r.get("thread_id"), str)
    }
    thread_id = next(iter(thread_ids)) if len(thread_ids) == 1 else None
    home = Path(codex_home or os.environ.get("CODEX_HOME") or Path.home() / ".codex")
    rollout = find_rollout(thread_id, home, warnings)
    before_read = len(warnings)
    records = read_records(rollout, warnings) if rollout else []
    if len(warnings) != before_read:
        # A missing call/boundary could silently attribute another response.
        records = []
    # Verify the file's identity, not just its filename.
    if records and not any(
        r.get("type") == "session_meta" and isinstance(r.get("payload"), dict) and r["payload"].get("id") == thread_id
        for r in records
    ):
        warnings.append("rollout_identity_mismatch")
        records = []
    calls = rollout_calls(records)
    by_arguments = defaultdict(list)
    for call in calls:
        if call["name"] in ("act", "mcp__sim__act"):
            by_arguments[call["arguments_sha256"]].append(call)

    # Preserve started calls even if the process died before item.completed.
    items = {}
    for event in events:
        item = event.get("item") or {}
        if (
            isinstance(item, dict)
            and item.get("type") == "mcp_tool_call"
            and item.get("server") == "sim"
            and item.get("tool") == "act"
        ):
            if isinstance(item.get("id"), str) and isinstance(item.get("arguments"), dict):
                try:
                    arguments_hash(item["arguments"])
                    items[item["id"]] = item
                except (ValueError, TypeError):
                    warnings.append("invalid_action_arguments")
            else:
                warnings.append("invalid_action_event")
    action_metrics = [r for r in metrics if r.get("event") == "tool_call" and r.get("tool") == "act"]
    metric_groups = defaultdict(list)
    for metric in action_metrics:
        if metric.get("arguments_sha256"):
            metric_groups[metric["arguments_sha256"]].append(metric)
    item_groups = defaultdict(list)
    for item in items.values():
        try:
            item_groups[arguments_hash(item.get("arguments"))].append(item)
        except (ValueError, TypeError):
            warnings.append("invalid_action_arguments")
    actions, used_metrics = [], set()
    for item in items.values():
        fingerprint = arguments_hash(item.get("arguments"))
        unique = len(item_groups[fingerprint]) == 1
        candidates = by_arguments[fingerprint]
        call = candidates[0] if unique and len(candidates) == 1 else None
        candidates = metric_groups[fingerprint]
        metric = candidates[0] if unique and len(candidates) == 1 else None
        if metric is not None:
            used_metrics.add(id(metric))
        actions.append(
            dict(
                action_index=len(actions) + 1,
                codex_item_id=item["id"],
                observation_id=(item.get("arguments") or {}).get("observation_id"),
                arguments_sha256=fingerprint,
                status=item.get("status"),
                call_id=call["call_id"] if call else None,
                response_id=call["response_id"] if call else None,
                token_usage=call["token_usage"] if call else None,
                token_usage_status=call["token_usage_status"] if call else "unmatched_rollout_call",
                token_usage_source=call["token_usage_source"] if call else None,
                _metric=metric,
            )
        )
    # Keep genuinely extra MCP calls when stdout was truncated. Ambiguous timing
    # records are separate rather than counting the same action twice.
    unmatched_metrics = []
    for metric in action_metrics:
        if id(metric) not in used_metrics:
            fingerprint = metric.get("arguments_sha256")
            if items and (not fingerprint or fingerprint in item_groups):
                unmatched_metrics.append(
                    {
                        k: metric.get(k)
                        for k in (
                            "call",
                            "request_id",
                            "observation_id",
                            "tool_seconds",
                            "http_seconds",
                            "image_seconds",
                            "ok",
                        )
                    }
                )
                continue
            actions.append(
                dict(
                    action_index=len(actions) + 1,
                    codex_item_id=None,
                    observation_id=metric.get("observation_id"),
                    call_id=None,
                    response_id=None,
                    token_usage=None,
                    token_usage_status="missing_codex_event",
                    token_usage_source=None,
                    _metric=metric,
                )
            )
    for action in actions:
        metric = action.pop("_metric")
        action.update(
            execution_seconds=seconds(metric.get("tool_seconds")) if metric else None,
            http_seconds=seconds(metric.get("http_seconds")) if metric else None,
            image_seconds=seconds(metric.get("image_seconds")) if metric else None,
            mcp_call=metric.get("call") if metric else None,
            request_id=metric.get("request_id") if metric else None,
            ok=metric.get("ok") if metric else None,
            execution_time_source="mcp_metrics.tool_seconds" if metric else None,
        )
        host = host_executions.get(action["request_id"], [])
        host = host[0] if len(host) == 1 else {}
        action["host_execution_seconds"] = seconds(host.get("execution_seconds"))
        action["host_feedback"] = host.get("feedback")
    usages = [a["token_usage"] for a in actions if a["token_usage"] is not None]
    times = [a["execution_seconds"] for a in actions if a["execution_seconds"] is not None]
    totals = {
        k: sum(u[k] for u in usages) if usages and all(u[k] is not None for u in usages) else None for k in TOKEN_FIELDS
    }
    return dict(
        schema_version=1,
        thread_id=thread_id,
        token_usage_scope="model_response_generating_single_act",
        execution_time_scope="mcp_tool_handler_excludes_model_generation",
        actions=actions,
        summary=dict(
            action_count=len(actions),
            actions_with_token_usage=len(usages),
            actions_with_execution_time=len(times),
            unmatched_execution_count=len(unmatched_metrics),
            complete=(len(usages) == len(times) == len(actions) and not warnings and not unmatched_metrics),
            attributed_action_tokens=totals,
            recorded_execution_seconds=sum(times) if times else None,
        ),
        turn_usage=[r["usage"] for r in events if r.get("type") == "turn.completed" and "usage" in r],
        unmatched_execution_metrics=unmatched_metrics,
        warnings=sorted(set(warnings)),
    )


def write_report(output, codex_home=None):
    """Write only the independent telemetry artifact; never touch result.json."""
    from execution.artifacts import write_json

    output = Path(output)
    report = build_report(output, codex_home)
    write_json(output / "action_metrics.json", report, durable=True)
    return report


def main():
    parser = argparse.ArgumentParser(description="Rebuild per-action telemetry after an episode has stopped.")
    parser.add_argument("output", type=Path)
    parser.add_argument("--codex-home", type=Path)
    args = parser.parse_args()
    report = write_report(args.output, args.codex_home)
    print(json.dumps(report["summary"], ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
