"""Current Time Tool for Hermes Android.

Provides the current date and time to the AI.
Simple but essential - without this the AI doesn't know what day it is.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone, timedelta

from tools.registry import registry, tool_result

# Use China Standard Time (UTC+8)
CST = timezone(timedelta(hours=8))


def current_time() -> str:
    """Get the current date and time.

    Returns the current date, time, day of week, and timezone info.
    """
    now = datetime.now(CST)

    weekday_names = ["星期一", "星期二", "星期三", "星期四", "星期五", "星期六", "星期日"]

    return tool_result({
        "date": now.strftime("%Y年%m月%d日"),
        "time": now.strftime("%H:%M:%S"),
        "datetime": now.strftime("%Y-%m-%d %H:%M:%S"),
        "weekday": weekday_names[now.weekday()],
        "timezone": "CST (UTC+8)",
        "iso": now.isoformat(),
        "year": now.year,
        "month": now.month,
        "day": now.day,
        "hour": now.hour,
    })


registry.register(
    name="current_time",
    handler=current_time,
    schema={
        "type": "function",
        "function": {
            "name": "current_time",
            "description": "获取当前日期和时间。当你需要知道今天几号、星期几、现在几点时使用此工具。",
            "parameters": {
                "type": "object",
                "properties": {},
                "required": [],
            },
        },
    },
    description="获取当前日期和时间",
    emoji="🕐",
)
