"""Web Search Tool for Hermes Android.

Provides web search capability using httpx to query search engines.
Supports multiple free search backends (DuckDuckGo, Wikipedia).
No API key required.
"""

from __future__ import annotations

import json
import logging
import re
import urllib.parse
from typing import Any, Dict, List, Optional

import httpx

from tools.registry import registry, tool_error, tool_result

logger = logging.getLogger("hermes.tools.web_search")

# ---------------------------------------------------------------------------
# DuckDuckGo Instant Answer API (free, no key)
# ---------------------------------------------------------------------------

DDG_API = "https://api.duckduckgo.com/"
WIKI_API = "https://zh.wikipedia.org/api/rest_v1/page/summary/"


def _search_duckduckgo(query: str, max_results: int = 5) -> List[Dict[str, str]]:
    """Search DuckDuckGo Instant Answer API."""
    results = []
    try:
        params = {
            "q": query,
            "format": "json",
            "no_html": 1,
            "skip_disambig": 1,
        }
        with httpx.Client(timeout=httpx.Timeout(15.0, connect=5.0)) as client:
            resp = client.get(DDG_API, params=params)
            if resp.status_code != 200:
                logger.warning(f"DDG API returned {resp.status_code}")
                return results

            data = resp.json()

            # Abstract (direct answer)
            if data.get("AbstractText"):
                results.append({
                    "title": data.get("AbstractTitle", query),
                    "url": data.get("AbstractURL", ""),
                    "snippet": data.get("AbstractText", ""),
                    "source": data.get("AbstractSource", "DuckDuckGo"),
                })

            # Related topics
            for topic in data.get("RelatedTopics", [])[:max_results]:
                if isinstance(topic, dict) and topic.get("Text"):
                    results.append({
                        "title": topic.get("Text", "")[:80],
                        "url": topic.get("FirstURL", ""),
                        "snippet": topic.get("Text", ""),
                        "source": "DuckDuckGo",
                    })

            # Infobox
            if data.get("Infobox"):
                for item in data.get("Infobox", {}).get("content", [])[:3]:
                    if item.get("label") and item.get("value"):
                        results.append({
                            "title": item.get("label", ""),
                            "url": "",
                            "snippet": f"{item['label']}: {item['value']}",
                            "source": data.get("Infobox", {}).get("meta", {}).get("src", ""),
                        })

    except Exception as e:
        logger.error(f"DuckDuckGo search error: {e}")

    return results[:max_results]


def _search_wikipedia(query: str) -> Optional[Dict[str, str]]:
    """Search Wikipedia for a summary of the given topic."""
    try:
        # URL encode the query for Chinese characters
        encoded = urllib.parse.quote(query, safe="")
        url = f"{WIKI_API}{encoded}"
        with httpx.Client(timeout=httpx.Timeout(10.0, connect=5.0)) as client:
            resp = client.get(url)
            if resp.status_code != 200:
                return None

            data = resp.json()
            return {
                "title": data.get("title", query),
                "url": data.get("content_urls", {}).get("desktop", {}).get("page", ""),
                "snippet": data.get("extract", ""),
                "source": "Wikipedia",
            }
    except Exception as e:
        logger.error(f"Wikipedia search error: {e}")
        return None


def _fetch_url(url: str, max_chars: int = 5000) -> str:
    """Fetch and extract text content from a URL."""
    try:
        with httpx.Client(
            timeout=httpx.Timeout(15.0, connect=5.0),
            follow_redirects=True,
            headers={"User-Agent": "Mozilla/5.0 (Android) HermesAgent/1.0"},
        ) as client:
            resp = client.get(url)
            if resp.status_code != 200:
                return f"HTTP Error: {resp.status_code}"

            content_type = resp.headers.get("content-type", "")
            if "text/html" not in content_type and "text/plain" not in content_type:
                return f"Unsupported content type: {content_type}"

            text = resp.text

            # Basic HTML stripping for HTML content
            if "text/html" in content_type:
                # Remove script and style tags and their contents
                text = re.sub(r"<script[^>]*>.*?</script>", "", text, flags=re.DOTALL | re.IGNORECASE)
                text = re.sub(r"<style[^>]*>.*?</style>", "", text, flags=re.DOTALL | re.IGNORECASE)
                # Remove HTML tags
                text = re.sub(r"<[^>]+>", " ", text)
                # Clean up whitespace
                text = re.sub(r"\s+", " ", text).strip()
                # Decode HTML entities
                text = text.replace("&nbsp;", " ").replace("&amp;", "&").replace("&lt;", "<").replace("&gt;", ">")
                text = text.replace("&quot;", '"').replace("&#39;", "'")

            if len(text) > max_chars:
                text = text[:max_chars] + "..."

            return text

    except Exception as e:
        return f"Error fetching URL: {e}"


# ---------------------------------------------------------------------------
# Tool handlers
# ---------------------------------------------------------------------------

def web_search(query: str, max_results: int = 5) -> str:
    """Search the web for information.

    Args:
        query: Search query string
        max_results: Maximum number of results to return
    """
    if not query.strip():
        return tool_error("Search query is required")

    all_results = []

    # Try DuckDuckGo
    ddg_results = _search_duckduckgo(query, max_results)
    all_results.extend(ddg_results)

    # Try Wikipedia as supplementary
    wiki_result = _search_wikipedia(query)
    if wiki_result and wiki_result.get("snippet"):
        # Avoid duplicates
        existing_snippets = [r.get("snippet", "")[:50] for r in all_results]
        if wiki_result["snippet"][:50] not in existing_snippets:
            all_results.append(wiki_result)

    if not all_results:
        return tool_result({
            "query": query,
            "results": [],
            "count": 0,
            "message": "未找到相关结果，请尝试不同的搜索词",
        })

    return tool_result({
        "query": query,
        "results": all_results[:max_results],
        "count": len(all_results[:max_results]),
    })


def web_fetch(url: str, max_chars: int = 5000) -> str:
    """Fetch and read the content of a web page.

    Args:
        url: URL to fetch
        max_chars: Maximum characters to return
    """
    if not url.strip():
        return tool_error("URL is required")

    # Basic URL validation
    if not url.startswith(("http://", "https://")):
        return tool_error("URL must start with http:// or https://")

    content = _fetch_url(url, max_chars)

    return tool_result({
        "url": url,
        "content": content,
        "length": len(content),
    })


# ---------------------------------------------------------------------------
# Registration
# ---------------------------------------------------------------------------

registry.register(
    name="web_search",
    handler=web_search,
    schema={
        "type": "function",
        "function": {
            "name": "web_search",
            "description": "Search the web for information using DuckDuckGo and Wikipedia. Returns relevant results with titles, URLs, and snippets.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Search query in natural language",
                    },
                    "max_results": {
                        "type": "integer",
                        "description": "Maximum number of results (default: 5)",
                    },
                },
                "required": ["query"],
            },
        },
    },
    description="Search the web for information",
    emoji="🔍",
)

registry.register(
    name="web_fetch",
    handler=web_fetch,
    schema={
        "type": "function",
        "function": {
            "name": "web_fetch",
            "description": "Fetch and read the content of a web page. Returns the text content of the page.",
            "parameters": {
                "type": "object",
                "properties": {
                    "url": {
                        "type": "string",
                        "description": "URL to fetch",
                    },
                    "max_chars": {
                        "type": "integer",
                        "description": "Maximum characters to return (default: 5000)",
                    },
                },
                "required": ["url"],
            },
        },
    },
    description="Fetch and read web page content",
    emoji="🌐",
)
