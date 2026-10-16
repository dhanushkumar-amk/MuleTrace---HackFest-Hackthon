"""MuleTrace FastMCP server module (Phase 9).

Exposes all 17 registered graph tools via Model Context Protocol (MCP).
Supports two transports:
1. stdio: default (python -m backend.mcp_server)
2. streamable HTTP: port 8765 (python -m backend.mcp_server --http)

Safety and protocol constraints:
- In stdio mode, standard output is reserved strictly for JSON-RPC MCP messages.
  All application logging directs exclusively to stderr.
- Tools are strictly read-only against the graph.
"""
from __future__ import annotations

import argparse
import inspect
import logging
import sys
from typing import Any, Callable, Dict, List
from mcp.server.mcpserver import MCPServer

from backend.tools.registry import ToolDefinition, list_tools

# FastMCP alias for compatibility across MCP SDK v1 and v2
FastMCP = MCPServer

# Direct all standard logging strictly to stderr to keep stdout pure for JSON-RPC
logging.basicConfig(
    stream=sys.stderr,
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("muletrace_mcp")


def _build_mcp_callable(tool_def: ToolDefinition) -> Callable[..., Any]:
    """Dynamically build an async tool function preserving type signatures and schema."""
    model_cls = tool_def.input_model
    params: List[inspect.Parameter] = []
    annotations: Dict[str, Any] = {}

    for name, field in model_cls.model_fields.items():
        default = field.default if field.default is not ... else inspect.Parameter.empty
        param = inspect.Parameter(
            name,
            inspect.Parameter.POSITIONAL_OR_KEYWORD,
            default=default,
            annotation=field.annotation,
        )
        params.append(param)
        annotations[name] = field.annotation

    annotations["return"] = dict

    async def tool_runner(*args: Any, **kwargs: Any) -> Dict[str, Any]:
        bound = sig.bind(*args, **kwargs)
        bound.apply_defaults()
        return tool_def.execute(**bound.arguments)

    sig = inspect.Signature(parameters=params, return_annotation=dict)
    tool_runner.__signature__ = sig  # type: ignore[attr-defined]
    tool_runner.__annotations__ = annotations
    tool_runner.__name__ = tool_def.name
    tool_runner.__doc__ = tool_def.description

    return tool_runner


def create_server() -> MCPServer:
    """Create and configure the MuleTrace MCP server with all registered tools."""
    srv = MCPServer("muletrace")
    for tool_def in list_tools():
        tool_fn = _build_mcp_callable(tool_def)
        srv.add_tool(
            fn=tool_fn,
            name=tool_def.name,
            description=tool_def.description,
        )
    return srv


# Global server instance for in-process access
server = create_server()


def main() -> None:
    """CLI entrypoint supporting stdio and streamable HTTP transports."""
    parser = argparse.ArgumentParser(description="MuleTrace Model Context Protocol (MCP) Server")
    parser.add_argument(
        "--http",
        action="store_true",
        help="Run streamable HTTP transport on port 8765 (default: stdio)",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=8765,
        help="Port for streamable HTTP transport (default: 8765)",
    )
    parser.add_argument(
        "--host",
        type=str,
        default="127.0.0.1",
        help="Host for streamable HTTP transport (default: 127.0.0.1)",
    )
    args = parser.parse_args()

    if args.http:
        logger.info("Starting MuleTrace MCP server on streamable HTTP http://%s:%d/mcp", args.host, args.port)
        server.run(transport="streamable-http", host=args.host, port=args.port)
    else:
        logger.info("Starting MuleTrace MCP server on stdio transport")
        server.run(transport="stdio")


if __name__ == "__main__":
    main()
