"""Web Search Tool for Hermes Android.

Provides web search capability using httpx.
Prioritizes China-accessible search engines (Baidu, Sogou).
Falls back to Bing, DDG, Wikipedia for international users.
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

HEADERS_BROWSER = {
    "User-Agent": "Mozilla/5.0 (Linux; Android 14; Pixel 8) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.6422.113 Mobile Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
}

# Diagnostics: track which engines were tried and what happened
_search_diagnostics: List[str] = []


# ---------------------------------------------------------------------------
# Baidu Search (primary for China)
# ---------------------------------------------------------------------------

def _search_baidu(query: str, max_results: int = 8) -> List[Dict[str, str]]:
    """Search Baidu - most reliable in China."""
    results = []
    _search_diagnostics.append(f"Baidu: starting query='{query}'")
    try:
        url = "https://www.baidu.com/s"
        params = {
            "wd": query,
            "rn": str(max_results),
            "ie": "utf-8",
        }
        with httpx.Client(
            timeout=httpx.Timeout(15.0, connect=8.0),
            follow_redirects=True,
            headers=HEADERS_BROWSER,
        ) as client:
            resp = client.get(url, params=params)
            _search_diagnostics.append(f"Baidu: HTTP {resp.status_code}, {len(resp.text)} chars")

            if resp.status_code != 200:
                return results

            html = resp.text

            # Baidu search results:
            # Each result in <div class="result c-container"> or <div class="c-container">
            # Title: <h3 class="c-title"> containing <a href="...">
            # Snippet: <span class="content-right_8Zs40"> or class="c-gap-top-small" or <div class="c-abstract">

            # Method 1: Parse using h3 title links (most reliable)
            # Baidu format: <h3 class="..."><a href="http://www.baidu.com/link?url=..." target="_blank">Title</a></h3>
            title_pattern = re.compile(
                r'<h3[^>]*class="[^"]*t[^"]*"[^>]*>\s*<a[^>]*href="([^"]*)"[^>]*>(.*?)</a>\s*</h3>',
                re.DOTALL,
            )

            # Abstract/snippet patterns
            abstract_pattern = re.compile(
                r'<span[^>]*class="[^"]*(?:content-right|c-abstract|c-gap-top)[^"]*"[^>]*>(.*?)</span>',
                re.DOTALL,
            )

            titles = list(title_pattern.finditer(html))

            for i, match in enumerate(titles[:max_results]):
                link_url = match.group(1).strip()
                title = re.sub(r'<[^>]+>', '', match.group(2)).strip()

                # Baidu uses redirect URLs, keep as-is (they resolve to real URLs)
                if link_url.startswith("/"):
                    link_url = "https://www.baidu.com" + link_url

                # Try to find snippet near this title
                snippet = ""
                # Search for abstract after the title position
                start_pos = match.end()
                remaining = html[start_pos:start_pos + 2000]
                snippet_match = abstract_pattern.search(remaining)
                if snippet_match:
                    snippet = re.sub(r'<[^>]+>', '', snippet_match.group(1)).strip()
                else:
                    # Fallback: any text in a span or div after title
                    simple_match = re.search(r'<(?:span|div)[^>]*>(.*?)</(?:span|div)>', remaining, re.DOTALL)
                    if simple_match:
                        candidate = re.sub(r'<[^>]+>', '', simple_match.group(1)).strip()
                        # Only use if it looks like a real snippet (more than 20 chars, not navigation)
                        if len(candidate) > 20 and not candidate.startswith(('百度', '©', '京ICP')):
                            snippet = candidate

                if title and len(title) > 2:
                    results.append({
                        "title": title[:150],
                        "url": link_url,
                        "snippet": snippet[:400] if snippet else "",
                        "source": "百度",
                    })

            _search_diagnostics.append(f"Baidu: found {len(results)} results")

    except Exception as e:
        _search_diagnostics.append(f"Baidu: error - {e}")
        logger.error(f"Baidu search error: {e}")

    return results


# ---------------------------------------------------------------------------
# Bing Search
# ---------------------------------------------------------------------------

def _search_bing(query: str, max_results: int = 8) -> List[Dict[str, str]]:
    """Search Bing."""
    results = []
    _search_diagnostics.append(f"Bing: starting")
    try:
        url = "https://www.bing.com/search"
        params = {"q": query}
        with httpx.Client(
            timeout=httpx.Timeout(15.0, connect=8.0),
            follow_redirects=True,
            headers=HEADERS_BROWSER,
        ) as client:
            resp = client.get(url, params=params)
            _search_diagnostics.append(f"Bing: HTTP {resp.status_code}, {len(resp.text)} chars")

            if resp.status_code != 200:
                return results

            html = resp.text
            blocks = re.findall(r'<li class="b_algo"[^>]*>(.*?)</li>', html, re.DOTALL)

            for block in blocks[:max_results]:
                title_match = re.search(
                    r'<h2[^>]*>\s*<a[^>]*href="([^"]*)"[^>]*>(.*?)</a>\s*</h2>',
                    block, re.DOTALL,
                )
                if not title_match:
                    continue

                link_url = title_match.group(1).strip()
                title = re.sub(r'<[^>]+>', '', title_match.group(2)).strip()

                if not link_url or 'bing.com' in link_url:
                    continue

                snippet = ""
                snippet_match = re.search(
                    r'<div class="b_caption[^"]*"[^>]*>.*?<p[^>]*>(.*?)</p>',
                    block, re.DOTALL,
                )
                if snippet_match:
                    snippet = re.sub(r'<[^>]+>', '', snippet_match.group(1)).strip()

                if title:
                    results.append({
                        "title": title[:150],
                        "url": link_url,
                        "snippet": snippet[:400] if snippet else "",
                        "source": "Bing",
                    })

            _search_diagnostics.append(f"Bing: found {len(results)} results")

    except Exception as e:
        _search_diagnostics.append(f"Bing: error - {e}")
        logger.error(f"Bing search error: {e}")

    return results


# ---------------------------------------------------------------------------
# DuckDuckGo Lite
# ---------------------------------------------------------------------------

def _search_ddg_lite(query: str, max_results: int = 8) -> List[Dict[str, str]]:
    """Search DuckDuckGo Lite."""
    results = []
    _search_diagnostics.append(f"DDG Lite: starting")
    try:
        url = "https://lite.duckduckgo.com/lite/"
        data = {"q": query}
        with httpx.Client(
            timeout=httpx.Timeout(15.0, connect=8.0),
            follow_redirects=True,
            headers=HEADERS_BROWSER,
        ) as client:
            resp = client.post(url, data=data)
            _search_diagnostics.append(f"DDG Lite: HTTP {resp.status_code}, {len(resp.text)} chars")

            if resp.status_code != 200:
                return results

            html = resp.text

            # DDG Lite: look for any <a> with href containing real URLs
            # The structure is simple <table><tr><td>... format
            link_pattern = re.compile(
                r'<a[^>]*href="(https?://[^"]*)"[^>]*>(.*?)</a>',
                re.DOTALL,
            )

            seen = set()
            for match in link_pattern.finditer(html):
                link_url = match.group(1).strip()
                title = re.sub(r'<[^>]+>', '', match.group(2)).strip()

                # Skip DDG internal URLs
                if any(d in link_url for d in ['duckduckgo.com', 'ddg.gg']):
                    continue
                if link_url in seen:
                    continue

                seen.add(link_url)

                if title and len(title) > 3:
                    results.append({
                        "title": title[:150],
                        "url": link_url,
                        "snippet": "",
                        "source": "DuckDuckGo",
                    })

                if len(results) >= max_results:
                    break

            _search_diagnostics.append(f"DDG Lite: found {len(results)} results")

    except Exception as e:
        _search_diagnostics.append(f"DDG Lite: error - {e}")
        logger.error(f"DDG Lite search error: {e}")

    return results


# ---------------------------------------------------------------------------
# Wikipedia Search (both zh and en)
# ---------------------------------------------------------------------------

def _search_wikipedia(query: str, max_results: int = 5) -> List[Dict[str, str]]:
    """Search Wikipedia."""
    results = []
    _search_diagnostics.append(f"Wikipedia: starting")
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
            api_url = f"https://{lang}.wikipedia.org/w/api.php"
            with httpx.Client(timeout=httpx.Timeout(10.0, connect=5.0)) as client:
                resp = client.get(api_url, params=params)
                _search_diagnostics.append(f"Wikipedia {lang}: HTTP {resp.status_code}")

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
            _search_diagnostics.append(f"Wikipedia {lang}: error - {e}")

    _search_diagnostics.append(f"Wikipedia: found {len(results)} results")
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
            headers=HEADERS_BROWSER,
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
    global _search_diagnostics
    _search_diagnostics = []  # Reset diagnostics

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

    # Tier 1: Baidu (best for China users)
    add_results(_search_baidu(query, max_results))

    # Tier 2: Bing (good international search)
    if len(all_results) < max_results:
        add_results(_search_bing(query, max_results))

    # Tier 3: DDG Lite (backup)
    if len(all_results) < max_results:
        add_results(_search_ddg_lite(query, max_results))

    # Tier 4: Wikipedia
    if len(all_results) < max_results:
        add_results(_search_wikipedia(query, max_results))

    final = all_results[:max_results]

    if not final:
        # Return diagnostics to help debug
        return tool_result({
            "query": query,
            "results": [],
            "count": 0,
            "message": "未找到相关结果，请尝试不同的搜索词或用英文搜索",
            "diagnostics": _search_diagnostics,
        })

    # Include diagnostics for transparency
    result_data = {
        "query": query,
        "results": final,
        "count": len(final),
    }

    # Only include diagnostics if there were issues
    failed_engines = [d for d in _search_diagnostics if "error" in d.lower() or "found 0" in d.lower()]
    if failed_engines:
        result_data["diagnostics"] = _search_diagnostics

    return tool_result(result_data)


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
            "description": "Search the web for information. Uses Baidu, Bing, DuckDuckGo and Wikipedia. Returns results with titles, URLs, and snippets.",
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
