"""Hermes Agent Android - Tools Package.

Simplified Android-adapted version of the Hermes Agent tools system.
"""

from tools.registry import registry, tool_error, tool_result

# Import tool modules to trigger registration
import tools.todo_tool
import tools.memory_tool
import tools.skills_tool
import tools.skill_manager_tool
import tools.cronjob_tools
import tools.web_search_tool
import tools.file_tools

__all__ = ["registry", "tool_error", "tool_result"]
