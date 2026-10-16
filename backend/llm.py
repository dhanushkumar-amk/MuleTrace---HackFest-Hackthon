"""LLM client and compaction utilities for MuleTrace.

Provides Groq LLM integration with automatic fallback across available models,
and exports the compact_output helper for bounding output tokens.
"""
from __future__ import annotations

import os
from typing import Any, Dict, List, Optional
from dotenv import load_dotenv
from groq import Groq

from backend.tools.compaction import compact_output, TRUNCATION_NOTE

load_dotenv()


def get_llm_api_key() -> str:
    """Retrieve Groq API key from environment."""
    key = os.getenv("LLM_API_KEY") or os.getenv("GROQ_API_KEY")
    if not key:
        raise ValueError("Neither LLM_API_KEY nor GROQ_API_KEY is configured in .env")
    return key


def get_llm_model() -> str:
    """Retrieve configured LLM model name with sensible default."""
    return os.getenv("LLM_MODEL", "openai/gpt-oss-120b")


def get_groq_client() -> Groq:
    """Instantiate and return a Groq API client."""
    return Groq(api_key=get_llm_api_key())


__all__ = [
    "compact_output",
    "TRUNCATION_NOTE",
    "get_groq_client",
    "get_llm_model",
    "get_llm_api_key",
]
