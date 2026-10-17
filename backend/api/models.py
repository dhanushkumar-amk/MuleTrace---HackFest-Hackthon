"""Pydantic request and response schemas for MuleTrace API (Phase 13).

Strict validation, standard error shapes, zero hardcoded IDs.
"""
from __future__ import annotations

import re
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field, field_validator


SAFE_ID_PATTERN = re.compile(r"^[A-Za-z0-9_\-]+$")


def validate_id_str(v: str) -> str:
    if not v or not SAFE_ID_PATTERN.match(v) or ".." in v:
        raise ValueError("Identifier must contain only letters, numbers, underscores, and hyphens.")
    return v


class ErrorResponse(BaseModel):
    error: str = Field(..., description="High-level error explanation.")
    hint: str = Field(..., description="Actionable suggestion to resolve the error.")


class HealthResponse(BaseModel):
    status: str = "ok"
    falkordb_reachable: bool
    groq_key_present: bool
    mcp_mode: str
    graph_node_count: int = 0
    graph_nodes_count: int = 0
    saved_cases_count: int = 0


class ReportItem(BaseModel):
    id: str
    victim_account: str
    amount: int
    reported_at: int
    description: str


class CaseSummaryItem(BaseModel):
    session_id: str
    report_id: str
    case_id: Optional[str] = ""
    victim_name: Optional[str] = ""
    total_recoverable: int = 0
    recoverable_total: int = 0
    verified: bool = False
    created_at: int = 0
    timestamp: int = 0
    status: str = "COMPLETED"
    file: Optional[str] = ""


class ToolItem(BaseModel):
    name: str
    kind: str
    short_description: str


class InvestigationStartRequest(BaseModel):
    report_id: Optional[str] = Field(default="FR_0001", description="Fraud report ID to investigate.")
    task: Optional[str] = Field(default=None, description="Optional natural language query.")
    save_memory: bool = Field(default=False, description="Whether to persist findings to long-term memory graph.")
    polish: bool = Field(default=False, description="Whether to run optional Groq summary polish.")
    mode: Optional[str] = Field(default=None, description="Execution mode: 'live' or 'replay'.")
    speed: float = Field(default=1.0, ge=0.0, description="Replay speed multiplier (e.g. 1.0 = normal, 0.0 = instant).")

    @field_validator("report_id")
    @classmethod
    def check_report_id(cls, v: Optional[str]) -> Optional[str]:
        if v is not None:
            return validate_id_str(v)
        return v


class InvestigationStartResponse(BaseModel):
    session_id: str
    status: str = "running"
    mode: str = "live"
    replay: bool = False
    fallback_available: bool = False


class InvestigationStatusResponse(BaseModel):
    session_id: str
    status: str
    mode: str = "live"
    replay: bool = False
    verified: bool = False
    case: Optional[Dict[str, Any]] = None
    explanation: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    fallback_available: bool = False
    disclaimer: str = "recommendation for human review, nothing was frozen"


class AccountProfileResponse(BaseModel):
    account_id: str
    holder_name: Optional[str] = None
    bank: Optional[str] = None
    balance_held: int = 0
    inflow_total: int = 0
    outflow_total: int = 0
    distinct_senders: int = 0
    distinct_receivers: int = 0
    shared_devices_count: int = 0
    shared_phones_count: int = 0
    is_flagged: bool = False
    risk_score: float = 0.0
