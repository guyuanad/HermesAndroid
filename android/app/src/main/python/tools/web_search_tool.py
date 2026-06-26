"""Web Search Tool for Hermes Android.

Provides web search capability using httpx.
Uses multiple reliable search backends with robust HTML parsing.
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
# Constants
# ---------------------------------------------------------------------------

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Linux; Android 14; Pixel 8) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.6422.113 Mobile Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
}


# ---------------------------------------------------------------------------
# Bing Search (most reliable HTML search)
# ---------------------------------------------------------------------------

def _search_bing(query: str, max_results: int = 8) -> List[Dict[str, str]]:
    """Search Bing and parse HTML results. Most reliable free search."""
    results = []
    try:
        url = "https://www.bing.com/search"
        params = {
            "q": query,
            "setlang": "zh-Hans",
            "cc": "CN",
        }
        with httpx.Client(
            timeout=httpx.Timeout(15.0, connect=8.0),
            follow_redirects=True,
            headers=HEADERS,
        ) as client:
            resp = client.get(url, params=params)
            if resp.status_code != 200:
                logger.warning(f"Bing returned {resp.status_code}")
                return results

            html = resp.text

            # Bing results are in <li class="b_algo"> blocks
            # Title: <h2><a href="URL">Title</a></h2>
            # Snippet: <div class="b_caption"><p>...</p> or <p class="b_lineclamp2">

            # Extract result blocks
            blocks = re.findall(r'<li class="b_algo"[^>]*>(.*?)</li>', html, re.DOTALL)

            for block in blocks[:max_results]:
                # Extract title and URL
                title_match = re.search(r'<h2[^>]*>\s*<a[^>]*href="([^"]*)"[^>]*>(.*?)</a>\s*</h2>', block, re.DOTALL)
                if not title_match:
                    continue

                url = title_match.group(1).strip()
                title = re.sub(r'<[^>]+>', '', title_match.group(2)).strip()

                # Skip Bing internal URLs
                if not url or 'bing.com' in url or 'microsoft.com' in url.lower():
                    continue

                # Extract snippet
                snippet = ""
                # Try b_caption first
                snippet_match = re.search(r'<div class="b_caption[^"]*"[^>]*>.*?<p[^>]*>(.*?)</p>', block, re.DOTALL)
                if snippet_match:
                    snippet = re.sub(r'<[^>]+>', '', snippet_match.group(1)).strip()
                else:
                    # Try any <p> in the block
                    snippet_match = re.search(r'<p[^>]*class="[^"]*lineclamp[^"]*"[^>]*>(.*?)</p>', block, re.DOTALL)
                    if snippet_match:
                        snippet = re.sub(r'<[^>]+>', '', snippet_match.group(1)).strip()

                if title:
                    results.append({
                        "title": title[:150],
                        "url": url,
                        "snippet": snippet[:400] if snippet else "",
                        "source": "Bing",
                    })

    except Exception as e:
        logger.error(f"Bing search error: {e}")

    return results


# ---------------------------------------------------------------------------
# DuckDuckGo Lite (simpler HTML than regular DDG)
# ---------------------------------------------------------------------------

def _search_ddg_lite(query: str, max_results: int = 8) -> List[Dict[str, str]]:
    """Search DuckDuckGo Lite (simple table-based HTML, easier to parse)."""
    results = []
    try:
        url = "https://lite.duckduckgo.com/lite/"
        data = {"q": query, "kl": "cn-zh"}
        with httpx.Client(
            timeout=httpx.Timeout(15.0, connect=8.0),
            follow_redirects=True,
            headers=HEADERS,
        ) as client:
            resp = client.post(url, data=data)
            if resp.status_code != 200:
                logger.warning(f"DDG Lite returned {resp.status_code}")
                return results

            html = resp.text

            # DDG Lite uses a simple table structure:
            # <tr> with result-link containing <a href="URL">Title</a>
            # Next <tr> with result-snippet containing the snippet text

            # Find all links in result rows
            link_pattern = re.compile(
                r'<a[^>]*class="result-link"[^>]*href="([^"]*)"[^>]*>(.*?)</a>',
                re.DOTALL,
            )
            snippet_pattern = re.compile(
                r'<td[^>]*class="result-snippet"[^>]*>(.*?)</td>',
                re.DOTALL,
            )

            links = list(link_pattern.finditer(html))
            snippets = list(snippet_pattern.finditer(html))

            for i, match in enumerate(links[:max_results]):
                url = match.group(1).strip()
                title = re.sub(r'<[^>]+>', '', match.group(2)).strip()

                # Extract actual URL from DDG redirect
                if "//duckduckgo.com/lite/" in url or "//duckduckgo.com/?" in url:
                    uddg = re.search(r'uddg=([^&]+)', url)
                    if uddg:
                        url = urllib.parse.unquote(uddg.group(1))
                    else:
                        continue

                snippet = ""
                if i < len(snippets):
                    snippet = re.sub(r'<[^>]+>', '', snippets[i].group(1)).strip()

                if title and url:
                    results.append({
                        "title": title[:150],
                        "url": url,
                        "snippet": snippet[:400] if snippet else "",
                        "source": "DuckDuckGo",
                    })

    except Exception as e:
        logger.error(f"DDG Lite search error: {e}")

    return results


# ---------------------------------------------------------------------------
# DuckDuckGo Instant Answer API
# ---------------------------------------------------------------------------

def _search_ddg_api(query: str, max_results: int = 5) -> List[Dict[str, str]]:
    """Search DuckDuckGo Instant Answer API (only returns direct answers)."""
    results = []
    try:
        params = {
            "q": query,
            "format": "json",
            "no_html": 1,
            "skip_disambig": 1,
        }
        with httpx.Client(timeout=httpx.Timeout(15.0, connect=5.0)) as client:
            resp = client.get("https://api.duckduckgo.com/", params=params)
            if resp.status_code != 200:
                return results

            data = resp.json()

            if data.get("AbstractText"):
                results.append({
                    "title": data.get("AbstractTitle", query),
                    "url": data.get("AbstractURL", ""),
                    "snippet": data.get("AbstractText", ""),
                    "source": data.get("AbstractSource", "DuckDuckGo"),
                })

            for topic in data.get("RelatedTopics", [])[:max_results]:
                if isinstance(topic, dict) and topic.get("Text"):
                    results.append({
                        "title": topic.get("Text", "")[:80],
                        "url": topic.get("FirstURL", ""),
                        "snippet": topic.get("Text", ""),
                        "source": "DuckDuckGo",
                    })

    except Exception as e:
        logger.error(f"DDG API search error: {e}")

    return results[:max_results]


# ---------------------------------------------------------------------------
# Wikipedia Search
# ---------------------------------------------------------------------------

def _search_wikipedia(query: str, max_results: int = 5) -> List[Dict[str, str]]:
    """Search Wikipedia (both zh and en) for results."""
    results = []
    for lang in ("zh", "en"):
        try:
            params = {
                "action": "query",
                "list": "search",
                "srsearch": query,
                "srlimit": max_results,
                "format": "json",
                "utf8": 1,
            }
            url = f"https://{lang}.wikipedia.org/w/api.php"
            with httpx.Client(timeout=httpx.Timeout(10.0, connect=5.0)) as client:
                resp = client.get(url, params=params)
                if resp.status_code != 200:
                    continue

                data = resp.json()
                for item in data.get("query", {}).get("search", []):
                    title = item.get("title", "")
                    snippet = re.sub(r'<[^>]+>', '', item.get("snippet", ""))
                    title_enc = urllib.parse.quote(title.replace(" ", "_"), safe="")
                    results.append({
                        "title": title,
                        "url": f"https://{lang}.wikipedia.org/wiki/{title_enc}",
                        "snippet": snippet[:300],
                        "source": f"Wikipedia ({lang})",
                    })

        except Exception as e:
            logger.error(f"Wikipedia {lang} search error: {e}")

    return results


# ---------------------------------------------------------------------------
# URL Fetch
# ---------------------------------------------------------------------------

def _fetch_url(url: str, max_chars: int = 5000) -> str:
    """Fetch and extract text content from a URL."""
    try:
        with httpx.Client(
            timeout=httpx.Timeout(15.0, connect=8.0),
            follow_redirects=True,
            headers=HEADERS,
        ) as client:
            resp = client.get(url)
            if resp.status_code != 200:
                return f"HTTP Error: {resp.status_code}"

            content_type = resp.headers.get("content-type", "")
            if "text/html" not in content_type and "text/plain" not in content_type:
                return f"Unsupported content type: {content_type}"

            text = resp.text

            if "text/html" in content_type:
                text = re.sub(r"<script[^>]*>.*?</script>", "", text, flags=re.DOTALL | re.IGNORECASE)
                text = re.sub(r"<style[^>]*>.*?</style>", "", text, flags=re.DOTALL | re.IGNORECASE)
                text = re.sub(r"<!--.*?-->", "", text, flags=re.DOTALL)
                text = re.sub(r"<[^>]+>", " ", text)
                text = re.sub(r"\s+", " ", text).strip()
                text = text.replace("&nbsp;", " ").replace("&amp;", "&")
                text = text.replace("&lt;", "<").replace("&gt;", ">")
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

    all_results: List[Dict[str, str]] = []
    seen_urls: set = set()

    def add_results(new_results: List[Dict[str, str]]) -> None:
        for r in new_results:
            url = r.get("url", "")
            if url and url not in seen_urls:
                all_results.append(r)
                seen_urls.add(url)

    # Tier 1: Bing (most reliable, full web results)
    try:
        bing_results = _search_bing(query, max_results)
        add_results(bing_results)
        logger.info(f"Bing: {len(bing_results)} results")
    except Exception as e:
        logger.error(f"Bing error: {e}")

    # Tier 2: DDG Lite (backup web results)
    if len(all_results) < max_results:
        try:
            ddg_results = _search_ddg_lite(query, max_results)
            add_results(ddg_results)
            logger.info(f"DDG Lite: {len(ddg_results)} results")
        except Exception as e:
            logger.error(f"DDG Lite error: {e}")

    # Tier 3: DDG Instant Answer (encyclopedia-style answers)
    if len(all_results) < max_results:
        try:
            ddg_api_results = _search_ddg_api(query, max_results)
            add_results(ddg_api_results)
            logger.info(f"DDG API: {len(ddg_api_results)} results")
        except Exception as e:
            logger.error(f"DDG API error: {e}")

    # Tier 4: Wikipedia (both zh and en)
    if len(all_results) < max_results:
        try:
            wiki_results = _search_wikipedia(query, max_results)
            add_results(wiki_results)
            logger.info(f"Wikipedia: {len(wiki_results)} results")
        except Exception as e:
            logger.error(f"Wikipedia error: {e}")

    final = all_results[:max_results]

    if not final:
        return tool_result({
            "query": query,
            "results": [],
            "count": 0,
            "message": "未找到相关结果，请尝试不同的搜索词或用英文搜索",
        })

    return tool_result({
        "query": query,
        "results": final,
        "count": len(final),
    })


def web_fetch(url: str, max_chars: int = 5000) -> str:
    """Fetch and read the content of a web page.

    Args:
        url: URL to fetch
        max_chars: Maximum characters to return
    """
    if not url.strip():
        return tool_error("URL is required")

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
            "description": "Search the web for information using Bing, DuckDuckGo and Wikipedia. Returns results with titles, URLs, and snippets.",
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
