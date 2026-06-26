"""Skills Tool for Hermes Android.

Simplified port from hermes-agent/tools/skills_tool.py.
Removes: plugin system, skill preprocessing, usage stats, security scanning,
         path_security, fuzzy_match, gateway session context.
Keeps: SKILL.md YAML frontmatter parsing, skills_list(), skill_view(),
       skill directory structure.
"""

from __future__ import annotations

import json
import logging
import os
import re
from typing import Any, Dict, List, Optional

import yaml

from tools.registry import registry, tool_error, tool_result

logger = logging.getLogger("hermes.tools.skills")

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

SKILLS_DIR_NAME = "skills"
SKILL_FILE = "SKILL.md"
ALLOWED_SUBDIRS = {"references", "templates", "scripts", "assets"}

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _skills_dir(home: str) -> str:
    """Get the skills directory path."""
    return os.path.join(home, SKILLS_DIR_NAME)


def _parse_frontmatter(content: str) -> tuple:
    """Parse YAML frontmatter from SKILL.md content.

    Returns (metadata_dict, body_text).
    """
    if not content.startswith("---"):
        return {}, content

    parts = content.split("---", 2)
    if len(parts) < 3:
        return {}, content

    try:
        meta = yaml.safe_load(parts[1]) or {}
    except yaml.YAMLError:
        meta = {}

    body = parts[2].strip()
    return meta, body


def _load_skill_metadata(skill_dir: str) -> Optional[Dict[str, Any]]:
    """Load and parse a skill's SKILL.md metadata."""
    skill_file = os.path.join(skill_dir, SKILL_FILE)
    if not os.path.isfile(skill_file):
        return None

    try:
        with open(skill_file, "r", encoding="utf-8") as f:
            content = f.read()
    except Exception as e:
        logger.error(f"Error reading {skill_file}: {e}")
        return None

    meta, body = _parse_frontmatter(content)
    if not meta.get("name"):
        meta["name"] = os.path.basename(skill_dir)

    meta["_dir"] = skill_dir
    meta["_body_length"] = len(body)
    return meta


def _list_skill_files(skill_dir: str) -> List[str]:
    """List all files in a skill directory (relative paths)."""
    files = []
    for root, dirs, filenames in os.walk(skill_dir):
        # Skip hidden dirs
        dirs[:] = [d for d in dirs if not d.startswith(".")]
        for fname in filenames:
            if fname.startswith("."):
                continue
            full_path = os.path.join(root, fname)
            rel_path = os.path.relpath(full_path, skill_dir)
            files.append(rel_path)
    return sorted(files)


# ---------------------------------------------------------------------------
# Tool handlers
# ---------------------------------------------------------------------------

def skills_list(home: str = "") -> str:
    """List all available skills with metadata.

    Args:
        home: Hermes home directory
    """
    if not home:
        return tool_error("Home directory not configured")

    sdir = _skills_dir(home)
    if not os.path.isdir(sdir):
        return tool_result({"skills": [], "count": 0})

    skills = []
    try:
        entries = sorted(os.listdir(sdir))
    except Exception as e:
        return tool_error(f"Error listing skills: {e}")

    for entry in entries:
        skill_path = os.path.join(sdir, entry)
        if not os.path.isdir(skill_path):
            continue

        meta = _load_skill_metadata(skill_path)
        if meta is None:
            continue

        skills.append({
            "name": meta.get("name", entry),
            "description": meta.get("description", ""),
            "version": meta.get("version", "1.0"),
            "category": meta.get("category", "general"),
            "emoji": meta.get("emoji", ""),
            "file_count": len(_list_skill_files(skill_path)),
        })

    return tool_result({"skills": skills, "count": len(skills)})


def skill_view(name: str, home: str = "", file: str = "") -> str:
    """View a skill's content or a specific file within it.

    Args:
        name: Skill name
        home: Hermes home directory
        file: Optional specific file to view (relative path within skill)
    """
    if not home:
        return tool_error("Home directory not configured")
    if not name:
        return tool_error("Skill name is required")

    sdir = _skills_dir(home)
    skill_path = os.path.join(sdir, name)

    # Prevent path traversal
    real_sdir = os.path.realpath(sdir)
    real_skill = os.path.realpath(skill_path)
    if not real_skill.startswith(real_sdir):
        return tool_error("Invalid skill name")

    if not os.path.isdir(skill_path):
        return tool_error(f"Skill not found: {name}")

    if file:
        # View a specific file
        file_path = os.path.join(skill_path, file)
        real_file = os.path.realpath(file_path)
        if not real_file.startswith(real_skill):
            return tool_error("Invalid file path")

        # Only allow files in allowed subdirs or SKILL.md
        rel = os.path.relpath(real_file, real_skill)
        first_part = rel.split(os.sep)[0]
        if first_part not in ALLOWED_SUBDIRS and first_part != SKILL_FILE:
            return tool_error(f"File not in allowed location: {first_part}")

        if not os.path.isfile(file_path):
            return tool_error(f"File not found: {file}")

        try:
            with open(file_path, "r", encoding="utf-8") as f:
                content = f.read()
            return tool_result({"file": file, "content": content, "skill": name})
        except Exception as e:
            return tool_error(f"Error reading file: {e}")
    else:
        # View the full SKILL.md
        skill_file = os.path.join(skill_path, SKILL_FILE)
        if not os.path.isfile(skill_file):
            return tool_error(f"SKILL.md not found for: {name}")

        try:
            with open(skill_file, "r", encoding="utf-8") as f:
                content = f.read()
        except Exception as e:
            return tool_error(f"Error reading skill: {e}")

        meta, body = _parse_frontmatter(content)
        files = _list_skill_files(skill_path)

        return tool_result({
            "skill": name,
            "metadata": meta,
            "content": body,
            "files": files,
        })


# ---------------------------------------------------------------------------
# Registration
# ---------------------------------------------------------------------------

registry.register(
    name="skills_list",
    handler=skills_list,
    schema={
        "type": "function",
        "function": {
            "name": "skills_list",
            "description": "List all available skills with their metadata (name, description, version, category).",
            "parameters": {
                "type": "object",
                "properties": {},
                "required": [],
            },
        },
    },
    description="List available skills",
    emoji="🎯",
)

registry.register(
    name="skill_view",
    handler=skill_view,
    schema={
        "type": "function",
        "function": {
            "name": "skill_view",
            "description": "View a skill's full content (SKILL.md) or a specific support file within it.",
            "parameters": {
                "type": "object",
                "properties": {
                    "name": {
                        "type": "string",
                        "description": "Skill name to view",
                    },
                    "file": {
                        "type": "string",
                        "description": "Optional specific file to view (relative path within skill directory)",
                    },
                },
                "required": ["name"],
            },
        },
    },
    description="View skill content",
    emoji="🎯",
)
