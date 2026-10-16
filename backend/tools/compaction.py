"""Output compaction helper for MuleTrace tools.

Groq free-tier and small-context models require compact outputs to avoid token overflow.
Every tool result passes through `compact_output`:
1. Serializes to a compact JSON dict.
2. Trims to about 3,000 characters if oversized, dropping secondary fields first while
   strictly preserving 'path', 'truncated', and 'total'.
3. Adds a helpful 'note' instructing the LLM how to narrow its query when truncated.
"""
from __future__ import annotations

import copy
import json
from typing import Any, Dict, List, Optional

DEFAULT_MAX_CHARS = 3000
TRUNCATION_NOTE = (
    "Result truncated to fit token limits. Narrow query using smaller time window, "
    "higher min_amount, or smaller top_k/max_hops."
)

# Fields that should never be stripped during compaction
CRITICAL_FIELDS = {"path", "paths", "truncated", "total", "error", "hint", "account", "from", "to", "amount"}
# Fields that can be safely discarded first when trimming item verbosity
LOW_PRIORITY_FIELDS = {"location", "holder_name", "description", "details", "bank", "account_type"}


def _serialize_len(obj: Any) -> int:
    try:
        return len(json.dumps(obj, separators=(",", ":"), default=str))
    except Exception:
        return len(str(obj))


def compact_output(result: Any, max_chars: int = DEFAULT_MAX_CHARS) -> Dict[str, Any]:
    """Compacts and bounds tool output to approximately max_chars."""
    if not isinstance(result, dict):
        if isinstance(result, list):
            result = {"items": result, "total": len(result), "truncated": False}
        else:
            result = {"result": result}

    # If already within limit, return directly
    if _serialize_len(result) <= max_chars:
        return result

    data = copy.deepcopy(result)
    is_truncated = False

    candidate_keys = ["items", "paths", "nodes", "edges", "events", "splits", "ranks", "components", "communities", "members"]

    # 1. Trim wrapped containers: {"truncated": bool, "total": int, "items": list}
    for k, v in list(data.items()):
        if isinstance(v, dict) and "items" in v and isinstance(v["items"], list):
            items_list = v["items"]
            orig_total = v.get("total", len(items_list))
            v["total"] = orig_total

            while len(v["items"]) > 1 and _serialize_len(data) > (max_chars - 300):
                new_len = max(1, len(v["items"]) // 2)
                v["items"] = v["items"][:new_len]
                v["truncated"] = True
                is_truncated = True

    # 2. Trim direct list fields
    for k in candidate_keys:
        if k in data and isinstance(data[k], list) and len(data[k]) > 1:
            orig_total = data.get("total", len(data[k]))
            data["total"] = orig_total
            while len(data[k]) > 1 and _serialize_len(data) > (max_chars - 300):
                new_len = max(1, len(data[k]) // 2)
                data[k] = data[k][:new_len]
                data["truncated"] = True
                is_truncated = True

    # 3. Trim nested sub-lists inside items (e.g. "members" in components, "sharing_accounts")
    for k, v in list(data.items()):
        target_list = None
        if isinstance(v, list):
            target_list = v
        elif isinstance(v, dict) and isinstance(v.get("items"), list):
            target_list = v["items"]

        if target_list and isinstance(target_list, list):
            for item in target_list:
                if isinstance(item, dict):
                    for subk, subv in list(item.items()):
                        if isinstance(subv, list) and len(subv) > 5 and subk not in ("path", "paths"):
                            item[subk] = subv[:5]
                            is_truncated = True

    # 4. Strip low-priority fields from items inside lists if still too long
    if _serialize_len(data) > (max_chars - 200):
        for k, v in list(data.items()):
            target_list = None
            if isinstance(v, list):
                target_list = v
            elif isinstance(v, dict) and isinstance(v.get("items"), list):
                target_list = v["items"]

            if target_list and isinstance(target_list, list):
                for item in target_list:
                    if isinstance(item, dict):
                        for low_k in LOW_PRIORITY_FIELDS:
                            if low_k in item and low_k not in CRITICAL_FIELDS:
                                item.pop(low_k, None)

    # 5. Aggressive slicing down to 1 item / sub-lists down to 2 if still over budget
    if _serialize_len(data) > max_chars:
        for k, v in list(data.items()):
            if isinstance(v, dict) and "items" in v and isinstance(v["items"], list):
                v["items"] = v["items"][:1]
                v["truncated"] = True
                is_truncated = True
                if v["items"] and isinstance(v["items"][0], dict):
                    for subk, subv in list(v["items"][0].items()):
                        if isinstance(subv, list) and len(subv) > 2 and subk not in ("path", "paths"):
                            v["items"][0][subk] = subv[:2]
            elif isinstance(v, list) and k in candidate_keys:
                data[k] = data[k][:1]
                data["truncated"] = True
                is_truncated = True

    # 6. Truncate long strings if still over budget
    if _serialize_len(data) > max_chars:
        def _trim_strings(obj: Any) -> Any:
            if isinstance(obj, dict):
                return {dk: _trim_strings(dv) for dk, dv in obj.items()}
            elif isinstance(obj, list):
                return [_trim_strings(elem) for elem in obj]
            elif isinstance(obj, str) and len(obj) > 100 and obj not in CRITICAL_FIELDS:
                return obj[:100] + "..."
            return obj

        data = _trim_strings(data)
        is_truncated = True

    # Mark truncated and append guidance note
    if is_truncated or data.get("truncated"):
        data["truncated"] = True
        data["note"] = TRUNCATION_NOTE

    return data
