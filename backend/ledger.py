"""Evidence ledger and grounding verification for MuleTrace (Phases 10-11).

Tracks factual claims produced by tool executions and verifies that the agent's
final outputs are strictly grounded in tool observations.
"""
from __future__ import annotations

import copy
from typing import Any, Dict, List, Optional, Set


class EvidenceLedger:
    """Session ledger tracking tool observations and verifying grounding."""

    def __init__(self, session_id: Optional[str] = None):
        self.session_id = session_id
        self.tool_calls: List[Dict[str, Any]] = []
        self.observed_accounts: Set[str] = set()
        self.observed_txns: Set[str] = set()
        self.observed_devices: Set[str] = set()
        self.observed_cashouts: Set[str] = set()

        self.last_freeze_list_result: Optional[Dict[str, Any]] = None
        self.last_past_cases_result: Optional[Dict[str, Any]] = None
        self.memory_saved: bool = False

    def record_tool_call(self, tool_name: str, arguments: Dict[str, Any], result: Dict[str, Any]) -> None:
        """Record an executed tool invocation and extract facts."""
        self.tool_calls.append({
            "tool_name": tool_name,
            "arguments": arguments,
            "result": copy.deepcopy(result),
        })

        if tool_name == "build_freeze_list":
            if "items" in result:
                self.last_freeze_list_result = result
        elif tool_name == "recall_past_cases":
            if "items" in result:
                self.last_past_cases_result = result
        elif tool_name == "save_case_to_memory":
            if result.get("saved") is True:
                self.memory_saved = True

        # Extract accounts and transactions
        if isinstance(result, dict):
            for k, v in result.items():
                if k == "account" and isinstance(v, str):
                    self.observed_accounts.add(v)
                elif k in ("items", "nodes", "paths") and isinstance(v, list):
                    for item in v:
                        if isinstance(item, dict):
                            if "account" in item:
                                self.observed_accounts.add(item["account"])
                            if "id" in item and item.get("label") == "Account":
                                self.observed_accounts.add(item["id"])
                            if "path" in item and isinstance(item["path"], list):
                                for node_id in item["path"]:
                                    self.observed_accounts.add(node_id)
                            if "txn_id" in item:
                                self.observed_txns.add(item["txn_id"])

    def get_freeze_list(self) -> List[Dict[str, Any]]:
        """Return the items from the last build_freeze_list tool call."""
        if self.last_freeze_list_result and "items" in self.last_freeze_list_result:
            return copy.deepcopy(self.last_freeze_list_result["items"])
        return []

    def get_not_recommended(self) -> List[Dict[str, Any]]:
        """Return the not_recommended items from the last build_freeze_list tool call."""
        if self.last_freeze_list_result and "not_recommended" in self.last_freeze_list_result:
            return copy.deepcopy(self.last_freeze_list_result["not_recommended"])
        return []

    def get_past_cases(self) -> List[Dict[str, Any]]:
        """Return the past cases discovered by recall_past_cases."""
        if self.last_past_cases_result and "items" in self.last_past_cases_result:
            items_container = self.last_past_cases_result["items"]
            if isinstance(items_container, dict) and "items" in items_container:
                return copy.deepcopy(items_container["items"])
            if isinstance(items_container, list):
                return copy.deepcopy(items_container)
        return []

    def is_memory_saved(self) -> bool:
        return self.memory_saved

    def get_total_recoverable(self) -> int:
        if self.last_freeze_list_result:
            return self.last_freeze_list_result.get("total_recoverable", 0)
        return 0

    def get_total_cashed_out(self) -> int:
        if self.last_freeze_list_result:
            return self.last_freeze_list_result.get("total_cashed_out", 0)
        return 0

    def ground_freeze_list(self, freeze_items: List[Dict[str, Any]]) -> tuple[List[Dict[str, Any]], int]:
        """Verify freeze list items against the tool output of build_freeze_list.

        Returns (verified_items, claims_removed_count).
        """
        tool_items = self.get_freeze_list()
        tool_items_by_account = {it["account"]: it for it in tool_items}

        grounded = []
        claims_removed = 0

        for item in freeze_items:
            aid = item.get("account")
            if aid in tool_items_by_account:
                # Grounded in actual tool output
                grounded.append(copy.deepcopy(tool_items_by_account[aid]))
            else:
                claims_removed += 1

        return grounded, claims_removed
