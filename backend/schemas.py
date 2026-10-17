"""Typed schemas for MuleTrace agent results and freeze lists (Phase 11)."""
from __future__ import annotations

from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class FreezeItem(BaseModel):
    priority: int = Field(..., description="Rank priority (1..N).")
    account: str = Field(..., description="Target account ID.")
    bank: str = Field(..., description="Account issuing bank.")
    amount_recoverable: int = Field(..., description="Balance currently held in rupees.")
    amount_already_cashed_out: int = Field(default=0, description="Amount already exited downstream.")
    signals: List[str] = Field(default_factory=list, description="Independent risk signals observed.")
    confidence: str = Field(..., description="Confidence assessment (high, medium, low).")
    path: List[str] = Field(default_factory=list, description="Ordered account IDs from victim to target.")
    edge_facts: List[Dict[str, Any]] = Field(default_factory=list, description="Detailed hop facts.")
    hops: int = Field(..., description="Number of hops from victim.")
    path_text: str = Field(..., description="Human-readable path string (e.g. 'Ravi -> A -> B').")
    reason: str = Field(..., description="Factual justification for freezing.")
    evidence_call_ids: List[str] = Field(default_factory=list, description="Tools verifying evidence.")


class NotRecommendedItem(BaseModel):
    account: str
    why: str


class InvestigationResult(BaseModel):
    session_id: str = Field(default="", description="Unique investigation trace session ID.")
    report_id: str
    summary: str
    recommendation_only: bool = True
    freeze_list: List[Dict[str, Any]] = Field(default_factory=list)
    not_recommended: List[Dict[str, Any]] = Field(default_factory=list)
    past_cases: List[Dict[str, Any]] = Field(default_factory=list)
    memory_saved: bool = False
    total_recoverable: int = 0
    total_cashed_out: int = 0
    steps_taken: int = 0
    claims_removed: int = 0
    llm_time_seconds: float = 0.0
    tool_time_seconds: float = 0.0
    total_time_seconds: float = 0.0
