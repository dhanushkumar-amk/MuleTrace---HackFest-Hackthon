"""Single source of truth for MuleTrace agent tools (Phase 9).

Registers all 17 read-only graph query and algorithm tools with typed Pydantic
input schemas, prompt-optimized descriptions (<80 words), robust error handling,
per-call timeouts (10s), execution tracing, and Groq-friendly token compaction.

Safety invariants:
- Read-only against graph. No tool accepts raw Cypher.
- Never reads test files, documentation, or answer keys.
"""
from __future__ import annotations

import concurrent.futures
import time
from typing import Any, Callable, Dict, List, Literal, Optional, Type
from pydantic import BaseModel, Field, field_validator

from backend.db import get_graph
from backend import queries
from backend import algorithms
from backend import freeze
from backend import memory
from backend.tools.compaction import compact_output, _serialize_len
from backend.tools import trace

ToolKind = Literal["query", "algorithm", "action"]
DEFAULT_TIMEOUT_SECONDS = 10.0


# ===========================================================================
# 1. Pydantic Input Models
# ===========================================================================

class GetFraudReportInput(BaseModel):
    report_id: str = Field(
        ...,
        description="Unique ID of the filed fraud report (e.g. 'FR_0001').",
    )


class GetAccountProfileInput(BaseModel):
    account_id: str = Field(
        ...,
        description="Account ID to analyze behavioral features for (e.g. 'ACC_0461').",
    )


class TraceMoneyForwardInput(BaseModel):
    start_account_id: str = Field(
        ...,
        description="Account ID where stolen money originated (e.g. victim account).",
    )
    start_time: int = Field(
        ...,
        description="Epoch timestamp of initial theft to follow forward. Note: theft occurs prior to report filing, so pass ~2 hours before reported_at (e.g. reported_at - 7200).",
    )
    max_hops: int = Field(
        default=8,
        ge=1,
        le=20,
        description="Maximum forward transfer hops to trace.",
    )
    min_amount: Optional[int] = Field(
        default=None,
        ge=0,
        description="Optional minimum transfer amount threshold.",
    )
    max_paths: int = Field(
        default=50,
        ge=1,
        le=200,
        description="Maximum distinct transfer paths to return.",
    )


class FindCashOutPointsInput(BaseModel):
    account_ids: List[str] = Field(
        ...,
        description="List of suspect account IDs to check for terminal cash-out events.",
    )
    limit: int = Field(
        default=200,
        ge=1,
        le=500,
        description="Maximum cash-out events to return.",
    )

    @field_validator("account_ids", mode="before")
    @classmethod
    def _coerce_list(cls, v: Any) -> List[str]:
        if isinstance(v, str):
            return [v]
        return list(v)


class GetBalanceHeldInput(BaseModel):
    account_ids: List[str] = Field(
        ...,
        description="List of target account IDs to inspect currently held balances.",
    )

    @field_validator("account_ids", mode="before")
    @classmethod
    def _coerce_list(cls, v: Any) -> List[str]:
        if isinstance(v, str):
            return [v]
        return list(v)


class FindSharedDevicesInput(BaseModel):
    account_id: str = Field(
        ...,
        description="Target account ID to discover other accounts sharing digital devices.",
    )


class FindSharedPhonesInput(BaseModel):
    account_id: str = Field(
        ...,
        description="Target account ID to discover other accounts sharing registered phone numbers.",
    )


class DetectRapidHopsInput(BaseModel):
    account_id: Optional[str] = Field(
        default=None,
        description="Optional account ID to inspect; if omitted, checks the entire network.",
    )
    window_seconds: int = Field(
        default=600,
        ge=1,
        description="Time window in seconds to identify >=70% forward transfers.",
    )
    limit: int = Field(
        default=20,
        ge=1,
        le=100,
        description="Maximum rapid-hop events to return.",
    )


class DetectFanInInput(BaseModel):
    window_seconds: int = Field(
        default=86400,
        ge=60,
        description="Time window in seconds for incoming aggregation.",
    )
    min_senders: int = Field(
        default=6,
        ge=2,
        description="Minimum distinct senders to qualify as fan-in aggregator.",
    )
    limit: int = Field(
        default=20,
        ge=1,
        le=100,
        description="Maximum aggregator accounts to return.",
    )


class DetectFanOutInput(BaseModel):
    account_id: str = Field(
        ...,
        description="Target account ID to check for outbound splitting.",
    )
    window_seconds: int = Field(
        default=3600,
        ge=60,
        description="Time window in seconds for outgoing splits.",
    )
    limit: int = Field(
        default=50,
        ge=1,
        le=200,
        description="Maximum fan-out events to return.",
    )


class GetNeighborhoodInput(BaseModel):
    account_id: str = Field(
        ...,
        description="Target account ID to extract local neighborhood subgraph around.",
    )
    hops: int = Field(
        default=2,
        ge=1,
        le=3,
        description="Number of hops for immediate neighborhood subgraph (1 or 2).",
    )
    limit: int = Field(
        default=60,
        ge=1,
        le=200,
        description="Maximum nodes in neighborhood.",
    )


class FindShortestPathInput(BaseModel):
    src_account_id: str = Field(
        ...,
        description="Source account ID.",
    )
    dst_account_id: str = Field(
        ...,
        description="Destination account ID.",
    )
    max_hops: int = Field(
        default=10,
        ge=1,
        le=20,
        description="Maximum hops to search.",
    )
    mode: str = Field(
        default="money",
        description="Mode: 'money' for transfer-only path, 'any' for hybrid device/phone path.",
    )
    max_device_sharing: int = Field(
        default=3,
        ge=1,
        description="Max accounts sharing a device/phone to be considered private.",
    )


class RankHubAccountsInput(BaseModel):
    window_start: Optional[int] = Field(
        default=None,
        description="Optional start timestamp for PageRank window.",
    )
    window_end: Optional[int] = Field(
        default=None,
        description="Optional end timestamp for PageRank window.",
    )
    top_k: int = Field(
        default=10,
        ge=1,
        le=50,
        description="Number of top hub accounts to return.",
    )
    weight: str = Field(
        default="amount",
        description="Edge weight: 'amount' for transfer volume, 'count' for unweighted.",
    )


class FindConnectedComponentsInput(BaseModel):
    window_start: Optional[int] = Field(
        default=None,
        description="Optional start timestamp.",
    )
    window_end: Optional[int] = Field(
        default=None,
        description="Optional end timestamp.",
    )
    min_size: int = Field(
        default=3,
        ge=2,
        description="Minimum component size.",
    )
    include_shared_devices: bool = Field(
        default=True,
        description="Whether to include shared device links.",
    )
    max_device_sharing: int = Field(
        default=3,
        ge=1,
        description="Maximum sharing threshold for devices.",
    )
    min_amount: Optional[float] = Field(
        default=None,
        description="Optional minimum transfer amount filter.",
    )
    limit: int = Field(
        default=20,
        ge=1,
        le=100,
        description="Maximum components to return.",
    )


class FindCommunitiesInput(BaseModel):
    window_start: Optional[int] = Field(
        default=None,
        description="Optional start timestamp.",
    )
    window_end: Optional[int] = Field(
        default=None,
        description="Optional end timestamp.",
    )
    resolution: float = Field(
        default=1.0,
        ge=0.1,
        le=5.0,
        description="Louvain modularity resolution parameter.",
    )
    limit: int = Field(
        default=20,
        ge=1,
        le=100,
        description="Maximum communities to return.",
    )
    max_device_sharing: int = Field(
        default=3,
        ge=1,
        description="Maximum sharing threshold for devices.",
    )
    dev_weight: float = Field(
        default=50000.0,
        description="Synthetic weight for device links.",
    )


class FindConnectedRingInput(BaseModel):
    account_id: str = Field(
        ...,
        description="Seed account ID to extract connected ring and community around.",
    )
    window_start: Optional[int] = Field(
        default=None,
        description="Optional start timestamp.",
    )
    window_end: Optional[int] = Field(
        default=None,
        description="Optional end timestamp.",
    )
    max_device_sharing: int = Field(
        default=3,
        ge=1,
        description="Maximum sharing threshold for devices.",
    )
    dev_weight: float = Field(
        default=50000.0,
        description="Synthetic weight for device links.",
    )


class RankChokepointsInput(BaseModel):
    account_ids: List[str] = Field(
        ...,
        description="List of suspect account IDs forming the induced subgraph.",
    )
    top_k: int = Field(
        default=5,
        ge=1,
        le=50,
        description="Number of top chokepoint accounts to return.",
    )

    @field_validator("account_ids", mode="before")
    @classmethod
    def _coerce_list(cls, v: Any) -> List[str]:
        if isinstance(v, str):
            return [v]
        return list(v)


class BuildFreezeListInput(BaseModel):
    report_id: str = Field(
        ...,
        description="Unique ID of the filed fraud report (e.g. 'FR_0001').",
    )
    candidate_account_ids: List[str] = Field(
        ...,
        max_length=15,
        description="List of suspect candidate account IDs (max 15) to independently verify and rank for freeze recommendation.",
    )

    @field_validator("candidate_account_ids", mode="before")
    @classmethod
    def _coerce_list(cls, v: Any) -> List[str]:
        if isinstance(v, str):
            return [v]
        return list(v)


class SaveCaseToMemoryInput(BaseModel):
    report_id: str = Field(
        ...,
        description="Unique ID of the filed fraud report (e.g. 'FR_0001').",
    )
    summary: str = Field(
        ...,
        description="High-level factual narrative of the fraud investigation findings.",
    )
    account_ids: Optional[List[str]] = Field(
        default=None,
        description="Optional subset of accounts to save. Must appear in the last build_freeze_list result.",
    )

    @field_validator("account_ids", mode="before")
    @classmethod
    def _coerce_list(cls, v: Any) -> Optional[List[str]]:
        if v is None:
            return None
        if isinstance(v, str):
            return [v]
        return list(v)


class RecallPastCasesInput(BaseModel):
    account_ids: List[str] = Field(
        ...,
        description="List of target account IDs to inspect for historical case involvement or shared device or phone connections.",
    )

    @field_validator("account_ids", mode="before")
    @classmethod
    def _coerce_list(cls, v: Any) -> List[str]:
        if isinstance(v, str):
            return [v]
        return list(v)


# ===========================================================================
# 2. ToolDefinition Class
# ===========================================================================

def _extract_path_field(res: Any) -> Optional[Any]:
    """Helper to locate path information in tool results for the trace log."""
    if not isinstance(res, dict):
        return None
    if "path" in res and res["path"]:
        return res["path"]
    if "paths" in res:
        paths_val = res["paths"]
        if isinstance(paths_val, dict) and "items" in paths_val and paths_val["items"]:
            return paths_val["items"][0]
        if isinstance(paths_val, list) and paths_val:
            return paths_val[0]
    if "items" in res and isinstance(res["items"], dict):
        items_list = res["items"].get("items")
        if isinstance(items_list, list) and items_list and isinstance(items_list[0], dict):
            if "path" in items_list[0]:
                return items_list[0]["path"]
    return None


class ToolDefinition:
    """Encapsulates a registered MuleTrace tool."""

    def __init__(
        self,
        name: str,
        description: str,
        input_model: Type[BaseModel],
        handler: Callable[..., Any],
        kind: ToolKind,
        timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
    ):
        self.name = name
        self.description = description
        self.input_model = input_model
        self.handler = handler
        self.kind = kind
        self.timeout_seconds = timeout_seconds

    def get_json_schema(self) -> Dict[str, Any]:
        """Return the JSON schema representation of the tool parameters."""
        schema = self.input_model.model_json_schema()
        # Clean schema title to match standard Groq tool-calling / MCP parameters conventions
        schema["title"] = f"{self.name}Arguments"
        return schema

    def execute(self, **kwargs: Any) -> Dict[str, Any]:
        """Execute the tool safely with parameter validation, timeout, tracing, and compaction."""
        t0 = time.perf_counter()

        # Step 1: Validate input parameters
        try:
            validated = self.input_model.model_validate(kwargs)
        except Exception as ve:
            duration_ms = (time.perf_counter() - t0) * 1000
            err_msg = f"Invalid arguments for tool '{self.name}': {str(ve)}"
            props = list(self.input_model.model_fields.keys())
            hint = f"Verify required fields: {props}. Ensure types match expected schema."
            res = {"error": err_msg, "hint": hint}
            trace.record(
                tool_name=self.name,
                arguments=kwargs,
                duration_ms=duration_ms,
                result_size=_serialize_len(res),
                ok=False,
                error=err_msg,
            )
            return compact_output(res)

        # Step 2: Execute with timeout
        def _invoke() -> Any:
            graph = get_graph()
            return self.handler(graph, **validated.model_dump())

        raw_result: Any = None
        exec_error: Optional[str] = None
        hint: Optional[str] = None

        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
            future = executor.submit(_invoke)
            try:
                raw_result = future.result(timeout=self.timeout_seconds)
            except concurrent.futures.TimeoutError:
                exec_error = f"Tool '{self.name}' timed out after {self.timeout_seconds} seconds."
                hint = "Narrow your search parameters (e.g. smaller window, lower hops, higher min_amount)."
            except Exception as exc:
                exec_error = f"Tool execution error in '{self.name}': {str(exc)}"
                hint = "Check whether referenced account or report IDs exist."

        duration_ms = (time.perf_counter() - t0) * 1000

        # Step 3: Handle execution errors or not-found results
        if exec_error:
            res = {"error": exec_error, "hint": hint or "Retry with corrected arguments."}
            trace.record(
                tool_name=self.name,
                arguments=kwargs,
                duration_ms=duration_ms,
                result_size=_serialize_len(res),
                ok=False,
                error=exec_error,
            )
            return compact_output(res)

        if isinstance(raw_result, dict) and raw_result.get("found") is False:
            err_msg = f"Target resource for '{self.name}' was not found in the graph."
            h = "Verify ID formatting (e.g. report 'FR_0001', account 'ACC_0461') or discover accounts first."
            res = {"error": err_msg, "hint": h, **raw_result}
            trace.record(
                tool_name=self.name,
                arguments=kwargs,
                duration_ms=duration_ms,
                result_size=_serialize_len(res),
                ok=False,
                error=err_msg,
            )
            return compact_output(res)

        # Step 4: Record trace and compact output
        path_info = _extract_path_field(raw_result)
        compacted = compact_output(raw_result)
        trace.record(
            tool_name=self.name,
            arguments=kwargs,
            duration_ms=duration_ms,
            result_size=_serialize_len(compacted),
            ok=True,
            path=path_info,
        )
        return compacted


# ===========================================================================
# 3. Registry Definition & Tool Registration
# ===========================================================================

_REGISTRY: Dict[str, ToolDefinition] = {}


def register_tool(
    name: str,
    description: str,
    input_model: Type[BaseModel],
    handler: Callable[..., Any],
    kind: ToolKind,
    timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
) -> ToolDefinition:
    """Register a tool in the global single source of truth."""
    tool_def = ToolDefinition(
        name=name,
        description=description,
        input_model=input_model,
        handler=handler,
        kind=kind,
        timeout_seconds=timeout_seconds,
    )
    _REGISTRY[name] = tool_def
    return tool_def


def get_tool(name: str) -> Optional[ToolDefinition]:
    """Retrieve a registered tool definition by name."""
    return _REGISTRY.get(name)


def list_tools() -> List[ToolDefinition]:
    """Return all registered tool definitions."""
    return list(_REGISTRY.values())


# Register all 17 tools wrapping existing queries and algorithms
register_tool(
    name="get_fraud_report",
    description="Retrieve details of a filed fraud report including stolen amount, reported timestamp, incident description, and victim account identity. Use first to initiate an investigation from a report ID. Do not use for tracing subsequent fund movement. Cannot prove whether recipient accounts are willful conspirators.",
    input_model=GetFraudReportInput,
    handler=queries.get_fraud_report,
    kind="query",
)

register_tool(
    name="get_account_profile",
    description="Compute transaction activity features for an account: balance, age, transaction counts, volume, and forwarding latency. Use to evaluate whether an account behaves like a mule or a legitimate merchant. Do not use for mapping multi-hop paths. High activity hints at mule behavior but cannot prove fraud without path context.",
    input_model=GetAccountProfileInput,
    handler=queries.get_account_profile,
    kind="query",
)

register_tool(
    name="trace_money_forward",
    description="Trace outgoing money transfers chronologically forward from an account starting at a given timestamp. Use to follow stolen funds hop-by-hop across recipient accounts. Do not use without a known start account and timestamp. Cannot prove whether recipient accounts are willful mules or compromised victims.",
    input_model=TraceMoneyForwardInput,
    handler=queries.trace_money_forward,
    kind="query",
)

register_tool(
    name="find_cash_out_points",
    description="Find terminal cash-out events (ATM withdrawals, crypto exchanges) linked to given accounts. Use to determine where stolen funds exit the banking network. Do not use on victim accounts. Identifies cash-out exit events but cannot prove the physical identity of the individual withdrawing funds.",
    input_model=FindCashOutPointsInput,
    handler=queries.find_cash_out_points,
    kind="query",
)

register_tool(
    name="get_balance_held",
    description="Retrieve current balances held across a list of accounts. Use to determine how much money sits in suspected mule accounts before deciding freeze amounts. Do not use for finding new connections. High balance confirms available funds but cannot prove fraud without incoming trace evidence.",
    input_model=GetBalanceHeldInput,
    handler=queries.get_balance_held,
    kind="query",
)

register_tool(
    name="find_shared_devices",
    description="Find other accounts sharing digital devices with the target account. Use to uncover co-conspirators or hidden mule rings controlled by the same operator. Do not use for tracing money transfers. Shared hardware indicates operational linkage but cannot prove transactions occurred between the accounts.",
    input_model=FindSharedDevicesInput,
    handler=queries.find_shared_devices,
    kind="query",
)

register_tool(
    name="find_shared_phones",
    description="Find accounts registered with the same phone number as the target account. Use to uncover synthetic identities or multi-account fraud setups. Do not use when only device or payment data is needed. Shared phone numbers show identity overlap but cannot prove unauthorized money flow.",
    input_model=FindSharedPhonesInput,
    handler=queries.find_shared_phones,
    kind="query",
)

register_tool(
    name="detect_rapid_hops",
    description="Detect rapid pass-through transfers where an account forwards >=70% of received funds within minutes. Use to spot high-velocity transit mules. Do not use for long-term layering or dormant accounts. Rapid forwarding is characteristic of mules, but legitimate pass-through services also exhibit this pattern.",
    input_model=DetectRapidHopsInput,
    handler=queries.detect_rapid_hops,
    kind="query",
)

register_tool(
    name="detect_fan_in",
    description="Detect aggregator accounts collecting payments from multiple distinct senders before forwarding. Use to find smurfing collection hubs. Do not use for single-chain fraud investigations. High fan-in suggests funneling activity, but legitimate merchants also receive numerous small incoming payments.",
    input_model=DetectFanInInput,
    handler=queries.detect_fan_in,
    kind="query",
)

register_tool(
    name="detect_fan_out",
    description="Detect an account splitting incoming money into multiple outbound transfers to different recipients. Use to identify layering and distribution nodes. Do not use on terminal cash-out accounts. Fan-out is common in payroll or group settlements, so confirm with transaction timing and paths.",
    input_model=DetectFanOutInput,
    handler=queries.detect_fan_out,
    kind="query",
)

register_tool(
    name="get_neighborhood",
    description="Retrieve the immediate 1- or 2-hop transaction network around an account for local context. Use when visualizing or inspecting adjacent connections. Do not use for end-to-end path discovery. Shows local topology but cannot prove which edges carried stolen money.",
    input_model=GetNeighborhoodInput,
    handler=queries.get_neighborhood,
    kind="query",
)

register_tool(
    name="find_shortest_path",
    description="Find the shortest money transfer path or hybrid device or phone path between two accounts. Use to verify if and how two suspects are connected. Do not use without both source and destination accounts. Proves network reachability, but cannot prove temporal causality of specific stolen amounts.",
    input_model=FindShortestPathInput,
    handler=algorithms.find_shortest_path,
    kind="algorithm",
)

register_tool(
    name="rank_hub_accounts",
    description="Rank accounts by PageRank centrality over transaction flows in a time window. Use to find influential network hubs. Do not use as sole proof of guilt; busy legitimate merchants also rank high, so confirm with get_account_profile. High rank is a hint, not proof.",
    input_model=RankHubAccountsInput,
    handler=algorithms.rank_hub_accounts,
    kind="algorithm",
)

register_tool(
    name="find_connected_components",
    description="Partition the network into weakly connected components based on transactions and shared devices. Use to segment isolated fraud rings across the network. Do not use to trace a specific victim's fund flow. Proves mutual network reachability, but cannot prove every member is complicit.",
    input_model=FindConnectedComponentsInput,
    handler=algorithms.find_connected_components,
    kind="algorithm",
)

register_tool(
    name="find_communities",
    description="Detect tightly-knit clusters of accounts using Louvain community detection on money flow and hardware links. Use to isolate syndicate structures. Do not use when looking for a linear payment chain. Identifies dense clusters, not proof that all accounts in a community are mules.",
    input_model=FindCommunitiesInput,
    handler=algorithms.find_communities,
    kind="algorithm",
)

register_tool(
    name="find_connected_ring",
    description="Extract the full connected component, community, and hardware-sharing links surrounding a specific suspect account. Use to uncover an entire ring once a mule is found. Do not use without a target account. Shows structural ring membership, but cannot determine individual stolen balances held.",
    input_model=FindConnectedRingInput,
    handler=algorithms.find_connected_ring,
    kind="algorithm",
)

register_tool(
    name="rank_chokepoints",
    description="Calculate betweenness centrality within a suspect candidate pool to rank bottlenecks money must flow through. Use to prioritize high-leverage accounts for freezing. Do not use on large uncurated lists. High betweenness shows topological centrality, but cannot verify if money is currently held.",
    input_model=RankChokepointsInput,
    handler=algorithms.rank_chokepoints,
    kind="algorithm",
)


# ===========================================================================
# 4. Phase 11 Action and Memory Tools
# ===========================================================================

def _handle_build_freeze_list(graph, report_id: str, candidate_account_ids: List[str]):
    return freeze.build_freeze_list(
        candidates=candidate_account_ids,
        case_context=report_id,
        graph=graph,
    )


def _handle_save_case_to_memory(graph, report_id: str, summary: str, account_ids: Optional[List[str]] = None):
    return memory.save_case_to_memory(
        graph=graph,
        report_id=report_id,
        summary=summary,
        account_ids=account_ids,
    )


def _handle_recall_past_cases(graph, account_ids: List[str]):
    return memory.recall_past_cases(
        graph=graph,
        account_ids=account_ids,
    )


register_tool(
    name="build_freeze_list",
    description="Assemble and rank a freeze recommendation for human review from verified suspect accounts. Use only after investigating the fraud report and vetting suspects with get_account_profile. Do NOT pass unexamined accounts. Independently re-verifies candidates against the graph money trail and behavioral signals; rejects decoys, accounts without valid trails, and already-emptied accounts.",
    input_model=BuildFreezeListInput,
    handler=_handle_build_freeze_list,
    kind="action",
)

register_tool(
    name="save_case_to_memory",
    description="Persist completed investigation findings to the memory graph. Writes Case node, FLAGGED_IN links, and links to earlier cases via shared infrastructure. Only accounts approved in build_freeze_list can be saved. Use only after obtaining a freeze recommendation. Idempotent.",
    input_model=SaveCaseToMemoryInput,
    handler=_handle_save_case_to_memory,
    kind="action",
)

register_tool(
    name="recall_past_cases",
    description="Retrieve historical fraud cases involving given accounts or their shared devices and phones. Returns earlier case dates, summaries, outcomes, and confidence levels. Use during an investigation to uncover repeat offenders, linked syndicates, or prior intelligence.",
    input_model=RecallPastCasesInput,
    handler=_handle_recall_past_cases,
    kind="query",
)

