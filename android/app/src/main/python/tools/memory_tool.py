"""Memory Tool for Hermes Android.

Simplified port from hermes-agent/tools/memory_tool.py.
Removes: threat_patterns, write_approval gate, fcntl/msvcrt file locking,
         external drift detection, MemoryProvider interface.
Keeps: MemoryStore with file-based persistence (MEMORY.md / USER.md),
       add/replace/remove/apply_batch, frozen snapshot for system prompts.
"""

from __future__ import annotations

import json
import logging
import os
import tempfile
import threading
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from tools.registry import registry, tool_error, tool_result

logger = logging.getLogger("hermes.tools.memory")

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

ENTRY_DELIMITER = "\n§\n"
MEMORY_CHAR_LIMIT = 2200
USER_CHAR_LIMIT = 1375

# ---------------------------------------------------------------------------
# MemoryStore
# ---------------------------------------------------------------------------

class MemoryStore:
    """File-based memory store using MEMORY.md and USER.md.

    Each file stores entries separated by '§' delimiter.
    A frozen snapshot is maintained for fast system-prompt injection.
    """

    def __init__(self, home_dir: str):
        self._home = home_dir
        self._memory_path = os.path.join(home_dir, "MEMORY.md")
        self._user_path = os.path.join(home_dir, "USER.md")

        # Live entries (mutable)
        self._memory_entries: List[str] = []
        self._user_entries: List[str] = []

        # Frozen snapshot (immutable, used for system prompts)
        self._memory_frozen: List[str] = []
        self._user_frozen: List[str] = []

        self._lock = threading.Lock()

        # Load from disk on init
        self.load_from_disk()

    # ---- Public API ----

    def add(self, entry: str, category: str = "memory") -> str:
        """Add a new entry to memory or user profile."""
        if not entry.strip():
            return tool_error("Empty entry")

        with self._lock:
            if category == "user":
                if sum(len(e) for e in self._user_entries) + len(entry) > USER_CHAR_LIMIT * 2:
                    self._user_entries = self._user_entries[-10:]  # Keep last 10
                self._user_entries.append(entry.strip())
                self._save_to_disk("user")
            else:
                if sum(len(e) for e in self._memory_entries) + len(entry) > MEMORY_CHAR_LIMIT * 2:
                    self._memory_entries = self._memory_entries[-20:]  # Keep last 20
                self._memory_entries.append(entry.strip())
                self._save_to_disk("memory")

        return tool_result({"added": entry[:100], "category": category})

    def replace(self, old: str, new: str, category: str = "memory") -> str:
        """Replace an entry that contains 'old' with 'new'."""
        if not old.strip():
            return tool_error("Old entry text is required")

        with self._lock:
            entries = self._user_entries if category == "user" else self._memory_entries
            found = False
            for i, entry in enumerate(entries):
                if old in entry:
                    entries[i] = new.strip()
                    found = True
                    break

            if not found:
                return tool_error(f"Entry not found for replacement in {category}")

            self._save_to_disk(category)

        return tool_result({"replaced": old[:50], "with": new[:50], "category": category})

    def remove(self, entry: str, category: str = "memory") -> str:
        """Remove an entry that contains the given text."""
        if not entry.strip():
            return tool_error("Entry text is required")

        with self._lock:
            entries = self._user_entries if category == "user" else self._memory_entries
            original_len = len(entries)
            entries[:] = [e for e in entries if entry not in e]

            if len(entries) == original_len:
                return tool_error(f"Entry not found for removal in {category}")

            self._save_to_disk(category)

        return tool_result({"removed": entry[:50], "category": category})

    def apply_batch(self, operations: List[Dict[str, str]], category: str = "memory") -> str:
        """Apply multiple memory operations atomically."""
        results = []
        with self._lock:
            for op in operations:
                action = op.get("action")
                if action == "add":
                    r = self.add(op.get("entry", ""), category)
                elif action == "replace":
                    r = self.replace(op.get("old", ""), op.get("new", ""), category)
                elif action == "remove":
                    r = self.remove(op.get("entry", ""), category)
                else:
                    r = tool_error(f"Unknown action: {action}")
                results.append(r)

        return tool_result({"batch_results": results, "count": len(results)})

    def load_from_disk(self) -> None:
        """Load entries from disk and create frozen snapshot."""
        with self._lock:
            self._memory_entries = self._read_file(self._memory_path)
            self._user_entries = self._read_file(self._user_path)

            # Create frozen snapshots
            self._memory_frozen = list(self._memory_entries)
            self._user_frozen = list(self._user_entries)

        logger.info(f"Loaded memory: {len(self._memory_entries)} entries, "
                     f"user: {len(self._user_entries)} entries")

    def format_for_system_prompt(self) -> str:
        """Return frozen snapshot formatted for system prompt injection."""
        parts = []
        if self._memory_frozen:
            parts.append("## Memory")
            for entry in self._memory_frozen:
                parts.append(f"- {entry}")
        if self._user_frozen:
            parts.append("## User Profile")
            for entry in self._user_frozen:
                parts.append(f"- {entry}")
        return "\n".join(parts)

    def get_all(self) -> Dict[str, List[str]]:
        """Return all current entries."""
        with self._lock:
            return {
                "memory": list(self._memory_entries),
                "user": list(self._user_entries),
            }

    # ---- Internal ----

    def _read_file(self, path: str) -> List[str]:
        """Read entries from a file."""
        try:
            with open(path, "r", encoding="utf-8") as f:
                content = f.read().strip()
            if not content:
                return []
            entries = content.split(ENTRY_DELIMITER)
            return [e.strip() for e in entries if e.strip()]
        except FileNotFoundError:
            return []
        except Exception as e:
            logger.error(f"Error reading {path}: {e}")
            return []

    def _save_to_disk(self, category: str) -> None:
        """Atomically save entries to disk."""
        if category == "user":
            path = self._user_path
            entries = self._user_entries
        else:
            path = self._memory_path
            entries = self._memory_entries

        content = ENTRY_DELIMITER.join(entries)
        if not content:
            content = ""

        try:
            dir_path = os.path.dirname(path)
            os.makedirs(dir_path, exist_ok=True)
            # Atomic write via temp file
            fd, tmp_path = tempfile.mkstemp(dir=dir_path, suffix=".md")
            try:
                with os.fdopen(fd, "w", encoding="utf-8") as f:
                    f.write(content)
                os.replace(tmp_path, path)
            except Exception:
                os.unlink(tmp_path)
                raise
            # Update frozen snapshot
            if category == "user":
                self._user_frozen = list(entries)
            else:
                self._memory_frozen = list(entries)
        except Exception as e:
            logger.error(f"Error saving {path}: {e}")


# ---------------------------------------------------------------------------
# Global instance (initialized by hermes_server)
# ---------------------------------------------------------------------------

_memory_store: Optional[MemoryStore] = None


def init_memory(home_dir: str) -> MemoryStore:
    """Initialize the global MemoryStore."""
    global _memory_store
    _memory_store = MemoryStore(home_dir)
    return _memory_store


def get_memory_store() -> Optional[MemoryStore]:
    """Get the global MemoryStore instance."""
    return _memory_store


# ---------------------------------------------------------------------------
# Tool handlers
# ---------------------------------------------------------------------------

def memory_add(entry: str, category: str = "memory") -> str:
    """Add a new memory entry."""
    if not _memory_store:
        return tool_error("Memory system not initialized")
    return _memory_store.add(entry, category)


def memory_replace(old: str, new: str, category: str = "memory") -> str:
    """Replace an existing memory entry."""
    if not _memory_store:
        return tool_error("Memory system not initialized")
    return _memory_store.replace(old, new, category)


def memory_remove(entry: str, category: str = "memory") -> str:
    """Remove a memory entry."""
    if not _memory_store:
        return tool_error("Memory system not initialized")
    return _memory_store.remove(entry, category)


# ---------------------------------------------------------------------------
# Registration
# ---------------------------------------------------------------------------

registry.register(
    name="memory_add",
    handler=memory_add,
    schema={
        "type": "function",
        "function": {
            "name": "memory_add",
            "description": "Add a new entry to the AI's memory. Use 'memory' category for general facts, 'user' for user preferences/profile info.",
            "parameters": {
                "type": "object",
                "properties": {
                    "entry": {
                        "type": "string",
                        "description": "The memory entry to add",
                    },
                    "category": {
                        "type": "string",
                        "enum": ["memory", "user"],
                        "description": "Memory category: 'memory' for general facts, 'user' for user profile",
                    },
                },
                "required": ["entry"],
            },
        },
    },
    description="Add a memory entry for persistent knowledge",
    emoji="🧠",
)

registry.register(
    name="memory_replace",
    handler=memory_replace,
    schema={
        "type": "function",
        "function": {
            "name": "memory_replace",
            "description": "Replace an existing memory entry that contains the old text with new text.",
            "parameters": {
                "type": "object",
                "properties": {
                    "old": {
                        "type": "string",
                        "description": "Text to find in existing entries",
                    },
                    "new": {
                        "type": "string",
                        "description": "Replacement text",
                    },
                    "category": {
                        "type": "string",
                        "enum": ["memory", "user"],
                        "description": "Memory category",
                    },
                },
                "required": ["old", "new"],
            },
        },
    },
    description="Replace a memory entry",
    emoji="🧠",
)

registry.register(
    name="memory_remove",
    handler=memory_remove,
    schema={
        "type": "function",
        "function": {
            "name": "memory_remove",
            "description": "Remove a memory entry that contains the given text.",
            "parameters": {
                "type": "object",
                "properties": {
                    "entry": {
                        "type": "string",
                        "description": "Text to find and remove from memory",
                    },
                    "category": {
                        "type": "string",
                        "enum": ["memory", "user"],
                        "description": "Memory category",
                    },
                },
                "required": ["entry"],
            },
        },
    },
    description="Remove a memory entry",
    emoji="🧠",
)
