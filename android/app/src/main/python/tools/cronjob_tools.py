"""Cron Job Tools for Hermes Android.

Simplified port from hermes-agent/tools/cronjob_tools.py.
Removes: gateway/session_context, external provider notification, threat scanning,
         invisible unicode checking, model override from config.
Keeps: cronjob() with create/list/update/pause/resume/remove/run operations,
       schedule parsing via cron.jobs sub-module.
"""

from __future__ import annotations

import json
import logging
from typing import Any, Optional

from tools.registry import registry, tool_error, tool_result
from tools.cron import jobs as cron_jobs

logger = logging.getLogger("hermes.tools.cronjob")

# ---------------------------------------------------------------------------
# Home directory (set by hermes_server)
# ---------------------------------------------------------------------------

_hermes_home: str = ""


def set_home(home: str) -> None:
    """Set the Hermes home directory for cron tools."""
    global _hermes_home
    _hermes_home = home


def _inject_home(kwargs: dict) -> dict:
    """Ensure 'home' kwarg is available for skill tools that need it."""
    if "home" not in kwargs:
        kwargs["home"] = _hermes_home
    return kwargs


# ---------------------------------------------------------------------------
# Tool handler
# ---------------------------------------------------------------------------

def cronjob(
    action: str,
    ref: str = "",
    name: str = "",
    schedule: str = "",
    prompt: str = "",
    model: str = "",
    skill: str = "",
    skill_input: str = "",
    paused: bool = False,
) -> str:
    """Manage cron jobs: create, list, update, pause, resume, remove, run.

    Args:
        action: Operation to perform
        ref: Job reference (ID or name) for update/pause/resume/remove/run
        name: Job name (for create)
        schedule: Cron schedule expression (for create/update)
        prompt: Prompt to execute (for create/update)
        model: Model override (for create/update)
        skill: Skill name to execute (for create/update)
        skill_input: Input for skill execution (for create/update)
        paused: Initial paused state (for create)
    """
    # ---- CREATE ----
    if action == "create":
        if not name:
            return tool_error("Job name is required")
        if not schedule:
            return tool_error("Schedule is required (cron format: minute hour day month weekday)")
        if not prompt and not skill:
            return tool_error("Either 'prompt' or 'skill' is required")

        # Validate schedule format
        try:
            cron_jobs.parse_schedule(schedule)
        except ValueError as e:
            return tool_error(str(e))

        try:
            job = cron_jobs.create_job(
                name=name,
                schedule=schedule,
                prompt=prompt,
                model=model,
                skill=skill,
                skill_input=skill_input,
            )
            if paused:
                cron_jobs.pause_job(job["id"])
                job["paused"] = True

            return tool_result({
                "action": "create",
                "id": job["id"],
                "name": job["name"],
                "schedule": job["schedule"],
                "schedule_description": job.get("schedule_description", schedule),
                "status": "paused" if paused else "active",
            })
        except Exception as e:
            return tool_error(f"Error creating job: {e}")

    # ---- LIST ----
    elif action == "list":
        try:
            job_list = cron_jobs.list_jobs()
            return tool_result({
                "jobs": job_list,
                "count": len(job_list),
            })
        except Exception as e:
            return tool_error(f"Error listing jobs: {e}")

    # ---- UPDATE ----
    elif action == "update":
        if not ref:
            return tool_error("Job reference (ref) is required")

        try:
            job = cron_jobs.resolve_job_ref(ref)
        except cron_jobs.AmbiguousJobReference as e:
            return tool_error(str(e))

        if not job:
            return tool_error(f"Job not found: {ref}")

        updates = {}
        if name:
            updates["name"] = name
        if schedule:
            try:
                cron_jobs.parse_schedule(schedule)
            except ValueError as e:
                return tool_error(str(e))
            updates["schedule"] = schedule
        if prompt:
            updates["prompt"] = prompt
        if model:
            updates["model"] = model
        if skill:
            updates["skill"] = skill
        if skill_input:
            updates["skill_input"] = skill_input

        if not updates:
            return tool_error("No fields to update")

        try:
            updated = cron_jobs.update_job(job["id"], **updates)
            return tool_result({
                "action": "update",
                "id": job["id"],
                "name": updated.get("name", ""),
                "updates": list(updates.keys()),
            })
        except Exception as e:
            return tool_error(f"Error updating job: {e}")

    # ---- PAUSE ----
    elif action == "pause":
        if not ref:
            return tool_error("Job reference (ref) is required")

        try:
            job = cron_jobs.resolve_job_ref(ref)
        except cron_jobs.AmbiguousJobReference as e:
            return tool_error(str(e))

        if not job:
            return tool_error(f"Job not found: {ref}")

        cron_jobs.pause_job(job["id"])
        return tool_result({"action": "pause", "id": job["id"], "name": job.get("name", ""), "status": "paused"})

    # ---- RESUME ----
    elif action == "resume":
        if not ref:
            return tool_error("Job reference (ref) is required")

        try:
            job = cron_jobs.resolve_job_ref(ref)
        except cron_jobs.AmbiguousJobReference as e:
            return tool_error(str(e))

        if not job:
            return tool_error(f"Job not found: {ref}")

        cron_jobs.resume_job(job["id"])
        return tool_result({"action": "resume", "id": job["id"], "name": job.get("name", ""), "status": "active"})

    # ---- REMOVE ----
    elif action == "remove":
        if not ref:
            return tool_error("Job reference (ref) is required")

        try:
            job = cron_jobs.resolve_job_ref(ref)
        except cron_jobs.AmbiguousJobReference as e:
            return tool_error(str(e))

        if not job:
            return tool_error(f"Job not found: {ref}")

        cron_jobs.remove_job(job["id"])
        return tool_result({"action": "remove", "id": job["id"], "name": job.get("name", ""), "status": "removed"})

    # ---- RUN ----
    elif action == "run":
        if not ref:
            return tool_error("Job reference (ref) is required")

        try:
            job = cron_jobs.resolve_job_ref(ref)
        except cron_jobs.AmbiguousJobReference as e:
            return tool_error(str(e))

        if not job:
            return tool_error(f"Job not found: {ref}")

        # Mark as run and return job details for execution
        cron_jobs.mark_job_run(job["id"])
        return tool_result({
            "action": "run",
            "id": job["id"],
            "name": job.get("name", ""),
            "prompt": job.get("prompt", ""),
            "model": job.get("model", ""),
            "skill": job.get("skill", ""),
            "skill_input": job.get("skill_input", ""),
            "status": "triggered",
        })

    else:
        return tool_error(
            f"Unknown action: {action}. Valid: create, list, update, pause, resume, remove, run"
        )


# ---------------------------------------------------------------------------
# Registration
# ---------------------------------------------------------------------------

registry.register(
    name="cronjob",
    handler=cronjob,
    schema={
        "type": "function",
        "function": {
            "name": "cronjob",
            "description": "Manage scheduled tasks (cron jobs). Create, list, update, pause, resume, remove, or manually run jobs.",
            "parameters": {
                "type": "object",
                "properties": {
                    "action": {
                        "type": "string",
                        "enum": ["create", "list", "update", "pause", "resume", "remove", "run"],
                        "description": "Operation to perform",
                    },
                    "ref": {
                        "type": "string",
                        "description": "Job reference (ID or name) for update/pause/resume/remove/run",
                    },
                    "name": {
                        "type": "string",
                        "description": "Job name (for create/update)",
                    },
                    "schedule": {
                        "type": "string",
                        "description": "Cron schedule (minute hour day month weekday), e.g. '*/5 * * * *' or '0 9 * * 1-5'",
                    },
                    "prompt": {
                        "type": "string",
                        "description": "Prompt to execute when job fires",
                    },
                    "model": {
                        "type": "string",
                        "description": "Model override for job execution",
                    },
                    "skill": {
                        "type": "string",
                        "description": "Skill name to execute when job fires",
                    },
                    "skill_input": {
                        "type": "string",
                        "description": "Input for skill execution",
                    },
                    "paused": {
                        "type": "boolean",
                        "description": "Create job in paused state",
                    },
                },
                "required": ["action"],
            },
        },
    },
    description="Manage scheduled tasks (cron jobs)",
    emoji="⏰",
)
