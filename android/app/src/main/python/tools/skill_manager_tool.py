"""Skill Manager Tool for Hermes Android.

Simplified port from hermes-agent/tools/skill_manager_tool.py.
Removes: skills_guard, write_approval, skill_usage/pinned_guard,
         security_scan, fuzzy_match, path_security, gateway session context.
Keeps: skill_manage() with create/edit/delete/write_file/remove_file,
       validation (name, category, frontmatter, content size, file path),
       atomic writes, directory structure.
"""

from __future__ import annotations

import json
import logging
import os
import re
import shutil
import tempfile
from typing import Any, Dict, Optional

import yaml

from tools.registry import registry, tool_error, tool_result

logger = logging.getLogger("hermes.tools.skill_manager")

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

SKILLS_DIR_NAME = "skills"
SKILL_FILE = "SKILL.md"
ALLOWED_SUBDIRS = {"references", "templates", "scripts", "assets"}
MAX_CONTENT_CHARS = 100_000
NAME_PATTERN = re.compile(r"^[a-z0-9][a-z0-9._-]*$")
VALID_CATEGORIES = {
    "general", "coding", "writing", "analysis", "creative",
    "workflow", "communication", "research", "automation", "custom",
}

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _skills_dir(home: str) -> str:
    return os.path.join(home, SKILLS_DIR_NAME)


def _validate_name(name: str) -> Optional[str]:
    """Validate skill name."""
    if not name:
        return "Name is required"
    if not NAME_PATTERN.match(name):
        return f"Name must match {NAME_PATTERN.pattern}"
    if len(name) > 64:
        return "Name too long (max 64 chars)"
    return None


def _validate_category(category: str) -> Optional[str]:
    """Validate skill category."""
    if not category:
        return None  # Category is optional
    if category not in VALID_CATEGORIES:
        return f"Invalid category. Valid: {', '.join(sorted(VALID_CATEGORIES))}"
    return None


def _validate_frontmatter(frontmatter_str: str) -> Optional[str]:
    """Validate YAML frontmatter."""
    try:
        meta = yaml.safe_load(frontmatter_str)
    except yaml.YAMLError as e:
        return f"Invalid YAML: {e}"

    if not isinstance(meta, dict):
        return "Frontmatter must be a YAML mapping"

    if "name" not in meta:
        return "Frontmatter must include 'name'"

    return None


def _validate_content_size(content: str) -> Optional[str]:
    """Validate content size."""
    if len(content) > MAX_CONTENT_CHARS:
        return f"Content too large ({len(content)} > {MAX_CONTENT_CHARS} chars)"
    return None


def _validate_file_path(file_path: str) -> Optional[str]:
    """Validate that a file path is within allowed subdirectories."""
    parts = file_path.replace("\\", "/").split("/")
    if not parts:
        return "Empty file path"

    first = parts[0]
    if first not in ALLOWED_SUBDIRS:
        return f"File must be in one of: {', '.join(sorted(ALLOWED_SUBDIRS))}"

    if ".." in parts:
        return "Path traversal not allowed"

    return None


def _atomic_write_text(path: str, content: str) -> None:
    """Atomically write text to a file."""
    dir_path = os.path.dirname(path)
    os.makedirs(dir_path, exist_ok=True)
    fd, tmp_path = tempfile.mkstemp(dir=dir_path)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(content)
        os.replace(tmp_path, path)
    except Exception:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
        raise


# ---------------------------------------------------------------------------
# Tool handler
# ---------------------------------------------------------------------------

def skill_manage(
    action: str,
    name: str = "",
    description: str = "",
    category: str = "general",
    content: str = "",
    frontmatter: str = "",
    file: str = "",
    file_content: str = "",
    version: str = "1.0",
    home: str = "",
) -> str:
    """Manage skills: create, edit, delete, write_file, remove_file.

    Args:
        action: Operation to perform
        name: Skill name
        description: Skill description
        category: Skill category
        content: Skill body content (markdown)
        frontmatter: YAML frontmatter string
        file: File path for write_file/remove_file operations
        file_content: File content for write_file operation
        version: Skill version
        home: Hermes home directory
    """
    if not home:
        return tool_error("Home directory not configured")

    sdir = _skills_dir(home)

    # ---- CREATE ----
    if action == "create":
        err = _validate_name(name)
        if err:
            return tool_error(err)

        skill_path = os.path.join(sdir, name)
        if os.path.exists(skill_path):
            return tool_error(f"Skill already exists: {name}")

        err = _validate_category(category)
        if err:
            return tool_error(err)

        if content:
            err = _validate_content_size(content)
            if err:
                return tool_error(err)

        # Build SKILL.md
        fm = {"name": name, "version": version, "category": category}
        if description:
            fm["description"] = description
        if frontmatter:
            try:
                extra = yaml.safe_load(frontmatter)
                if isinstance(extra, dict):
                    fm.update(extra)
            except yaml.YAMLError:
                pass

        fm_str = yaml.dump(fm, default_flow_style=False, allow_unicode=True).strip()
        skill_content = f"---\n{fm_str}\n---\n\n{content}\n"

        try:
            os.makedirs(skill_path, exist_ok=True)
            _atomic_write_text(os.path.join(skill_path, SKILL_FILE), skill_content)
        except Exception as e:
            return tool_error(f"Error creating skill: {e}")

        return tool_result({"action": "create", "name": name, "status": "created"})

    # ---- EDIT ----
    elif action == "edit":
        if not name:
            return tool_error("Skill name is required")

        skill_path = os.path.join(sdir, name)
        if not os.path.isdir(skill_path):
            return tool_error(f"Skill not found: {name}")

        skill_file = os.path.join(skill_path, SKILL_FILE)
        if not os.path.isfile(skill_file):
            return tool_error(f"SKILL.md not found for: {name}")

        # Read existing
        try:
            with open(skill_file, "r", encoding="utf-8") as f:
                existing = f.read()
        except Exception as e:
            return tool_error(f"Error reading skill: {e}")

        # Parse existing frontmatter
        from tools.skills_tool import _parse_frontmatter
        meta, body = _parse_frontmatter(existing)

        # Update fields
        if description:
            meta["description"] = description
        if category:
            meta["category"] = category
        if version:
            meta["version"] = version
        if frontmatter:
            try:
                extra = yaml.safe_load(frontmatter)
                if isinstance(extra, dict):
                    meta.update(extra)
            except yaml.YAMLError:
                pass

        new_body = content if content else body
        if new_body:
            err = _validate_content_size(new_body)
            if err:
                return tool_error(err)

        fm_str = yaml.dump(meta, default_flow_style=False, allow_unicode=True).strip()
        skill_content = f"---\n{fm_str}\n---\n\n{new_body}\n"

        try:
            _atomic_write_text(skill_file, skill_content)
        except Exception as e:
            return tool_error(f"Error saving skill: {e}")

        return tool_result({"action": "edit", "name": name, "status": "updated"})

    # ---- DELETE ----
    elif action == "delete":
        if not name:
            return tool_error("Skill name is required")

        skill_path = os.path.join(sdir, name)

        # Safety: prevent path traversal
        real_sdir = os.path.realpath(sdir)
        real_skill = os.path.realpath(skill_path)
        if not real_skill.startswith(real_sdir):
            return tool_error("Invalid skill name")

        if not os.path.isdir(skill_path):
            return tool_error(f"Skill not found: {name}")

        try:
            shutil.rmtree(skill_path)
        except Exception as e:
            return tool_error(f"Error deleting skill: {e}")

        return tool_result({"action": "delete", "name": name, "status": "deleted"})

    # ---- WRITE FILE ----
    elif action == "write_file":
        if not name:
            return tool_error("Skill name is required")
        if not file:
            return tool_error("File path is required")
        if file_content is None:
            return tool_error("File content is required")

        err = _validate_file_path(file)
        if err:
            return tool_error(err)

        err = _validate_content_size(file_content)
        if err:
            return tool_error(err)

        skill_path = os.path.join(sdir, name)
        if not os.path.isdir(skill_path):
            return tool_error(f"Skill not found: {name}")

        file_path = os.path.join(skill_path, file)

        # Safety: prevent path traversal
        real_skill = os.path.realpath(skill_path)
        real_file = os.path.realpath(file_path)
        if not real_file.startswith(real_skill):
            return tool_error("Invalid file path")

        try:
            _atomic_write_text(file_path, file_content)
        except Exception as e:
            return tool_error(f"Error writing file: {e}")

        return tool_result({"action": "write_file", "name": name, "file": file, "status": "written"})

    # ---- REMOVE FILE ----
    elif action == "remove_file":
        if not name:
            return tool_error("Skill name is required")
        if not file:
            return tool_error("File path is required")

        err = _validate_file_path(file)
        if err:
            return tool_error(err)

        skill_path = os.path.join(sdir, name)
        file_path = os.path.join(skill_path, file)

        # Safety
        real_skill = os.path.realpath(skill_path)
        real_file = os.path.realpath(file_path)
        if not real_file.startswith(real_skill):
            return tool_error("Invalid file path")

        if not os.path.isfile(file_path):
            return tool_error(f"File not found: {file}")

        try:
            os.remove(file_path)
        except Exception as e:
            return tool_error(f"Error removing file: {e}")

        return tool_result({"action": "remove_file", "name": name, "file": file, "status": "removed"})

    else:
        return tool_error(f"Unknown action: {action}. Valid: create, edit, delete, write_file, remove_file")


# ---------------------------------------------------------------------------
# Registration
# ---------------------------------------------------------------------------

registry.register(
    name="skill_manage",
    handler=skill_manage,
    schema={
        "type": "function",
        "function": {
            "name": "skill_manage",
            "description": "Manage skills: create new skills, edit existing ones, delete skills, or manage support files within skills.",
            "parameters": {
                "type": "object",
                "properties": {
                    "action": {
                        "type": "string",
                        "enum": ["create", "edit", "delete", "write_file", "remove_file"],
                        "description": "Operation to perform",
                    },
                    "name": {
                        "type": "string",
                        "description": "Skill name (lowercase alphanumeric, dots, dashes)",
                    },
                    "description": {
                        "type": "string",
                        "description": "Skill description",
                    },
                    "category": {
                        "type": "string",
                        "description": "Skill category",
                    },
                    "content": {
                        "type": "string",
                        "description": "Skill body content (Markdown)",
                    },
                    "frontmatter": {
                        "type": "string",
                        "description": "Extra YAML frontmatter fields",
                    },
                    "file": {
                        "type": "string",
                        "description": "File path (for write_file/remove_file, relative to skill dir)",
                    },
                    "file_content": {
                        "type": "string",
                        "description": "File content (for write_file)",
                    },
                    "version": {
                        "type": "string",
                        "description": "Skill version",
                    },
                },
                "required": ["action", "name"],
            },
        },
    },
    description="Create, edit, delete skills and manage skill files",
    emoji="🎯",
)
