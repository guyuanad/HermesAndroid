"""Cron Jobs - JSON file storage + simple scheduler for Hermes Android.

Self-implemented replacement for hermes-agent/cron/jobs.py.
Uses JSON file persistence and a background thread scheduler.

Removes: gateway/session_context, external provider notification.
Keeps: Core job CRUD, schedule parsing, pause/resume, claim/execution tracking.
"""

from __future__ import annotations

import json
import logging
import os
import re
import tempfile
import threading
import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

logger = logging.getLogger("hermes.tools.cron")

# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------

class AmbiguousJobReference(Exception):
    """Raised when a job reference matches multiple jobs."""
    pass


# ---------------------------------------------------------------------------
# Schedule Parsing
# ---------------------------------------------------------------------------

def parse_schedule(schedule: str) -> Dict[str, Any]:
    """Parse a cron schedule string into components.

    Supports: minute hour day-of-month month day-of-week
    Examples: "*/5 * * * *" (every 5 min), "0 9 * * 1-5" (9am weekdays)

    Returns dict with: minute, hour, dom, month, dow, description
    """
    parts = schedule.strip().split()
    if len(parts) != 5:
        raise ValueError(f"Invalid cron schedule (need 5 fields): {schedule}")

    result = {
        "minute": parts[0],
        "hour": parts[1],
        "dom": parts[2],  # day of month
        "month": parts[3],
        "dow": parts[4],  # day of week
    }

    # Generate human-readable description
    desc_parts = []
    if parts[0] == "*/5":
        desc_parts.append("每5分钟")
    elif parts[0] == "*/15":
        desc_parts.append("每15分钟")
    elif parts[0] == "*/30":
        desc_parts.append("每30分钟")
    elif parts[0] == "0":
        desc_parts.append("整点")
    else:
        desc_parts.append(f"分钟:{parts[0]}")

    if parts[1] != "*":
        desc_parts.append(f"{parts[1]}时")

    if parts[4] != "*":
        day_map = {"0": "周日", "1": "周一", "2": "周二", "3": "周三",
                    "4": "周四", "5": "周五", "6": "周六"}
        days = []
        for d in parts[4].split(","):
            if "-" in d:
                start, end = d.split("-")
                for i in range(int(start), int(end) + 1):
                    days.append(day_map.get(str(i), str(i)))
            else:
                days.append(day_map.get(d, d))
        desc_parts.append(",".join(days))

    if parts[2] != "*":
        desc_parts.append(f"每月{parts[2]}日")

    result["description"] = " ".join(desc_parts) if desc_parts else "每分钟"
    return result


def _matches_cron_field(value: int, pattern: str) -> bool:
    """Check if a value matches a cron field pattern."""
    if pattern == "*":
        return True

    # Handle step values: */N
    if pattern.startswith("*/"):
        step = int(pattern[2:])
        return value % step == 0

    # Handle ranges: N-M
    if "-" in pattern and "," not in pattern:
        start, end = pattern.split("-")
        return int(start) <= value <= int(end)

    # Handle lists: N,M,K
    if "," in pattern:
        for item in pattern.split(","):
            if _matches_cron_field(value, item):
                return True
        return False

    # Simple value
    return value == int(pattern)


def _should_fire_now(schedule_str: str) -> bool:
    """Check if a cron schedule should fire at the current time."""
    try:
        parsed = parse_schedule(schedule_str)
    except ValueError:
        return False

    now = datetime.now(timezone.utc)
    return (
        _matches_cron_field(now.minute, parsed["minute"])
        and _matches_cron_field(now.hour, parsed["hour"])
        and _matches_cron_field(now.day, parsed["dom"])
        and _matches_cron_field(now.month, parsed["month"])
        and _matches_cron_field(now.isoweekday() % 7, parsed["dow"])
    )


# ---------------------------------------------------------------------------
# Job Store (JSON file)
# ---------------------------------------------------------------------------

class JobStore:
    """JSON file-based job storage."""

    def __init__(self, data_dir: str):
        self._path = os.path.join(data_dir, "cron_jobs.json")
        self._lock = threading.Lock()
        self._jobs: Dict[str, dict] = {}
        self._load()

    def _load(self) -> None:
        """Load jobs from disk."""
        try:
            with open(self._path, "r", encoding="utf-8") as f:
                data = json.load(f)
            self._jobs = {k: v for k, v in data.items()}
        except (FileNotFoundError, json.JSONDecodeError):
            self._jobs = {}

    def _save(self) -> None:
        """Save jobs to disk atomically."""
        dir_path = os.path.dirname(self._path)
        os.makedirs(dir_path, exist_ok=True)
        fd, tmp_path = tempfile.mkstemp(dir=dir_path, suffix=".json")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                json.dump(self._jobs, f, indent=2, ensure_ascii=False, default=str)
            os.replace(tmp_path, self._path)
        except Exception:
            try:
                os.unlink(tmp_path)
            except OSError:
                pass
            raise

    def get(self, job_id: str) -> Optional[dict]:
        """Get a job by ID."""
        with self._lock:
            return self._jobs.get(job_id)

    def get_by_name(self, name: str) -> Optional[dict]:
        """Get a job by name."""
        with self._lock:
            for job in self._jobs.values():
                if job.get("name") == name:
                    return job
        return None

    def list_all(self) -> List[dict]:
        """List all jobs."""
        with self._lock:
            return list(self._jobs.values())

    def put(self, job: dict) -> None:
        """Insert or update a job."""
        with self._lock:
            self._jobs[job["id"]] = job
            self._save()

    def delete(self, job_id: str) -> bool:
        """Delete a job. Returns True if deleted."""
        with self._lock:
            if job_id in self._jobs:
                del self._jobs[job_id]
                self._save()
                return True
            return False


# ---------------------------------------------------------------------------
# Global job store instance
# ---------------------------------------------------------------------------

_job_store: Optional[JobStore] = None
_scheduler_thread: Optional[threading.Thread] = None
_scheduler_running = False
_on_job_fire = None  # Callback: (job_dict) -> None


def init_jobs(data_dir: str, on_fire=None) -> None:
    """Initialize the job store and start the scheduler."""
    global _job_store, _scheduler_thread, _scheduler_running, _on_job_fire

    _job_store = JobStore(data_dir)
    _on_job_fire = on_fire

    # Start background scheduler
    _scheduler_running = True
    _scheduler_thread = threading.Thread(target=_scheduler_loop, daemon=True)
    _scheduler_thread.start()

    logger.info(f"Cron scheduler initialized with {len(_job_store.list_all())} jobs")


def shutdown_jobs() -> None:
    """Stop the scheduler."""
    global _scheduler_running
    _scheduler_running = False


def _scheduler_loop() -> None:
    """Background loop that checks for jobs to fire."""
    global _scheduler_running

    while _scheduler_running:
        try:
            now = datetime.now(timezone.utc)
            # Sleep until next minute boundary
            sleep_seconds = 60 - now.second - now.microsecond / 1_000_000
            time.sleep(max(sleep_seconds, 1))

            if not _scheduler_running:
                break

            # Check all active jobs
            if _job_store:
                for job in _job_store.list_all():
                    if job.get("paused"):
                        continue
                    schedule = job.get("schedule", "")
                    if not schedule:
                        continue

                    if _should_fire_now(schedule):
                        _fire_job(job)

        except Exception as e:
            logger.error(f"Scheduler error: {e}")
            time.sleep(10)


def _fire_job(job: dict) -> None:
    """Fire a job and update its last_run timestamp."""
    if _job_store:
        # Claim the job (prevent double-fire)
        claimed = claim_job_for_fire(job["id"])
        if not claimed:
            return

        logger.info(f"Firing cron job: {job.get('name', job['id'])}")

        # Call the callback if set
        if _on_job_fire:
            try:
                _on_job_fire(job)
            except Exception as e:
                logger.error(f"Job fire callback error: {e}")


# ---------------------------------------------------------------------------
# Public API (matching original cron.jobs interface)
# ---------------------------------------------------------------------------

def create_job(
    name: str,
    schedule: str,
    prompt: str = "",
    model: str = "",
    skill: str = "",
    skill_input: str = "",
) -> dict:
    """Create a new cron job."""
    if not _job_store:
        raise RuntimeError("Job store not initialized")

    # Validate schedule
    parsed = parse_schedule(schedule)

    import uuid
    job_id = str(uuid.uuid4())[:8]

    job = {
        "id": job_id,
        "name": name,
        "schedule": schedule,
        "schedule_description": parsed.get("description", schedule),
        "prompt": prompt,
        "model": model,
        "skill": skill,
        "skill_input": skill_input,
        "paused": False,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "last_run": None,
        "run_count": 0,
    }

    _job_store.put(job)
    return job


def get_job(job_id: str) -> Optional[dict]:
    """Get a job by ID."""
    if not _job_store:
        return None
    return _job_store.get(job_id)


def list_jobs() -> List[dict]:
    """List all jobs."""
    if not _job_store:
        return []
    return _job_store.list_all()


def update_job(job_id: str, **updates) -> Optional[dict]:
    """Update a job's fields."""
    if not _job_store:
        return None

    job = _job_store.get(job_id)
    if not job:
        return None

    # If schedule is being updated, re-parse it
    if "schedule" in updates:
        parsed = parse_schedule(updates["schedule"])
        updates["schedule_description"] = parsed.get("description", updates["schedule"])

    job.update(updates)
    job["updated_at"] = datetime.now(timezone.utc).isoformat()
    _job_store.put(job)
    return job


def pause_job(job_id: str) -> Optional[dict]:
    """Pause a job."""
    return update_job(job_id, paused=True)


def resume_job(job_id: str) -> Optional[dict]:
    """Resume a paused job."""
    return update_job(job_id, paused=False)


def remove_job(job_id: str) -> bool:
    """Remove a job."""
    if not _job_store:
        return False
    return _job_store.delete(job_id)


def resolve_job_ref(ref: str) -> Optional[dict]:
    """Resolve a job reference (ID or name) to a job dict.

    Raises AmbiguousJobReference if the name matches multiple jobs.
    """
    if not _job_store:
        return None

    # Try by ID first
    job = _job_store.get(ref)
    if job:
        return job

    # Try by name
    matches = []
    for j in _job_store.list_all():
        if j.get("name") == ref:
            matches.append(j)
        elif ref.lower() in j.get("name", "").lower():
            matches.append(j)

    if len(matches) == 1:
        return matches[0]
    elif len(matches) > 1:
        names = [m.get("name", m["id"]) for m in matches]
        raise AmbiguousJobReference(
            f"Reference '{ref}' matches multiple jobs: {', '.join(names)}"
        )

    return None


def mark_job_run(job_id: str) -> None:
    """Mark a job as having been run."""
    if not _job_store:
        return

    job = _job_store.get(job_id)
    if job:
        job["last_run"] = datetime.now(timezone.utc).isoformat()
        job["run_count"] = job.get("run_count", 0) + 1
        job["updated_at"] = datetime.now(timezone.utc).isoformat()
        _job_store.put(job)


def claim_job_for_fire(job_id: str) -> bool:
    """Claim a job for firing (prevent double-fire).

    Returns True if the job was successfully claimed.
    """
    if not _job_store:
        return False

    job = _job_store.get(job_id)
    if not job:
        return False

    # Simple check: don't fire if it was already fired in the last 30 seconds
    last_run = job.get("last_run")
    if last_run:
        try:
            last_dt = datetime.fromisoformat(last_run)
            elapsed = (datetime.now(timezone.utc) - last_dt).total_seconds()
            if elapsed < 30:
                return False
        except (ValueError, TypeError):
            pass

    mark_job_run(job_id)
    return True
