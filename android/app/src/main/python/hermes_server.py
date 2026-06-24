"""Hermes Agent Android server - lightweight FastAPI backend.

This is a self-contained FastAPI server that runs on Android via Chaquopy.
It provides the core API endpoints needed by the React Native UI:
  - Chat with LLM (streaming via SSE)
  - Session management (in-memory + file persistence)
  - Configuration & environment variables
  - System status / health check

LLM calls go through the openai Python SDK (compatible with OpenAI,
OpenRouter, Anthropic via OpenRouter, etc.).
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse, JSONResponse

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("hermes_server")

# ---------------------------------------------------------------------------
# State
# ---------------------------------------------------------------------------

_hermes_home: str = ""
_start_time: float = time.time()
_sessions: Dict[str, dict] = {}  # id -> session dict
_config: dict = {}
_env_vars: Dict[str, str] = {}

DEFAULT_CONFIG = {
    "model": {"default": "openrouter/auto", "provider": "auto"},
    "agent": {"max_turns": 60, "reasoning_effort": "medium"},
    "compression": {"enabled": True, "threshold": 0.50},
    "memory": {
        "memory_enabled": True,
        "user_profile_enabled": True,
        "nudge_interval": 10,
    },
    "session_reset": {"mode": "both", "idle_minutes": 1440},
    "skills": {"creation_nudge_interval": 15},
    "terminal": {"backend": "local"},
}

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _load_env_file(path: str) -> Dict[str, str]:
    """Parse a simple KEY=VALUE .env file."""
    env = {}
    try:
        with open(path) as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                if "=" in line:
                    k, v = line.split("=", 1)
                    env[k.strip()] = v.strip()
    except FileNotFoundError:
        pass
    return env


def _save_env_file(path: str, env: Dict[str, str]) -> None:
    with open(path, "w") as f:
        f.write("# Hermes Agent Environment Variables\n")
        for k, v in env.items():
            if not k.startswith("#"):
                f.write(f"{k}={v}\n")


def _load_config(path: str) -> dict:
    try:
        import yaml
        with open(path) as f:
            return yaml.safe_load(f) or {}
    except FileNotFoundError:
        return {}


def _save_config(path: str, cfg: dict) -> None:
    try:
        import yaml
        with open(path, "w") as f:
            yaml.dump(cfg, f, default_flow_style=False)
    except Exception:
        pass


def _persist_session(session: dict) -> None:
    """Save session to disk."""
    sessions_dir = os.path.join(_hermes_home, "sessions")
    os.makedirs(sessions_dir, exist_ok=True)
    sid = session["id"]
    path = os.path.join(sessions_dir, f"{sid}.json")
    with open(path, "w") as f:
        json.dump(session, f, indent=2, default=str)


def _load_sessions_from_disk() -> None:
    """Load persisted sessions on startup."""
    global _sessions
    sessions_dir = os.path.join(_hermes_home, "sessions")
    if not os.path.isdir(sessions_dir):
        return
    for fname in os.listdir(sessions_dir):
        if not fname.endswith(".json"):
            continue
        try:
            with open(os.path.join(sessions_dir, fname)) as f:
                s = json.load(f)
                _sessions[s["id"]] = s
        except Exception:
            pass


async def _call_llm_stream(messages: List[dict], model: str, api_key: str, base_url: str):
    """Stream chat completions from the LLM provider via openai SDK."""
    try:
        from openai import OpenAI
    except ImportError:
        yield 'data: {"type": "error", "data": {"text": "openai package not installed"}}\n\n'
        return

    try:
        client = OpenAI(api_key=api_key, base_url=base_url)
        stream = client.chat.completions.create(
            model=model,
            messages=messages,
            stream=True,
        )
        for chunk in stream:
            if chunk.choices and chunk.choices[0].delta.content:
                text = chunk.choices[0].delta.content
                yield f'data: {json.dumps({"type": "text_delta", "data": {"text": text}})}\n\n'
        yield 'data: {"type": "done", "data": {}}\n\n'
    except Exception as e:
        logger.error(f"LLM call failed: {e}")
        yield f'data: {json.dumps({"type": "error", "data": {"text": str(e)}})}\n\n'


def _get_llm_config() -> tuple:
    """Get model, api_key, base_url from config and env."""
    model = _config.get("model", {}).get("default", "openrouter/auto")
    provider = _config.get("model", {}).get("provider", "auto")

    # Determine API key and base URL based on provider
    api_key = ""
    base_url = "https://openrouter.ai/api/v1"

    if "anthropic" in provider or "anthropic" in model:
        api_key = _env_vars.get("ANTHROPIC_API_KEY", "")
        base_url = "https://openrouter.ai/api/v1"  # Use OpenRouter as proxy
    elif "google" in provider or "gemini" in model:
        api_key = _env_vars.get("GOOGLE_API_KEY", "")
        base_url = "https://openrouter.ai/api/v1"
    elif "openrouter" in model or provider == "auto":
        api_key = _env_vars.get("OPENROUTER_API_KEY", "")
        base_url = "https://openrouter.ai/api/v1"
    else:
        # Try OpenAI-compatible
        api_key = _env_vars.get("OPENAI_API_KEY", _env_vars.get("OPENROUTER_API_KEY", ""))
        base_url = _env_vars.get("OPENAI_BASE_URL", "https://openrouter.ai/api/v1")

    return model, api_key, base_url


# ---------------------------------------------------------------------------
# FastAPI app
# ---------------------------------------------------------------------------


def create_app() -> FastAPI:
    app = FastAPI(title="Hermes Agent Android", version="0.1.0")

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # ----- System -----

    @app.get("/api/status")
    async def api_status():
        return {
            "status": "running",
            "version": "0.1.0-android",
            "uptime": int(time.time() - _start_time),
            "active_sessions": len(_sessions),
            "gateway_status": {},
        }

    @app.get("/api/health")
    async def api_health():
        return {"status": "ok"}

    @app.get("/api/system/stats")
    async def api_system_stats():
        total_msgs = sum(s.get("message_count", 0) for s in _sessions.values())
        return {
            "total_tokens": 0,
            "total_cost": 0.0,
            "sessions_count": len(_sessions),
            "messages_count": total_msgs,
            "by_model": {},
        }

    # ----- Chat -----

    @app.post("/api/chat")
    async def api_chat(request: Request):
        """Send a message and get a streaming response via SSE."""
        body = await request.json()
        session_id = body.get("session_id")
        message = body.get("message", "")

        if not message:
            raise HTTPException(400, "message is required")

        # Get or create session
        if not session_id or session_id not in _sessions:
            session_id = str(uuid.uuid4())
            _sessions[session_id] = {
                "id": session_id,
                "title": message[:50],
                "model": _config.get("model", {}).get("default", "openrouter/auto"),
                "provider": _config.get("model", {}).get("provider", "auto"),
                "created_at": _now_iso(),
                "updated_at": _now_iso(),
                "message_count": 0,
                "token_count": 0,
                "messages": [],
            }

        session = _sessions[session_id]

        # Add user message
        session["messages"].append({
            "id": str(uuid.uuid4()),
            "role": "user",
            "content": message,
            "timestamp": _now_iso(),
        })
        session["message_count"] += 1
        session["updated_at"] = _now_iso()

        # Build messages for LLM
        llm_messages = []
        for m in session["messages"][-20:]:  # Last 20 messages for context
            llm_messages.append({"role": m["role"], "content": m["content"]})

        model, api_key, base_url = _get_llm_config()

        if not api_key:
            # No API key configured - return error message
            session["messages"].append({
                "id": str(uuid.uuid4()),
                "role": "assistant",
                "content": "Please configure your API key in Settings first. You need at least an OPENROUTER_API_KEY or OPENAI_API_KEY.",
                "timestamp": _now_iso(),
            })
            session["message_count"] += 1
            _persist_session(session)
            return StreamingResponse(
                iter(['data: {"type": "text_delta", "data": {"text": "Please configure your API key in Settings first. You need at least an OPENROUTER_API_KEY or OPENAI_API_KEY."}}\n\n',
                      'data: {"type": "done", "data": {}}\n\n']),
                media_type="text/event-stream",
            )

        # Stream LLM response
        async def generate():
            full_text = ""
            async for event in _call_llm_stream(llm_messages, model, api_key, base_url):
                yield event
                # Extract text delta for session persistence
                try:
                    data_str = event.removeprefix("data: ").strip()
                    if data_str:
                        parsed = json.loads(data_str)
                        if parsed.get("type") == "text_delta":
                            full_text += parsed["data"]["text"]
                except Exception:
                    pass

            # Save assistant response to session
            if full_text:
                session["messages"].append({
                    "id": str(uuid.uuid4()),
                    "role": "assistant",
                    "content": full_text,
                    "timestamp": _now_iso(),
                    "model": model,
                })
                session["message_count"] += 1
                session["updated_at"] = _now_iso()
                _persist_session(session)

        return StreamingResponse(generate(), media_type="text/event-stream")

    # ----- Sessions -----

    @app.get("/api/sessions")
    async def api_list_sessions():
        result = []
        for s in _sessions.values():
            result.append({
                "id": s["id"],
                "title": s.get("title", "Untitled"),
                "model": s.get("model", ""),
                "provider": s.get("provider", ""),
                "created_at": s.get("created_at", ""),
                "updated_at": s.get("updated_at", ""),
                "message_count": s.get("message_count", 0),
                "token_count": s.get("token_count", 0),
                "preview": s.get("messages", [{}])[-1].get("content", "")[:100] if s.get("messages") else "",
            })
        return result

    @app.post("/api/sessions")
    async def api_create_session(request: Request):
        body = await request.json() if request.headers.get("content-type") else {}
        title = body.get("title", "New Session") if isinstance(body, dict) else "New Session"
        sid = str(uuid.uuid4())
        session = {
            "id": sid,
            "title": title,
            "model": _config.get("model", {}).get("default", "openrouter/auto"),
            "provider": _config.get("model", {}).get("provider", "auto"),
            "created_at": _now_iso(),
            "updated_at": _now_iso(),
            "message_count": 0,
            "token_count": 0,
            "messages": [],
        }
        _sessions[sid] = session
        _persist_session(session)
        return session

    @app.get("/api/sessions/{session_id}")
    async def api_get_session(session_id: str):
        if session_id not in _sessions:
            raise HTTPException(404, "Session not found")
        return _sessions[session_id]

    @app.delete("/api/sessions/{session_id}")
    async def api_delete_session(session_id: str):
        if session_id in _sessions:
            del _sessions[session_id]
            # Remove from disk
            path = os.path.join(_hermes_home, "sessions", f"{session_id}.json")
            if os.path.exists(path):
                os.remove(path)
        return {"ok": True}

    @app.get("/api/sessions/search")
    async def api_search_sessions(q: str = ""):
        if not q:
            return list(_sessions.values())
        q_lower = q.lower()
        return [
            s for s in _sessions.values()
            if q_lower in s.get("title", "").lower()
            or any(q_lower in m.get("content", "").lower() for m in s.get("messages", []))
        ]

    @app.get("/api/sessions/stats")
    async def api_session_stats():
        return {
            "total": len(_sessions),
            "total_messages": sum(s.get("message_count", 0) for s in _sessions.values()),
        }

    @app.get("/api/sessions/{session_id}/export")
    async def api_export_session(session_id: str):
        if session_id not in _sessions:
            raise HTTPException(404, "Session not found")
        return _sessions[session_id]

    # ----- Config -----

    @app.get("/api/config")
    async def api_get_config():
        return _config

    @app.put("/api/config")
    async def api_update_config(request: Request):
        global _config
        body = await request.json()
        _config.update(body)
        _save_config(os.path.join(_hermes_home, "config.yaml"), _config)
        return _config

    @app.get("/api/config/raw")
    async def api_get_config_raw():
        try:
            with open(os.path.join(_hermes_home, "config.yaml")) as f:
                return f.read()
        except FileNotFoundError:
            return ""

    # ----- Environment / API Keys -----

    @app.get("/api/env")
    async def api_get_env():
        known_keys = [
            "OPENROUTER_API_KEY", "OPENAI_API_KEY", "ANTHROPIC_API_KEY",
            "GOOGLE_API_KEY", "GROQ_API_KEY", "OPENAI_BASE_URL",
        ]
        result = []
        for k in known_keys:
            v = _env_vars.get(k, "")
            result.append({
                "key": k,
                "value": v[:8] + "..." if len(v) > 8 else v,
                "is_set": bool(v),
            })
        return result

    @app.put("/api/env")
    async def api_set_env(request: Request):
        global _env_vars
        body = await request.json()
        key = body.get("key")
        value = body.get("value", "")
        if not key:
            raise HTTPException(400, "key is required")
        _env_vars[key] = value
        os.environ[key] = value
        _save_env_file(os.path.join(_hermes_home, ".env"), _env_vars)
        return {"ok": True, "key": key}

    @app.delete("/api/env")
    async def api_delete_env(request: Request):
        global _env_vars
        body = await request.json()
        key = body.get("key")
        if key in _env_vars:
            del _env_vars[key]
        os.environ.pop(key, None)
        _save_env_file(os.path.join(_hermes_home, ".env"), _env_vars)
        return {"ok": True}

    # ----- Model -----

    @app.get("/api/model/options")
    async def api_model_options():
        return [
            {"id": "openrouter/auto", "name": "Auto (OpenRouter)", "provider": "openrouter",
             "context_length": 128000, "supports_vision": True, "supports_tools": True},
            {"id": "openai/gpt-4o", "name": "GPT-4o", "provider": "openrouter",
             "context_length": 128000, "supports_vision": True, "supports_tools": True},
            {"id": "openai/gpt-4o-mini", "name": "GPT-4o Mini", "provider": "openrouter",
             "context_length": 128000, "supports_vision": True, "supports_tools": True},
            {"id": "anthropic/claude-sonnet-4", "name": "Claude Sonnet 4", "provider": "openrouter",
             "context_length": 200000, "supports_vision": True, "supports_tools": True},
            {"id": "google/gemini-2.5-pro", "name": "Gemini 2.5 Pro", "provider": "openrouter",
             "context_length": 1000000, "supports_vision": True, "supports_tools": True},
            {"id": "deepseek/deepseek-chat", "name": "DeepSeek V3", "provider": "openrouter",
             "context_length": 65536, "supports_vision": False, "supports_tools": True},
        ]

    @app.get("/api/model/current")
    async def api_model_current():
        return {
            "model": _config.get("model", {}).get("default", "openrouter/auto"),
            "provider": _config.get("model", {}).get("provider", "auto"),
        }

    @app.post("/api/model/set")
    async def api_model_set(request: Request):
        global _config
        body = await request.json()
        model = body.get("model", "openrouter/auto")
        provider = body.get("provider", "auto")
        _config.setdefault("model", {})["default"] = model
        _config["model"]["provider"] = provider
        _save_config(os.path.join(_hermes_home, "config.yaml"), _config)
        return {"model": model, "provider": provider}

    # ----- Skills (stub) -----

    @app.get("/api/skills")
    async def api_list_skills():
        return []

    @app.get("/api/skills/hub/search")
    async def api_skills_hub_search(q: str = ""):
        return []

    # ----- Cron (stub) -----

    @app.get("/api/cron/jobs")
    async def api_list_cron():
        return []

    # ----- MCP (stub) -----

    @app.get("/api/mcp/servers")
    async def api_list_mcp():
        return []

    # ----- Memory (stub) -----

    @app.get("/api/memory")
    async def api_get_memory():
        return {"enabled": False}

    # ----- Tools (stub) -----

    @app.get("/api/tools/toolsets")
    async def api_list_toolsets():
        return []

    # ----- Logs -----

    @app.get("/api/logs")
    async def api_get_logs():
        return []

    return app


# ---------------------------------------------------------------------------
# Entry point (called from Kotlin via Chaquopy)
# ---------------------------------------------------------------------------


def start_server() -> None:
    """Start the Hermes FastAPI server on localhost.

    Called from Kotlin via Chaquopy:
      Python.getInstance().getModule("hermes_server").callAttr("start_server")
    """
    global _hermes_home, _config, _env_vars

    from android_bootstrap import bootstrap
    _hermes_home = bootstrap()

    # Load persisted config and env
    _config = _load_config(os.path.join(_hermes_home, "config.yaml"))
    if not _config:
        _config = DEFAULT_CONFIG.copy()
        _save_config(os.path.join(_hermes_home, "config.yaml"), _config)

    _env_vars = _load_env_file(os.path.join(_hermes_home, ".env"))
    # Set env vars into process environment
    for k, v in _env_vars.items():
        os.environ.setdefault(k, v)

    # Load persisted sessions
    _load_sessions_from_disk()

    logger.info(f"Hermes home: {_hermes_home}")
    logger.info(f"Loaded {len(_sessions)} sessions, {len(_env_vars)} env vars")

    # Create and run the app
    app = create_app()
    logger.info("Starting Hermes server on 127.0.0.1:9119")

    import uvicorn
    config = uvicorn.Config(
        app,
        host="127.0.0.1",
        port=9119,
        log_level="info",
        access_log=False,
    )
    server = uvicorn.Server(config)
    server.run()


def get_status() -> str:
    """Return server status for health check."""
    try:
        import urllib.request
        req = urllib.request.Request("http://127.0.0.1:9119/api/status")
        with urllib.request.urlopen(req, timeout=2) as resp:
            return resp.read().decode()
    except Exception:
        return '{"status": "starting"}'
