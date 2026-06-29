"""Hermes Agent Android server - v0.3.0 with full tool system.

FastAPI backend running on Android via Chaquopy.
Integrates: ToolRegistry, MemoryStore, Skills, Cron, TodoStore.
Supports agent loop with tool calling via OpenAI-compatible API.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import time
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import httpx
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
_sessions: Dict[str, dict] = {}
_config: dict = {}
_env_vars: Dict[str, str] = {}
_registry = None  # Initialized after tools import

DEFAULT_CONFIG = {
    "model": {"default": "agnes-2.0-flash", "provider": "agnes"},
    "agent": {"max_turns": 10, "reasoning_effort": "medium"},
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

DEFAULT_API_KEY = "sk-ZhRdw91eDhWgmR3qGSr5LjbNTgsKDReZhjXQLkEpXvrUWAhr"
DEFAULT_BASE_URL = "https://apihub.agnes-ai.com/v1"
DEFAULT_MODEL = "agnes-2.0-flash"
MAX_TOOL_TURNS = 10


# ---------------------------------------------------------------------------
# Format tool results as readable text (when LLM fails to summarize)
# ---------------------------------------------------------------------------

def _format_tool_results_readable(tool_calls_log: list) -> str:
    """Convert tool call results into human-readable text.

    Called when the LLM fails to generate a text summary after tool calls.
    """
    parts = []

    for tc in tool_calls_log:
        name = tc.get("name", "")
        result_str = tc.get("result_preview", "")

        try:
            parsed = json.loads(result_str)
        except (json.JSONDecodeError, TypeError):
            parsed = None

        if not isinstance(parsed, dict):
            parts.append(f"[{name}] {result_str[:200]}")
            continue

        # Handle specific tool types
        if name == "current_time":
            r = parsed.get("result", parsed)
            date = r.get("date", "")
            time = r.get("time", "")
            weekday = r.get("weekday", "")
            parts.append(f"现在是 {date} {weekday} {time}")

        if name == "web_search":
            r = parsed.get("result", parsed)
            results = r.get("results", [])
            if results:
                for item in results[:5]:
                    title = item.get("title", "")
                    snippet = item.get("snippet", "")
                    url = item.get("url", "")
                    entry = f"- {title}"
                    if snippet:
                        entry += f"\n  {snippet[:100]}"
                    parts.append(entry)
            else:
                msg = r.get("message", "未找到结果")
                parts.append(f"搜索结果：{msg}")
                # Always show diagnostics so we can debug
                diagnostics = r.get("diagnostics", [])
                if diagnostics:
                    parts.append("调试信息：")
                    for d in diagnostics:
                        parts.append(f"  {d}")

        elif name in ("memory_add", "memory_replace", "memory_remove"):
            r = parsed.get("result", parsed)
            if "error" in parsed:
                parts.append(f"记忆操作失败：{parsed['error']}")
            else:
                parts.append(f"记忆已更新：{json.dumps(r, ensure_ascii=False)[:100]}")

        elif name in ("todo_write", "todo_read"):
            r = parsed.get("result", parsed)
            if isinstance(r, list):
                for item in r[:10]:
                    content = item.get("content", str(item))
                    status = item.get("status", "")
                    icon = {"pending": "○", "in_progress": "◐", "completed": "●"}.get(status, "○")
                    parts.append(f"{icon} {content}")
            elif isinstance(r, dict):
                parts.append(f"任务已更新：{json.dumps(r, ensure_ascii=False)[:100]}")

        elif name in ("skills_list", "skill_view"):
            r = parsed.get("result", parsed)
            skills = r.get("skills", r.get("result", []))
            if isinstance(skills, list):
                for s in skills[:5]:
                    if isinstance(s, dict):
                        parts.append(f"- {s.get('name', str(s))}: {s.get('description', '')[:80]}")
                    else:
                        parts.append(f"- {s}")

        elif name == "cronjob":
            r = parsed.get("result", parsed)
            parts.append(f"定时任务：{json.dumps(r, ensure_ascii=False)[:200]}")

        elif name == "list_files":
            r = parsed.get("result", parsed)
            entries = r.get("entries", [])
            for e in entries[:10]:
                etype = "📁" if e.get("type") == "directory" else "📄"
                parts.append(f"{etype} {e.get('name', '')} ({e.get('size', 0)} bytes)")

        elif name == "read_file":
            r = parsed.get("result", parsed)
            content = r.get("content", "")
            parts.append(content[:500] if content else "文件为空")

        else:
            # Generic fallback
            r = parsed.get("result", parsed)
            if "error" in parsed:
                parts.append(f"错误：{parsed['error']}")
            else:
                text = json.dumps(r, ensure_ascii=False)[:200]
                parts.append(f"[{name}] {text}")

    return "\n\n".join(parts)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _load_env_file(path: str) -> Dict[str, str]:
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
    sessions_dir = os.path.join(_hermes_home, "sessions")
    os.makedirs(sessions_dir, exist_ok=True)
    sid = session["id"]
    path = os.path.join(sessions_dir, f"{sid}.json")
    with open(path, "w") as f:
        json.dump(session, f, indent=2, default=str, ensure_ascii=False)


def _load_sessions_from_disk() -> None:
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


def _get_llm_config() -> tuple:
    model = _config.get("model", {}).get("default", DEFAULT_MODEL)
    provider = _config.get("model", {}).get("provider", "agnes")

    api_key = DEFAULT_API_KEY
    base_url = DEFAULT_BASE_URL

    user_key = _env_vars.get("OPENAI_API_KEY", "")
    user_url = _env_vars.get("OPENAI_BASE_URL", "")
    if user_key:
        api_key = user_key
    if user_url:
        base_url = user_url

    if "groq" in provider:
        base_url = "https://api.groq.com/openai/v1"
        if not user_key:
            api_key = _env_vars.get("GROQ_API_KEY", DEFAULT_API_KEY)
    elif "openai" in provider:
        base_url = "https://api.openai.com/v1"
        if not user_key:
            api_key = _env_vars.get("OPENAI_API_KEY", DEFAULT_API_KEY)
    elif "anthropic" in provider:
        base_url = "https://api.anthropic.com/v1"
        if not user_key:
            api_key = _env_vars.get("ANTHROPIC_API_KEY", DEFAULT_API_KEY)
    elif "google" in provider:
        base_url = "https://generativelanguage.googleapis.com/v1beta/openai"
        if not user_key:
            api_key = _env_vars.get("GOOGLE_API_KEY", DEFAULT_API_KEY)
    elif "openrouter" in provider:
        base_url = "https://openrouter.ai/api/v1"
        if not user_key:
            api_key = _env_vars.get("OPENROUTER_API_KEY", DEFAULT_API_KEY)
    elif "deepseek" in provider:
        base_url = "https://api.deepseek.com"
        if not user_key:
            api_key = _env_vars.get("DEEPSEEK_API_KEY", DEFAULT_API_KEY)
    elif "siliconflow" in provider:
        base_url = "https://api.siliconflow.cn/v1"
        if not user_key:
            api_key = _env_vars.get("SILICONFLOW_API_KEY", DEFAULT_API_KEY)

    return model, api_key, base_url


# ---------------------------------------------------------------------------
# LLM with Tool Calling (Agent Loop)
# ---------------------------------------------------------------------------

async def _call_llm_with_tools(
    messages: List[dict],
    model: str,
    api_key: str,
    base_url: str,
    tools: List[dict] = None,
    max_turns: int = MAX_TOOL_TURNS,
) -> Any:
    """Call LLM with tool support. Returns (full_text, tool_calls_log, error)."""

    url = f"{base_url.rstrip('/')}/chat/completions"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://hermes-agent.android",
        "X-Title": "Hermes Agent Android",
    }

    tool_calls_log = []
    current_messages = list(messages)
    full_text = ""
    tools_schema = tools  # Keep original for re-sending

    for turn in range(max_turns + 1):
        payload: dict = {
            "model": model,
            "messages": current_messages,
            "stream": False,
        }

        # Send tools schema on first turn; after tool results, don't send tools
        # so the LLM generates a text response instead of more tool calls
        if tools_schema and turn == 0:
            payload["tools"] = tools_schema
            payload["tool_choice"] = "auto"

        try:
            async with httpx.AsyncClient(timeout=httpx.Timeout(120.0, connect=30.0)) as client:
                response = await client.post(url, json=payload, headers=headers)

                if response.status_code != 200:
                    try:
                        error_json = response.json()
                        error_msg = error_json.get("error", {}).get("message", response.text)
                    except Exception:
                        error_msg = response.text
                    return full_text, tool_calls_log, f"API Error ({response.status_code}): {error_msg}"

                data = response.json()
                choice = data.get("choices", [{}])[0]
                message = choice.get("message", {})
                finish_reason = choice.get("finish_reason", "")

                # Collect text content
                content = message.get("content") or ""
                if content:
                    full_text += content

                # Check for tool calls
                tool_calls = message.get("tool_calls", [])

                if not tool_calls or finish_reason != "tool_calls":
                    # No more tool calls, we're done
                    break

                # Add assistant message with tool calls
                current_messages.append(message)

                # Process each tool call
                for tc in tool_calls:
                    tc_id = tc.get("id", str(uuid.uuid4()))
                    func = tc.get("function", {})
                    tool_name = func.get("name", "")
                    tool_args_str = func.get("arguments", "{}")

                    try:
                        tool_args = json.loads(tool_args_str) if isinstance(tool_args_str, str) else tool_args_str
                    except json.JSONDecodeError:
                        tool_args = {}

                    # Inject home directory for tools that need it
                    if tool_name in ("skills_list", "skill_view", "skill_manage"):
                        tool_args.setdefault("home", _hermes_home)
                    if tool_name == "list_files" and "path" not in tool_args:
                        tool_args["path"] = ""

                    # Dispatch tool
                    logger.info(f"Tool call: {tool_name}({tool_args})")
                    tool_result_str = _registry.dispatch(tool_name, tool_args)

                    # Log the tool call
                    tool_calls_log.append({
                        "name": tool_name,
                        "arguments": tool_args,
                        "result_preview": tool_result_str[:300],
                    })

                    # Add tool result to messages
                    current_messages.append({
                        "role": "tool",
                        "tool_call_id": tc_id,
                        "content": tool_result_str,
                    })

        except httpx.ConnectError as e:
            return full_text, tool_calls_log, f"Connection error: {e}"
        except Exception as e:
            logger.error(f"LLM call failed: {e}", exc_info=True)
            return full_text, tool_calls_log, str(e)

    # ---- Post-processing: ensure there's always a text response ----
    # If the LLM didn't generate text after tool calls, we need to ask it again
    # or generate a summary from tool results ourselves.
    if not full_text and tool_calls_log:
        logger.info("LLM returned no text after tool calls, requesting summary...")

        # Try one more LLM call asking for a summary
        summary_prompt = {
            "role": "user",
            "content": "请根据上面的工具调用结果，用中文给用户一个简洁有用的回复。不要提及工具或技术细节，直接回答用户的问题。"
        }
        current_messages.append(summary_prompt)

        payload = {
            "model": model,
            "messages": current_messages,
            "stream": False,
        }

        try:
            async with httpx.AsyncClient(timeout=httpx.Timeout(60.0, connect=15.0)) as client:
                response = await client.post(url, json=payload, headers=headers)
                if response.status_code == 200:
                    data = response.json()
                    content = data.get("choices", [{}])[0].get("message", {}).get("content", "")
                    if content:
                        full_text = content
                        logger.info(f"Summary generated: {len(full_text)} chars")
        except Exception as e:
            logger.error(f"Summary call failed: {e}")

        # Final fallback: generate summary from tool results directly
        if not full_text:
            parts = []
            for tc in tool_calls_log:
                name = tc["name"]
                result = tc.get("result_preview", "")
                # Try to parse the result for readable content
                try:
                    parsed = json.loads(result)
                    if isinstance(parsed, dict):
                        # web_search results
                        if "result" in parsed:
                            r = parsed["result"]
                            if isinstance(r, dict) and "results" in r:
                                for item in r["results"][:5]:
                                    title = item.get("title", "")
                                    snippet = item.get("snippet", "")
                                    url = item.get("url", "")
                                    if title:
                                        entry = f"- {title}"
                                        if snippet:
                                            entry += f"：{snippet[:100]}"
                                        parts.append(entry)
                            elif isinstance(r, dict) and "error" in r:
                                parts.append(f"错误: {r['error']}")
                            else:
                                parts.append(str(r)[:200])
                        elif "error" in parsed:
                            parts.append(f"工具 {name} 错误: {parsed['error']}")
                        else:
                            parts.append(str(parsed)[:200])
                except (json.JSONDecodeError, TypeError):
                    if result:
                        parts.append(result[:150])

            if parts:
                full_text = "根据搜索结果：\n\n" + "\n".join(parts)

    return full_text, tool_calls_log, None


async def _call_llm_stream(messages: List[dict], model: str, api_key: str, base_url: str):
    """Stream chat completions from LLM provider via httpx (no tool calling in stream mode)."""
    url = f"{base_url.rstrip('/')}/chat/completions"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://hermes-agent.android",
        "X-Title": "Hermes Agent Android",
    }
    payload = {
        "model": model,
        "messages": messages,
        "stream": True,
    }

    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(120.0, connect=30.0)) as client:
            async with client.stream("POST", url, json=payload, headers=headers) as response:
                if response.status_code != 200:
                    error_text = await response.aread()
                    try:
                        error_json = json.loads(error_text)
                        error_msg = error_json.get("error", {}).get("message", error_text.decode())
                    except Exception:
                        error_msg = error_text.decode()
                    yield f'data: {json.dumps({"type": "error", "data": {"text": f"API Error ({response.status_code}): {error_msg}"}}, ensure_ascii=False)}\n\n'
                    return

                async for line in response.aiter_lines():
                    if not line.startswith("data: "):
                        continue
                    data_str = line[6:].strip()
                    if data_str == "[DONE]":
                        break
                    try:
                        chunk = json.loads(data_str)
                        delta = chunk.get("choices", [{}])[0].get("delta", {})
                        content = delta.get("content", "")
                        if content:
                            yield f'data: {json.dumps({"type": "text_delta", "data": {"text": content}}, ensure_ascii=False)}\n\n'
                    except json.JSONDecodeError:
                        pass

        yield 'data: {"type": "done", "data": {}}\n\n'

    except httpx.ConnectError as e:
        yield f'data: {json.dumps({"type": "error", "data": {"text": f"Connection error: {e}"}}, ensure_ascii=False)}\n\n'
    except Exception as e:
        logger.error(f"LLM call failed: {e}")
        yield f'data: {json.dumps({"type": "error", "data": {"text": str(e)}}, ensure_ascii=False)}\n\n'


# ---------------------------------------------------------------------------
# FastAPI app
# ---------------------------------------------------------------------------


def create_app() -> FastAPI:
    app = FastAPI(title="Hermes Agent Android", version="0.3.0")

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
        tool_names = _registry.get_all_tool_names() if _registry else []
        return {
            "status": "running",
            "version": "0.3.0-android",
            "uptime": int(time.time() - _start_time),
            "active_sessions": len(_sessions),
            "tools_count": len(tool_names),
            "tools": tool_names,
            "memory_enabled": True,
            "skills_enabled": True,
            "cron_enabled": True,
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

    # ----- Chat with Tool Calling -----

    @app.post("/api/chat")
    async def api_chat(request: Request):
        body = await request.json()
        session_id = body.get("session_id")
        message = body.get("message", "")
        system_prompt = body.get("system_prompt", "")
        enable_tools = body.get("enable_tools", True)

        if not message:
            raise HTTPException(400, "message is required")

        if not session_id or session_id not in _sessions:
            session_id = str(uuid.uuid4())
            _sessions[session_id] = {
                "id": session_id,
                "title": message[:50],
                "model": _config.get("model", {}).get("default", DEFAULT_MODEL),
                "provider": _config.get("model", {}).get("provider", "agnes"),
                "created_at": _now_iso(),
                "updated_at": _now_iso(),
                "message_count": 0,
                "token_count": 0,
                "messages": [],
            }

        session = _sessions[session_id]

        session["messages"].append({
            "id": str(uuid.uuid4()),
            "role": "user",
            "content": message,
            "timestamp": _now_iso(),
        })
        session["message_count"] += 1
        session["updated_at"] = _now_iso()

        # Build LLM messages
        llm_messages = []

        # Build default system prompt with tool awareness
        default_system = (
            "你是 Hermes 智能助手，一个自我进化的 AI Agent。你运行在 Android 设备上，具备以下核心能力：\n"
            "\n"
            "## 你的工具\n"
            "你可以通过工具调用（tool calls）来执行操作，而不仅仅是聊天：\n"
            "- **获取时间** (current_time)：获取当前日期、时间和星期几。当你需要知道今天几号或星期几时，一定要先调用这个工具！\n"
            "- **记忆系统** (memory_add/memory_replace/memory_remove)：记住用户的重要信息和偏好，持久化保存\n"
            "- **任务管理** (todo_write/todo_read)：创建和管理待办事项列表\n"
            "- **技能系统** (skills_list/skill_view/skill_manage)：查看、创建和管理可复用的技能\n"
            "- **定时任务** (cronjob)：创建和管理定时执行的任务\n"
            "- **网页搜索** (web_search)：搜索网络获取最新信息\n"
            "- **网页读取** (web_fetch)：读取网页内容\n"
            "- **文件操作** (read_file/write_file/list_files)：读写本地文件\n"
            "\n"
            "## 使用原则\n"
            "1. 当用户问\"今天是几号\"、\"现在几点\"、\"星期几\"时，必须先调用 current_time 工具获取准确时间，不要猜测！\n"
            "2. 搜索时必须使用 current_time 返回的真实年份，不要把年份改成你训练数据中的年份！例如现在是2026年就搜索2026年，不要改成2025年。\n"
            "3. 主动使用工具：当用户分享重要信息时，用 memory_add 记住它；当用户提到待办事项时，用 todo_write 记录\n"
            "4. 当需要最新信息时，用 web_search 搜索；当用户给你网址时，用 web_fetch 读取\n"
            "5. 技能是可复用的操作模板，可以帮助你更好地完成特定类型的任务\n"
            "6. 记忆分为两种：一般记忆(memory)和用户画像(user)，后者用于存储用户的偏好和个人信息\n"
            "7. 如果用户要求定时执行某事，使用 cronjob 工具创建定时任务\n"
            "8. 文件操作限制在 Hermes 主目录内，保证安全\n"
            "9. 用中文回复用户\n"
            "10. 你已经拥有上述工具，不需要说\"我没有工具\"。直接使用工具调用来完成用户的请求。"
        )

        sys_parts = [default_system]

        # Add user's custom system prompt
        if system_prompt:
            sys_parts.append(system_prompt)

        # Add memory context
        from tools.memory_tool import get_memory_store
        mem_store = get_memory_store()
        if mem_store:
            mem_context = mem_store.format_for_system_prompt()
            if mem_context:
                sys_parts.append(mem_context)

        # Add todo context
        from tools.todo_tool import _get_store
        todo_store = _get_store(session_id)
        if todo_store and todo_store.has_items():
            todo_context = todo_store.format_for_injection()
            if todo_context:
                sys_parts.append(todo_context)

        llm_messages.append({"role": "system", "content": "\n\n".join(sys_parts)})

        for m in session["messages"][-20:]:
            llm_messages.append({"role": m["role"], "content": m["content"]})

        model, api_key, base_url = _get_llm_config()

        if not api_key:
            error_msg = "请先在设置中配置 API 密钥。"
            session["messages"].append({
                "id": str(uuid.uuid4()),
                "role": "assistant",
                "content": error_msg,
                "timestamp": _now_iso(),
            })
            session["message_count"] += 1
            _persist_session(session)
            return StreamingResponse(
                iter([f'data: {json.dumps({"type": "text_delta", "data": {"text": error_msg}}, ensure_ascii=False)}\n\n',
                      'data: {"type": "done", "data": {}}\n\n']),
                media_type="text/event-stream",
            )

        # Get tool definitions if enabled
        tools_schema = None
        if enable_tools and _registry:
            tools_schema = _registry.get_definitions()

        # Use non-streaming call with tool support
        full_text, tool_calls_log, error = await _call_llm_with_tools(
            llm_messages, model, api_key, base_url, tools=tools_schema,
        )

        if error and not full_text:
            full_text = error

        # Format response - only show the AI's text, NOT raw tool JSON
        response_text = full_text

        # If the AI didn't generate text after tool calls, create a readable summary
        if not response_text and tool_calls_log:
            response_text = _format_tool_results_readable(tool_calls_log)

        # Save assistant message
        session["messages"].append({
            "id": str(uuid.uuid4()),
            "role": "assistant",
            "content": response_text,
            "timestamp": _now_iso(),
            "model": model,
            "tool_calls": tool_calls_log,
        })
        session["message_count"] += 1
        session["updated_at"] = _now_iso()
        _persist_session(session)

        # Return as SSE for compatibility with existing frontend
        async def generate():
            # Send text in chunks for better UX
            chunk_size = 50
            for i in range(0, len(response_text), chunk_size):
                chunk = response_text[i:i + chunk_size]
                yield f'data: {json.dumps({"type": "text_delta", "data": {"text": chunk}}, ensure_ascii=False)}\n\n'
                await asyncio.sleep(0.01)

            if tool_calls_log:
                yield f'data: {json.dumps({"type": "tool_calls", "data": {"calls": tool_calls_log}}, ensure_ascii=False)}\n\n'

            yield 'data: {"type": "done", "data": {}}\n\n'

        return StreamingResponse(
            generate(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "X-Accel-Buffering": "no",
                "Connection": "keep-alive",
            },
        )

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
            "model": _config.get("model", {}).get("default", DEFAULT_MODEL),
            "provider": _config.get("model", {}).get("provider", "agnes"),
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
            "OPENAI_API_KEY", "ANTHROPIC_API_KEY", "GOOGLE_API_KEY",
            "GROQ_API_KEY", "DEEPSEEK_API_KEY", "SILICONFLOW_API_KEY",
            "OPENROUTER_API_KEY", "OPENAI_BASE_URL",
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
            {"id": "agnes-2.0-flash", "name": "Agnes 2.0 Flash (免费)", "provider": "agnes",
             "context_length": 128000, "supports_vision": False, "supports_tools": True},
            {"id": "gpt-4o", "name": "GPT-4o", "provider": "openai",
             "context_length": 128000, "supports_vision": True, "supports_tools": True},
            {"id": "gpt-4o-mini", "name": "GPT-4o Mini", "provider": "openai",
             "context_length": 128000, "supports_vision": True, "supports_tools": True},
            {"id": "gpt-4.1", "name": "GPT-4.1", "provider": "openai",
             "context_length": 1047576, "supports_vision": True, "supports_tools": True},
            {"id": "gpt-4.1-mini", "name": "GPT-4.1 Mini", "provider": "openai",
             "context_length": 1047576, "supports_vision": True, "supports_tools": True},
            {"id": "claude-sonnet-4-20250514", "name": "Claude Sonnet 4", "provider": "anthropic",
             "context_length": 200000, "supports_vision": True, "supports_tools": True},
            {"id": "claude-3-5-haiku-20241022", "name": "Claude 3.5 Haiku", "provider": "anthropic",
             "context_length": 200000, "supports_vision": True, "supports_tools": True},
            {"id": "gemini-2.5-pro", "name": "Gemini 2.5 Pro", "provider": "google",
             "context_length": 1048576, "supports_vision": True, "supports_tools": True},
            {"id": "gemini-2.5-flash", "name": "Gemini 2.5 Flash", "provider": "google",
             "context_length": 1048576, "supports_vision": True, "supports_tools": True},
            {"id": "deepseek-chat", "name": "DeepSeek V3", "provider": "deepseek",
             "context_length": 65536, "supports_vision": False, "supports_tools": True},
            {"id": "deepseek-reasoner", "name": "DeepSeek R1", "provider": "deepseek",
             "context_length": 65536, "supports_vision": False, "supports_tools": True},
        ]

    @app.get("/api/model/current")
    async def api_model_current():
        return {
            "model": _config.get("model", {}).get("default", DEFAULT_MODEL),
            "provider": _config.get("model", {}).get("provider", "agnes"),
        }

    @app.post("/api/model/set")
    async def api_model_set(request: Request):
        global _config
        body = await request.json()
        model = body.get("model", DEFAULT_MODEL)
        provider = body.get("provider", "agnes")
        _config.setdefault("model", {})["default"] = model
        _config["model"]["provider"] = provider
        _save_config(os.path.join(_hermes_home, "config.yaml"), _config)
        return {"model": model, "provider": provider}

    # ----- Tools -----

    @app.get("/api/tools")
    async def api_list_tools():
        if not _registry:
            return []
        tools = []
        for name in _registry.get_all_tool_names():
            entry = _registry.get_entry(name)
            schema = entry.schema if entry else {}
            func = schema.get("function", {})
            tools.append({
                "name": name,
                "description": func.get("description", ""),
                "parameters": func.get("parameters", {}),
                "emoji": entry.emoji if entry else "",
            })
        return tools

    @app.get("/api/tools/toolsets")
    async def api_list_toolsets():
        return [
            {"id": "time", "name": "时间查询", "emoji": "🕐", "tools": ["current_time"]},
            {"id": "memory", "name": "记忆系统", "emoji": "🧠", "tools": ["memory_add", "memory_replace", "memory_remove"]},
            {"id": "todo", "name": "任务管理", "emoji": "📋", "tools": ["todo_write", "todo_read"]},
            {"id": "skills", "name": "技能系统", "emoji": "🎯", "tools": ["skills_list", "skill_view", "skill_manage"]},
            {"id": "cron", "name": "定时任务", "emoji": "⏰", "tools": ["cronjob"]},
            {"id": "search", "name": "网页搜索", "emoji": "🔍", "tools": ["web_search", "web_fetch"]},
            {"id": "files", "name": "文件操作", "emoji": "📄", "tools": ["read_file", "write_file", "list_files"]},
        ]

    @app.post("/api/tools/dispatch")
    async def api_dispatch_tool(request: Request):
        """Manually dispatch a tool call."""
        body = await request.json()
        name = body.get("name")
        arguments = body.get("arguments", {})
        if not name:
            raise HTTPException(400, "name is required")

        # Inject home for skills tools
        if name in ("skills_list", "skill_view", "skill_manage"):
            arguments.setdefault("home", _hermes_home)
        if name == "list_files" and "path" not in arguments:
            arguments["path"] = ""

        result = _registry.dispatch(name, arguments)
        try:
            return JSONResponse(content=json.loads(result))
        except json.JSONDecodeError:
            return JSONResponse(content={"raw": result})

    # ----- Memory -----

    @app.get("/api/memory")
    async def api_get_memory():
        from tools.memory_tool import get_memory_store
        store = get_memory_store()
        if not store:
            return {"enabled": False}
        data = store.get_all()
        return {
            "enabled": True,
            "memory_entries": data["memory"],
            "user_entries": data["user"],
            "memory_count": len(data["memory"]),
            "user_count": len(data["user"]),
        }

    @app.post("/memory/add")
    async def api_memory_add(request: Request):
        from tools.memory_tool import get_memory_store
        store = get_memory_store()
        if not store:
            raise HTTPException(500, "Memory not initialized")
        body = await request.json()
        return JSONResponse(content=json.loads(store.add(
            body.get("entry", ""), body.get("category", "memory")
        )))

    @app.post("/memory/replace")
    async def api_memory_replace(request: Request):
        from tools.memory_tool import get_memory_store
        store = get_memory_store()
        if not store:
            raise HTTPException(500, "Memory not initialized")
        body = await request.json()
        return JSONResponse(content=json.loads(store.replace(
            body.get("old", ""), body.get("new", ""), body.get("category", "memory")
        )))

    @app.post("/memory/remove")
    async def api_memory_remove(request: Request):
        from tools.memory_tool import get_memory_store
        store = get_memory_store()
        if not store:
            raise HTTPException(500, "Memory not initialized")
        body = await request.json()
        return JSONResponse(content=json.loads(store.remove(
            body.get("entry", ""), body.get("category", "memory")
        )))

    @app.post("/memory/reload")
    async def api_memory_reload():
        from tools.memory_tool import get_memory_store
        store = get_memory_store()
        if store:
            store.load_from_disk()
        return {"ok": True}

    # ----- Skills -----

    @app.get("/api/skills")
    async def api_list_skills():
        from tools.skills_tool import skills_list
        result = skills_list(home=_hermes_home)
        try:
            data = json.loads(result)
            return data.get("result", data)
        except json.JSONDecodeError:
            return []

    @app.get("/api/skills/{name}")
    async def api_get_skill(name: str, file: str = ""):
        from tools.skills_tool import skill_view
        result = skill_view(name=name, home=_hermes_home, file=file)
        try:
            return JSONResponse(content=json.loads(result))
        except json.JSONDecodeError:
            return JSONResponse(content={"raw": result})

    @app.post("/api/skills/manage")
    async def api_manage_skill(request: Request):
        from tools.skill_manager_tool import skill_manage
        body = await request.json()
        body["home"] = _hermes_home
        result = skill_manage(**body)
        try:
            return JSONResponse(content=json.loads(result))
        except json.JSONDecodeError:
            return JSONResponse(content={"raw": result})

    @app.delete("/api/skills/{name}")
    async def api_delete_skill(name: str):
        from tools.skill_manager_tool import skill_manage
        result = skill_manage(action="delete", name=name, home=_hermes_home)
        try:
            return JSONResponse(content=json.loads(result))
        except json.JSONDecodeError:
            return JSONResponse(content={"raw": result})

    @app.get("/api/skills/hub/search")
    async def api_skills_hub_search(q: str = ""):
        return []

    # ----- Cron Jobs -----

    @app.get("/api/cron/jobs")
    async def api_list_cron():
        from tools.cron import jobs as cron_jobs
        return cron_jobs.list_jobs()

    @app.post("/api/cron/jobs")
    async def api_create_cron(request: Request):
        from tools.cron import jobs as cron_jobs
        body = await request.json()
        try:
            job = cron_jobs.create_job(
                name=body.get("name", ""),
                schedule=body.get("schedule", ""),
                prompt=body.get("prompt", ""),
                model=body.get("model", ""),
                skill=body.get("skill", ""),
                skill_input=body.get("skill_input", ""),
            )
            if body.get("paused"):
                cron_jobs.pause_job(job["id"])
            return job
        except Exception as e:
            raise HTTPException(400, str(e))

    @app.post("/api/cron/jobs/{job_id}/pause")
    async def api_pause_cron(job_id: str):
        from tools.cron import jobs as cron_jobs
        job = cron_jobs.pause_job(job_id)
        if not job:
            raise HTTPException(404, "Job not found")
        return job

    @app.post("/api/cron/jobs/{job_id}/resume")
    async def api_resume_cron(job_id: str):
        from tools.cron import jobs as cron_jobs
        job = cron_jobs.resume_job(job_id)
        if not job:
            raise HTTPException(404, "Job not found")
        return job

    @app.delete("/api/cron/jobs/{job_id}")
    async def api_delete_cron(job_id: str):
        from tools.cron import jobs as cron_jobs
        ok = cron_jobs.remove_job(job_id)
        if not ok:
            raise HTTPException(404, "Job not found")
        return {"ok": True}

    @app.post("/api/cron/jobs/{job_id}/run")
    async def api_run_cron(job_id: str):
        from tools.cron import jobs as cron_jobs
        cron_jobs.mark_job_run(job_id)
        job = cron_jobs.get_job(job_id)
        if not job:
            raise HTTPException(404, "Job not found")
        return {"ok": True, "job": job}

    # ----- MCP -----

    @app.get("/api/mcp/servers")
    async def api_list_mcp():
        return []

    # ----- Logs -----

    @app.get("/api/logs")
    async def api_get_logs():
        return []

    # ----- Debug: Search -----

    @app.get("/api/debug/search")
    async def api_debug_search(q: str = "test"):
        """Debug endpoint: test Baidu search and return raw HTML stats."""
        import tools.web_search_tool as ws
        ws._search_diagnostics = []
        results = ws._search_baidu(q, 5)
        return {
            "query": q,
            "results": results,
            "result_count": len(results),
            "diagnostics": ws._search_diagnostics,
        }

    @app.get("/api/debug/baidu_html")
    async def api_debug_baidu_html(q: str = "test", chars: int = 2000):
        """Debug: fetch Baidu HTML and return a sample + stats."""
        try:
            url = "https://www.baidu.com/s"
            params = {"wd": q, "rn": "10", "ie": "utf-8"}
            with httpx.Client(
                timeout=httpx.Timeout(15.0, connect=8.0),
                follow_redirects=True,
                headers=ws.HEADERS_DESKTOP,
            ) as client:
                resp = client.get(url, params=params)
                html = resp.text
                # Count h3 tags
                h3_count = len(re.findall(r'<h3', html))
                # Count all links
                link_count = len(re.findall(r'<a[^>]*href=', html))
                # Count baidu.com/link
                baidu_link_count = len(re.findall(r'baidu\.com/link', html))
                # Sample of HTML
                sample = html[:chars]
                return {
                    "query": q,
                    "http_status": resp.status_code,
                    "html_length": len(html),
                    "h3_count": h3_count,
                    "link_count": link_count,
                    "baidu_link_count": baidu_link_count,
                    "has_captcha": "验证码" in html or "captcha" in html.lower(),
                    "has_login_redirect": "passport.baidu.com" in html,
                    "title": re.search(r'<title>(.*?)</title>', html).group(1) if re.search(r'<title>(.*?)</title>', html) else "",
                    "html_sample": sample,
                }
        except Exception as e:
            return {"error": str(e)}

    return app


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def start_server() -> None:
    global _hermes_home, _config, _env_vars, _registry

    from android_bootstrap import bootstrap
    _hermes_home = bootstrap()

    _config = _load_config(os.path.join(_hermes_home, "config.yaml"))
    if not _config:
        _config = DEFAULT_CONFIG.copy()
        _save_config(os.path.join(_hermes_home, "config.yaml"), _config)

    # Force-update model config to built-in Agnes AI defaults
    if _config.get("model", {}).get("default", "") != DEFAULT_MODEL:
        _config.setdefault("model", {})["default"] = DEFAULT_MODEL
        _config["model"]["provider"] = "agnes"
        _save_config(os.path.join(_hermes_home, "config.yaml"), _config)

    _env_vars = _load_env_file(os.path.join(_hermes_home, ".env"))
    for k, v in _env_vars.items():
        os.environ.setdefault(k, v)

    _load_sessions_from_disk()

    # Initialize tools system
    logger.info("Initializing tool system...")
    import tools  # Triggers all tool registrations
    _registry = tools.registry

    # Initialize memory
    from tools.memory_tool import init_memory
    init_memory(_hermes_home)
    logger.info("Memory system initialized")

    # Initialize cron scheduler
    from tools.cron import jobs as cron_jobs
    from tools.cronjob_tools import set_home as cron_set_home
    cron_set_home(_hermes_home)
    cron_jobs.init_jobs(_hermes_home)
    logger.info("Cron scheduler initialized")

    # Initialize file tools
    from tools.file_tools import set_home as file_set_home
    file_set_home(_hermes_home)
    logger.info("File tools initialized")

    # Ensure skills directory exists
    os.makedirs(os.path.join(_hermes_home, "skills"), exist_ok=True)

    logger.info(f"Hermes home: {_hermes_home}")
    logger.info(f"Loaded {len(_sessions)} sessions, {len(_env_vars)} env vars")
    logger.info(f"Registered tools: {_registry.get_all_tool_names()}")

    app = create_app()
    logger.info("Starting Hermes server v0.3.0 on 127.0.0.1:9119")

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
    try:
        import urllib.request
        req = urllib.request.Request("http://127.0.0.1:9119/api/status")
        with urllib.request.urlopen(req, timeout=2) as resp:
            return resp.read().decode()
    except Exception:
        return '{"status": "starting"}'
