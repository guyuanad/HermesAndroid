"""Simplified File Tools for Hermes Android.

Provides basic file read/write/list capabilities for the Android app.
Operates within the Hermes home directory for safety.

Adapted from hermes-agent/tools/file_tools.py.
Removes: binary detection, fuzzy match, path_security, file_safety,
         redaction, terminal integration, Docker support, patch operations.
Keeps: Basic read_file, write_file, list_files with path safety.
"""

from __future__ import annotations

import json
import logging
import os
import tempfile
from typing import Any, Dict, List, Optional

from tools.registry import registry, tool_error, tool_result

logger = logging.getLogger("hermes.tools.file")

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

MAX_READ_CHARS = 50000
MAX_WRITE_CHARS = 100000
ALLOWED_EXTENSIONS = {
    ".txt", ".md", ".json", ".yaml", ".yml", ".py", ".js", ".ts", ".tsx",
    ".jsx", ".html", ".css", ".xml", ".csv", ".log", ".cfg", ".ini",
    ".toml", ".env", ".sh", ".bash", ".zsh", ".gitignore", ".dockerignore",
    ".properties", ".conf", ".rst", ".sql", ".java", ".kt", ".swift",
    ".c", ".cpp", ".h", ".hpp", ".rs", ".go", ".rb", ".php", ".lua",
    ".vim", ".el", ".clj", ".hs", ".scala", ".r", ".m", ".tex",
}

# ---------------------------------------------------------------------------
# Home directory (set by hermes_server)
# ---------------------------------------------------------------------------

_hermes_home: str = ""


def set_home(home: str) -> None:
    """Set the Hermes home directory."""
    global _hermes_home
    _hermes_home = home


def _resolve_path(path: str) -> Optional[str]:
    """Resolve and validate a file path within allowed directories.

    Returns the resolved absolute path or None if invalid.
    """
    if not path:
        return None

    # Expand user home
    if path.startswith("~"):
        path = os.path.expanduser(path)

    # Make absolute
    if not os.path.isabs(path):
        path = os.path.join(_hermes_home, path)

    # Resolve to absolute path
    resolved = os.path.abspath(path)

    # Allow paths within hermes home or temp directories
    allowed_roots = [_hermes_home, tempfile.gettempdir()]
    if not any(resolved.startswith(root) for root in allowed_roots if root):
        return None

    # Check for path traversal
    if ".." in path.split(os.sep):
        real_path = os.path.realpath(path)
        if not any(real_path.startswith(root) for root in allowed_roots if root):
            return None

    return resolved


def _is_text_file(path: str) -> bool:
    """Check if a file is likely a text file based on extension."""
    _, ext = os.path.splitext(path)
    return ext.lower() in ALLOWED_EXTENSIONS or ext == ""


# ---------------------------------------------------------------------------
# Tool handlers
# ---------------------------------------------------------------------------

def read_file(path: str, offset: int = 0, limit: int = 1000) -> str:
    """Read the contents of a text file.

    Args:
        path: File path (relative to Hermes home or absolute)
        offset: Line number to start reading from (1-based)
        limit: Maximum number of lines to read
    """
    resolved = _resolve_path(path)
    if not resolved:
        return tool_error(f"Access denied: path outside allowed directories")

    if not os.path.isfile(resolved):
        return tool_error(f"File not found: {path}")

    if not _is_text_file(resolved):
        return tool_error(f"Unsupported file type. Allowed: {', '.join(sorted(ALLOWED_EXTENSIONS))}")

    try:
        with open(resolved, "r", encoding="utf-8", errors="replace") as f:
            lines = f.readlines()

        # Apply offset and limit
        start = max(0, offset - 1) if offset > 0 else 0
        end = start + limit if limit > 0 else len(lines)
        selected = lines[start:end]

        content = "".join(selected)
        if len(content) > MAX_READ_CHARS:
            content = content[:MAX_READ_CHARS] + f"\n... (truncated, {len(content) - MAX_READ_CHARS} more chars)"

        return tool_result({
            "path": path,
            "content": content,
            "total_lines": len(lines),
            "shown_lines": f"{start + 1}-{min(end, len(lines))}",
        })

    except Exception as e:
        return tool_error(f"Error reading file: {e}")


def write_file(path: str, content: str) -> str:
    """Write content to a text file. Creates the file if it doesn't exist.

    Args:
        path: File path (relative to Hermes home or absolute)
        content: Content to write
    """
    if len(content) > MAX_WRITE_CHARS:
        return tool_error(f"Content too large ({len(content)} > {MAX_WRITE_CHARS} chars)")

    resolved = _resolve_path(path)
    if not resolved:
        return tool_error(f"Access denied: path outside allowed directories")

    try:
        dir_path = os.path.dirname(resolved)
        os.makedirs(dir_path, exist_ok=True)

        # Atomic write
        fd, tmp_path = tempfile.mkstemp(dir=dir_path, suffix=".tmp")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                f.write(content)
            os.replace(tmp_path, resolved)
        except Exception:
            try:
                os.unlink(tmp_path)
            except OSError:
                pass
            raise

        return tool_result({
            "path": path,
            "bytes_written": len(content.encode("utf-8")),
            "status": "written",
        })

    except Exception as e:
        return tool_error(f"Error writing file: {e}")


def list_files(path: str = "", pattern: str = "") -> str:
    """List files in a directory.

    Args:
        path: Directory path (relative to Hermes home or absolute, default: home)
        pattern: Optional glob pattern to filter files (e.g., "*.md", "*.py")
    """
    if not path:
        path = _hermes_home

    resolved = _resolve_path(path)
    if not resolved:
        return tool_error(f"Access denied: path outside allowed directories")

    if not os.path.isdir(resolved):
        return tool_error(f"Directory not found: {path}")

    try:
        entries = []
        for entry in sorted(os.listdir(resolved)):
            # Skip hidden files
            if entry.startswith("."):
                continue

            full_path = os.path.join(resolved, entry)
            is_dir = os.path.isdir(full_path)

            # Apply pattern filter
            if pattern and is_dir:
                continue  # Don't filter out dirs
            if pattern:
                import fnmatch
                if not fnmatch.fnmatch(entry, pattern):
                    continue

            stat = os.stat(full_path) if not is_dir else None
            entries.append({
                "name": entry,
                "type": "directory" if is_dir else "file",
                "size": stat.st_size if stat else 0,
            })

        return tool_result({
            "path": path,
            "entries": entries,
            "count": len(entries),
        })

    except Exception as e:
        return tool_error(f"Error listing directory: {e}")


# ---------------------------------------------------------------------------
# Registration
# ---------------------------------------------------------------------------

registry.register(
    name="read_file",
    handler=read_file,
    schema={
        "type": "function",
        "function": {
            "name": "read_file",
            "description": "Read the contents of a text file. Can read files within the Hermes home directory.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "File path (relative to Hermes home or absolute)",
                    },
                    "offset": {
                        "type": "integer",
                        "description": "Line number to start reading from (1-based, default: 1)",
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Maximum number of lines to read (default: 1000)",
                    },
                },
                "required": ["path"],
            },
        },
    },
    description="Read a text file's contents",
    emoji="📄",
)

registry.register(
    name="write_file",
    handler=write_file,
    schema={
        "type": "function",
        "function": {
            "name": "write_file",
            "description": "Write content to a text file. Creates the file and parent directories if needed.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "File path (relative to Hermes home or absolute)",
                    },
                    "content": {
                        "type": "string",
                        "description": "Content to write to the file",
                    },
                },
                "required": ["path", "content"],
            },
        },
    },
    description="Write content to a file",
    emoji="📝",
)

registry.register(
    name="list_files",
    handler=list_files,
    schema={
        "type": "function",
        "function": {
            "name": "list_files",
            "description": "List files and directories in a given path. Shows file sizes and types.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "Directory path (default: Hermes home directory)",
                    },
                    "pattern": {
                        "type": "string",
                        "description": "Optional glob pattern to filter files (e.g. '*.md', '*.py')",
                    },
                },
                "required": [],
            },
        },
    },
    description="List files in a directory",
    emoji="📂",
)
