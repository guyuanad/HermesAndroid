"""Hermes Agent Android bootstrap - initialize environment before server start."""

import os
import sys


def get_hermes_home() -> str:
    """Get or create the Hermes home directory."""
    home = os.path.expanduser("~/.hermes")
    os.makedirs(home, exist_ok=True)
    return home


def ensure_directories(home: str) -> None:
    """Create required subdirectories."""
    dirs = [
        "skills",
        "logs",
        "sessions",
        "cron",
        "mcp",
        "plugins",
        "themes",
    ]
    for d in dirs:
        os.makedirs(os.path.join(home, d), exist_ok=True)


def ensure_config(home: str) -> None:
    """Create default config.yaml if not exists."""
    config_path = os.path.join(home, "config.yaml")
    if not os.path.exists(config_path):
        default_config = {
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
        try:
            import yaml
            with open(config_path, "w") as f:
                yaml.dump(default_config, f, default_flow_style=False)
        except Exception:
            with open(config_path, "w") as f:
                f.write("model:\n  default: openrouter/auto\n  provider: auto\n")


def ensure_env(home: str) -> None:
    """Create .env file if not exists."""
    env_path = os.path.join(home, ".env")
    if not os.path.exists(env_path):
        with open(env_path, "w") as f:
            f.write("# Hermes Agent Environment Variables\n")
            f.write("# Add your API keys below:\n")
            f.write("# OPENROUTER_API_KEY=sk-...\n")
            f.write("# ANTHROPIC_API_KEY=sk-...\n")
            f.write("# GOOGLE_API_KEY=...\n")


def bootstrap() -> str:
    """Full bootstrap - returns the Hermes home path."""
    home = get_hermes_home()
    ensure_directories(home)
    ensure_config(home)
    ensure_env(home)
    os.environ.setdefault("HERMES_HOME", home)
    return home
