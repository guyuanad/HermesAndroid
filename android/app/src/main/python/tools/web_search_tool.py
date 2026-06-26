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
DDG_HTML = "https://html.duckduckgo.com/html/"
WIKI_API = "https://zh.wikipedia.org/api/rest_v1/page/summary/"
WIKI_SEARCH = "https://zh.wikipedia.org/w/api.php"


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


def _search_duckduckgo_html(query: str, max_results: int = 8) -> List[Dict[str, str]]:
    """Search DuckDuckGo via HTML parsing for full web results.

    The Instant Answer API only returns direct answers, not general
    web search results. This method parses the HTML search page to
    get actual search result links and snippets.
    """
    results = []
    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Linux; Android 14) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0 Mobile Safari/537.36",
        }
        data = {"q": query, "b": ""}
        with httpx.Client(timeout=httpx.Timeout(15.0, connect=5.0), follow_redirects=True) as client:
            resp = client.post(DDG_HTML, data=data, headers=headers)
            if resp.status_code != 200:
                logger.warning(f"DDG HTML returned {resp.status_code}")
                return results

            html = resp.text

            # Parse search results from HTML
            # DDG HTML uses: <a rel="nofollow" class="result__a" href="...">Title</a>
            # and: <a class="result__snippet" ...>Snippet</a>
            # and: <span class="result__url__domain">domain</span>

            import re as _re

            # Find result blocks
            result_pattern = _re.compile(
                r'<a[^>]*class="result__a"[^>]*href="([^"]*)"[^>]*>(.*?)</a>'
                r'.*?'
                r'(?:<a[^>]*class="result__snippet"[^>]*>(.*?)</a>|<td[^>]*class="result__snippet[^"]*"[^>]*>(.*?)</td>)?',
                _re.DOTALL,
            )

            for match in result_pattern.finditer(html):
                url = match.group(1).strip()
                title = _re.sub(r"<[^>]+>", "", match.group(2)).strip()
                snippet = ""
                if match.group(3):
                    snippet = _re.sub(r"<[^>]+>", "", match.group(3)).strip()
                elif match.group(4):
                    snippet = _re.sub(r"<[^>]+>", "", match.group(4)).strip()

                # Skip ad results
                if "duckduckgo.com" in url and "uddg=" in url:
                    # Extract actual URL from redirect
                    uddg_match = _re.search(r"uddg=([^&]+)", url)
                    if uddg_match:
                        url = urllib.parse.unquote(uddg_match.group(1))

                if title and url and "duckduckgo.com" not in url:
                    results.append({
                        "title": title[:120],
                        "url": url,
                        "snippet": snippet[:300] if snippet else "",
                        "source": "DuckDuckGo",
                    })

                if len(results) >= max_results:
                    break

    except Exception as e:
        logger.error(f"DuckDuckGo HTML search error: {e}")

    return results


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


def _search_wikipedia_search(query: str, max_results: int = 5) -> List[Dict[str, str]]:
    """Search Wikipedia using the search API for multiple results."""
    results = []
    try:
        params = {
            "action": "query",
            "list": "search",
            "srsearch": query,
            "srlimit": max_results,
            "format": "json",
            "utf8": 1,
        }
        with httpx.Client(timeout=httpx.Timeout(10.0, connect=5.0)) as client:
            resp = client.get(WIKI_SEARCH, params=params)
            if resp.status_code != 200:
                return results

            data = resp.json()
            for item in data.get("query", {}).get("search", []):
                title = item.get("title", "")
                snippet = item.get("snippet", "")
                # Clean HTML from snippet
                snippet = re.sub(r"<[^>]+>", "", snippet)
                # Get URL
                title_encoded = urllib.parse.quote(title.replace(" ", "_"), safe="")
                results.append({
                    "title": title,
                    "url": f"https://zh.wikipedia.org/wiki/{title_encoded}",
                    "snippet": snippet[:300],
                    "source": "Wikipedia",
                })
    except Exception as e:
        logger.error(f"Wikipedia search API error: {e}")

    return results


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

    # Primary: DuckDuckGo HTML search (full web results)
    ddg_html_results = _search_duckduckgo_html(query, max_results)
    all_results.extend(ddg_html_results)

    # Fallback: DuckDuckGo Instant Answer API (direct answers)
    if len(all_results) < max_results:
        ddg_results = _search_duckduckgo(query, max_results - len(all_results))
        # Deduplicate
        existing_urls = {r.get("url", "") for r in all_results}
        for r in ddg_results:
            if r.get("url", "") not in existing_urls:
                all_results.append(r)
                existing_urls.add(r.get("url", ""))

    # Supplementary: Wikipedia search API (multiple results)
    if len(all_results) < max_results:
        wiki_results = _search_wikipedia_search(query, max_results - len(all_results))
        existing_urls = {r.get("url", "") for r in all_results}
        for r in wiki_results:
            if r.get("url", "") not in existing_urls:
                all_results.append(r)
                existing_urls.add(r.get("url", ""))

    # Supplementary: Wikipedia summary (single best match)
    if len(all_results) < 2:
        wiki_result = _search_wikipedia(query)
        if wiki_result and wiki_result.get("snippet"):
            existing_urls = {r.get("url", "") for r in all_results}
            if wiki_result.get("url", "") not in existing_urls:
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
