"""MuleTrace MCP client bridge (Phase 9).

Async client class that connects to the MuleTrace MCP server (in-process, stdio,
or streamable HTTP, selectable via env var MCP_MODE).
Exposes:
- list_tools(): converts MCP tools into OpenAI/Groq function-calling schema.
- call_tool(name, arguments): calls a tool by name and returns parsed JSON dict.

Phase 10's agent interacts with the tool layer exclusively through this class.
"""
from __future__ import annotations

import json
import os
import sys
from typing import Any, Dict, List, Optional
from contextlib import AsyncExitStack

from mcp.client.session import ClientSession
from mcp.client.stdio import StdioServerParameters, stdio_client
from mcp.client.streamable_http import streamable_http_client

from backend.mcp_server import server as in_process_server


class MuleTraceMCPClient:
    """Async bridge connecting agents to the MuleTrace MCP server."""

    def __init__(
        self,
        mode: Optional[str] = None,
        http_url: str = "http://127.0.0.1:8765/mcp",
    ):
        # Modes: "in-process" (default, fastest), "stdio", "http"
        self.mode = mode or os.getenv("MCP_MODE", "in-process").lower()
        self.http_url = http_url
        self._exit_stack: Optional[AsyncExitStack] = None
        self._session: Optional[ClientSession] = None
        self._cached_openai_tools: Optional[List[Dict[str, Any]]] = None

    async def connect(self) -> "MuleTraceMCPClient":
        """Establish connection to the MCP server based on configured transport mode."""
        if self.mode == "in-process":
            # Direct in-process execution using FastMCP server instance
            return self

        self._exit_stack = AsyncExitStack()

        if self.mode == "stdio":
            server_params = StdioServerParameters(
                command=sys.executable,
                args=["-m", "backend.mcp_server"],
                env=dict(os.environ),
            )
            read_stream, write_stream = await self._exit_stack.enter_async_context(
                stdio_client(server_params)
            )
            self._session = await self._exit_stack.enter_async_context(
                ClientSession(read_stream, write_stream)
            )
            await self._session.initialize()
            return self

        elif self.mode in ("http", "streamable-http"):
            read_stream, write_stream = await self._exit_stack.enter_async_context(
                streamable_http_client(self.http_url)
            )
            self._session = await self._exit_stack.enter_async_context(
                ClientSession(read_stream, write_stream)
            )
            await self._session.initialize()
            return self

        else:
            raise ValueError(f"Unknown MCP_MODE: '{self.mode}'. Expected 'in-process', 'stdio', or 'http'.")

    async def close(self) -> None:
        """Close external MCP sessions and child process resources."""
        if self._exit_stack is not None:
            await self._exit_stack.aclose()
            self._exit_stack = None
            self._session = None

    async def __aenter__(self) -> "MuleTraceMCPClient":
        return await self.connect()

    async def __aexit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        await self.close()

    async def list_tools(self) -> List[Dict[str, Any]]:
        """List registered tools converted to OpenAI-style function-calling format for Groq."""
        if self._cached_openai_tools is not None:
            return self._cached_openai_tools

        if self.mode == "in-process":
            tools_data = await in_process_server.list_tools()
        else:
            if not self._session:
                await self.connect()
            assert self._session is not None
            response = await self._session.list_tools()
            tools_data = response.tools

        openai_tools: List[Dict[str, Any]] = []
        for t in tools_data:
            schema = t.input_schema if hasattr(t, "input_schema") else getattr(t, "inputSchema", {})
            # Ensure schema is valid JSON Schema object
            if not isinstance(schema, dict) or schema.get("type") != "object":
                schema = {"type": "object", "properties": {}}

            openai_tools.append({
                "type": "function",
                "function": {
                    "name": t.name,
                    "description": t.description or "",
                    "parameters": schema,
                },
            })

        self._cached_openai_tools = openai_tools
        return openai_tools

    async def call_tool(self, name: str, arguments: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Invoke a tool by name with arguments and return the parsed result dict."""
        args = arguments or {}

        try:
            if self.mode == "in-process":
                result = await in_process_server.call_tool(name, args)
            else:
                if not self._session:
                    await self.connect()
                assert self._session is not None
                result = await self._session.call_tool(name, args)

            # Unpack CallToolResult content
            if hasattr(result, "content") and result.content:
                for content_part in result.content:
                    if hasattr(content_part, "text") and content_part.text:
                        try:
                            parsed = json.loads(content_part.text)
                            if isinstance(parsed, dict):
                                return parsed
                            return {"result": parsed}
                        except Exception:
                            return {"result": content_part.text}

            # Check if structured_content is available
            if hasattr(result, "structured_content") and isinstance(result.structured_content, dict):
                return result.structured_content

            return {"result": str(result)}

        except Exception as exc:
            return {
                "error": f"MCP tool call '{name}' failed: {str(exc)}",
                "hint": "Verify argument keys and values against the tool schema.",
            }
