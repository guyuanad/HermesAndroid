"""Simplified Tool Registry for Hermes Android.

Adapted from hermes-agent/tools/registry.py.
Removes: MCP support, AST-based discovery, generation counter caching,
         check_fn TTL, toolset requirements, async bridging.
Keeps: Core ToolEntry/ToolRegistry, tool_error/tool_result helpers,
       OpenAI-format schema generation, dispatch.
"""

from __future__ import annotations

import asyncio
import json
import logging
import threading
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger("hermes.tools")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def tool_error(msg: str) -> str:
    """Return a JSON error string for tool results."""
    return json.dumps({"error": msg}, ensure_ascii=False)


def tool_result(data: Any) -> str:
    """Return a JSON result string for tool results."""
    return json.dumps({"result": data}, ensure_ascii=False)


# ---------------------------------------------------------------------------
# ToolEntry
# ---------------------------------------------------------------------------

class ToolEntry:
    """Represents a registered tool."""
    __slots__ = (
        "name", "schema", "handler", "description", "emoji",
    )

    def __init__(
        self,
        name: str,
        schema: dict,
        handler: Callable,
        description: str = "",
        emoji: str = "",
    ):
        self.name = name
        self.schema = schema
        self.handler = handler
        self.description = description
        self.emoji = emoji


# ---------------------------------------------------------------------------
# ToolRegistry
# ---------------------------------------------------------------------------

class ToolRegistry:
    """Thread-safe tool registry for Hermes Android."""

    def __init__(self):
        self._tools: Dict[str, ToolEntry] = {}
        self._lock = threading.RLock()

    def register(
        self,
        name: str,
        handler: Callable,
        schema: Optional[dict] = None,
        description: str = "",
        emoji: str = "",
    ) -> None:
        """Register a tool."""
        with self._lock:
            if schema is None:
                schema = {"type": "function", "function": {"name": name, "parameters": {}}}
            self._tools[name] = ToolEntry(
                name=name,
                schema=schema,
                handler=handler,
                description=description,
                emoji=emoji,
            )
            logger.info(f"Registered tool: {name}")

    def deregister(self, name: str) -> None:
        """Remove a tool from the registry."""
        with self._lock:
            self._tools.pop(name, None)

    def get_entry(self, name: str) -> Optional[ToolEntry]:
        """Get a tool entry by name."""
        with self._lock:
            return self._tools.get(name)

    def get_all_tool_names(self) -> List[str]:
        """Return all registered tool names."""
        with self._lock:
            return list(self._tools.keys())

    def get_definitions(self) -> List[dict]:
        """Return OpenAI-format tool schemas for all registered tools."""
        with self._lock:
            return [entry.schema for entry in self._tools.values()]

    def get_schema(self, name: str) -> Optional[dict]:
        """Return the schema for a specific tool."""
        entry = self.get_entry(name)
        return entry.schema if entry else None

    def dispatch(self, name: str, arguments: dict) -> str:
        """Execute a tool handler with the given arguments.

        Returns the tool result as a JSON string.
        Handles both sync and async handlers.
        """
        entry = self.get_entry(name)
        if not entry:
            return tool_error(f"Unknown tool: {name}")

        try:
            result = entry.handler(**arguments)
            # If the handler is async, run it in an event loop
            if asyncio.iscoroutine(result):
                try:
                    loop = asyncio.get_running_loop()
                    # We're already in an async context, schedule it
                    import concurrent.futures
                    with concurrent.futures.ThreadPoolExecutor() as pool:
                        result = pool.submit(asyncio.run, result).result()
                except RuntimeError:
                    # No running loop, safe to use asyncio.run
                    result = asyncio.run(result)

            if isinstance(result, str):
                return result
            return tool_result(result)
        except Exception as e:
            logger.error(f"Tool {name} failed: {e}", exc_info=True)
            return tool_error(f"Tool {name} failed: {e}")


# Global singleton
registry = ToolRegistry()
