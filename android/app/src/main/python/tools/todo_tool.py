"""Todo Tool for Hermes Android.

Direct port from hermes-agent/tools/todo_tool.py.
No external dependencies - pure Python standard library.

Provides an in-memory todo list per session for task management.
"""

from __future__ import annotations

import json
import logging
from typing import Any, Dict, List, Optional

from tools.registry import registry, tool_error, tool_result

logger = logging.getLogger("hermes.tools.todo")

# ---------------------------------------------------------------------------
# Limits
# ---------------------------------------------------------------------------

MAX_TODO_ITEMS = 256
MAX_TODO_CONTENT_CHARS = 4000

# ---------------------------------------------------------------------------
# TodoStore
# ---------------------------------------------------------------------------

class TodoStore:
    """In-memory todo list for a session."""

    def __init__(self):
        self._items: List[Dict[str, Any]] = []

    def write(self, todos: List[Dict[str, Any]], mode: str = "replace") -> str:
        """Write todo items. Mode: 'replace' or 'merge'."""
        if mode == "replace":
            self._items = []
            for item in todos:
                err = self._validate(item)
                if err:
                    return tool_error(f"Invalid todo item: {err}")
                self._items.append(item)
        elif mode == "merge":
            for item in todos:
                err = self._validate(item)
                if err:
                    return tool_error(f"Invalid todo item: {err}")
                # Update existing or append
                existing = next(
                    (i for i, t in enumerate(self._items) if t.get("id") == item.get("id")),
                    None,
                )
                if existing is not None:
                    self._items[existing] = item
                else:
                    self._items.append(item)
        else:
            return tool_error(f"Unknown mode: {mode}")

        if len(self._items) > MAX_TODO_ITEMS:
            return tool_error(f"Too many todo items (max {MAX_TODO_ITEMS})")

        return tool_result({"count": len(self._items)})

    def read(self) -> List[Dict[str, Any]]:
        """Read all todo items."""
        return list(self._items)

    def has_items(self) -> bool:
        """Check if there are any todo items."""
        return len(self._items) > 0

    def format_for_injection(self) -> str:
        """Format todos for system prompt injection."""
        if not self._items:
            return ""
        lines = ["## Current Todo List"]
        for item in self._items:
            status = item.get("status", "pending")
            content = item.get("content", "")
            tid = item.get("id", "?")
            icon = {"pending": "○", "in_progress": "◐", "completed": "●"}.get(status, "○")
            lines.append(f"{icon} [{tid}] {content} ({status})")
        return "\n".join(lines)

    def _validate(self, item: Dict[str, Any]) -> Optional[str]:
        """Validate a todo item."""
        if not isinstance(item, dict):
            return "must be a dict"
        if "id" not in item:
            return "missing 'id'"
        if "content" not in item:
            return "missing 'content'"
        if "status" not in item:
            return "missing 'status'"
        if item["status"] not in ("pending", "in_progress", "completed"):
            return f"invalid status: {item['status']}"
        self._cap_content(item)
        return None

    @staticmethod
    def _cap_content(item: Dict[str, Any]) -> None:
        """Cap content length."""
        content = item.get("content", "")
        if len(content) > MAX_TODO_CONTENT_CHARS:
            item["content"] = content[:MAX_TODO_CONTENT_CHARS] + "..."


# ---------------------------------------------------------------------------
# Session-based store management
# ---------------------------------------------------------------------------

_todo_stores: Dict[str, TodoStore] = {}


def _get_store(session_id: str) -> TodoStore:
    """Get or create a TodoStore for a session."""
    if session_id not in _todo_stores:
        _todo_stores[session_id] = TodoStore()
    return _todo_stores[session_id]


# ---------------------------------------------------------------------------
# Tool handlers
# ---------------------------------------------------------------------------

def todo_write(session_id: str = "default", todos: list = None, mode: str = "replace") -> str:
    """Write or update the todo list for a session.

    Args:
        session_id: Session identifier
        todos: List of todo items, each with id, content, status
        mode: 'replace' to overwrite, 'merge' to update/add
    """
    if not todos:
        return tool_error("todos list is required")
    store = _get_store(session_id)
    return store.write(todos, mode)


def todo_read(session_id: str = "default") -> str:
    """Read the current todo list for a session.

    Args:
        session_id: Session identifier
    """
    store = _get_store(session_id)
    return tool_result(store.read())


# ---------------------------------------------------------------------------
# Registration
# ---------------------------------------------------------------------------

registry.register(
    name="todo_write",
    handler=todo_write,
    schema={
        "type": "function",
        "function": {
            "name": "todo_write",
            "description": "Write or update the todo list. Each item has id, content, and status (pending/in_progress/completed).",
            "parameters": {
                "type": "object",
                "properties": {
                    "todos": {
                        "type": "array",
                        "description": "List of todo items",
                        "items": {
                            "type": "object",
                            "properties": {
                                "id": {"type": "string", "description": "Unique item ID"},
                                "content": {"type": "string", "description": "Todo content"},
                                "status": {
                                    "type": "string",
                                    "enum": ["pending", "in_progress", "completed"],
                                    "description": "Item status",
                                },
                            },
                            "required": ["id", "content", "status"],
                        },
                    },
                    "mode": {
                        "type": "string",
                        "enum": ["replace", "merge"],
                        "description": "Write mode: replace entire list or merge with existing",
                    },
                },
                "required": ["todos"],
            },
        },
    },
    description="Manage todo list for task tracking",
    emoji="📋",
)

registry.register(
    name="todo_read",
    handler=todo_read,
    schema={
        "type": "function",
        "function": {
            "name": "todo_read",
            "description": "Read the current todo list",
            "parameters": {
                "type": "object",
                "properties": {
                    "session_id": {
                        "type": "string",
                        "description": "Session identifier",
                    },
                },
                "required": [],
            },
        },
    },
    description="Read current todo list",
    emoji="📋",
)
