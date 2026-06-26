"""Web Search Tool for Hermes Android.

Provides web search capability using httpx.
Prioritizes China-accessible search engines (Baidu).
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

_search_diagnostics: List[str] = []


def _clean_html(text: str) -> str:
    """Remove HTML tags and clean up text."""
    text = re.sub(r'<[^>]+>', '', text)
    text = text.replace('&nbsp;', ' ').replace('&amp;', '&')
    text = text.replace('&lt;', '<').replace('&gt;', '>')
    text = text.replace('&quot;', '"').replace('&#39;', "'")
    text = text.replace('&#34;', '"').replace('&#x27;', "'")
    text = re.sub(r'\s+', ' ', text).strip()
    return text


# ---------------------------------------------------------------------------
# Baidu Search (primary for China)
# ---------------------------------------------------------------------------

def _search_baidu(query: str, max_results: int = 8) -> List[Dict[str, str]]:
    """Search Baidu - most reliable in China.

    Baidu's HTML structure changes frequently. We use multiple
    parsing strategies to maximize result extraction.
    """
    results = []
    _search_diagnostics.append(f"Baidu: query='{query}'")
    try:
        url = "https://www.baidu.com/s"
        params = {
            "wd": query,
            "rn": str(min(max_results, 50)),
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
            seen_urls = set()

            # ---- Strategy 1: mu + title pattern ----
            # Baidu wraps results in containers with mu attribute:
            # <div mu="https://..." > ... <h3 class="t"> <a href="...">Title</a> </h3> ...
            # or <h3 class="c-title"> ...
            container_pattern = re.compile(
                r'<div[^>]*mu="(https?://[^"]*)"[^>]*>(.*?)</div>\s*(?=<div[^>]*mu=|$)',
                re.DOTALL,
            )
            for container_match in container_pattern.finditer(html):
                mu_url = container_match.group(1)
                block = container_match.group(2)

                # Find title link
                title_match = re.search(
                    r'<h3[^>]*>\s*<a[^>]*href="([^"]*)"[^>]*>(.*?)</a>',
                    block, re.DOTALL,
                )
                if not title_match:
                    # Try without h3 wrapper
                    title_match = re.search(
                        r'<a[^>]*href="(https?://[^"]*)"[^>]*data-click[^>]*>(.*?)</a>',
                        block, re.DOTALL,
                    )

                if title_match:
                    link = title_match.group(1).strip()
                    title = _clean_html(title_match.group(2))

                    # Use mu URL if link is a Baidu redirect
                    real_url = mu_url if 'baidu.com/link' in link else link

                    if title and len(title) > 2 and real_url not in seen_urls:
                        # Find snippet
                        snippet = ""
                        snippet_match = re.search(
                            r'<(?:span|div)[^>]*class="[^"]*(?:c-abstract|content-right_)[^"]*"[^>]*>(.*?)</(?:span|div)>',
                            block, re.DOTALL,
                        )
                        if snippet_match:
                            snippet = _clean_html(snippet_match.group(1))[:400]

                        seen_urls.add(real_url)
                        results.append({
                            "title": title[:150],
                            "url": real_url,
                            "snippet": snippet,
                            "source": "百度",
                        })

                if len(results) >= max_results:
                    break

            # ---- Strategy 2: Any h3 > a with data-click ----
            if len(results) < max_results:
                h3_pattern = re.compile(
                    r'<h3[^>]*>\s*<a[^>]*href="([^"]*)"[^>]*(?:data-click|data-tt)[^>]*>(.*?)</a>\s*</h3>',
                    re.DOTALL,
                )
                for match in h3_pattern.finditer(html):
                    link = match.group(1).strip()
                    title = _clean_html(match.group(2))

                    # Skip Baidu internal and already seen
                    if 'baidu.com' in link and '/link?' not in link:
                        continue
                    if any(title == r['title'] for r in results):
                        continue

                    # Resolve Baidu redirect URLs
                    if '/link?' in link:
                        real_url = link  # Keep redirect URL, browser resolves it
                    else:
                        real_url = link

                    if title and len(title) > 2 and real_url not in seen_urls:
                        seen_urls.add(real_url)
                        results.append({
                            "title": title[:150],
                            "url": real_url,
                            "snippet": "",
                            "source": "百度",
                        })

                    if len(results) >= max_results:
                        break

            # ---- Strategy 3: Broadest - any meaningful <a> in result containers ----
            if len(results) < max_results:
                # Look for result containers and extract links
                result_blocks = re.findall(
                    r'<div[^>]*class="[^"]*result[^"]*c-container[^"]*"[^>]*>(.*?)</div>',
                    html, re.DOTALL,
                )
                for block in result_blocks:
                    link_match = re.search(
                        r'<a[^>]*href="(https?://[^"]*)"[^>]*>(.*?)</a>',
                        block, re.DOTALL,
                    )
                    if not link_match:
                        continue

                    link = link_match.group(1).strip()
                    title = _clean_html(link_match.group(2))

                    # Skip Baidu internal, short titles, duplicates
                    if any(d in link for d in ['baidu.com/s?', 'baidu.com/home', 'baidu.com/gaoji']):
                        continue
                    if len(title) < 4:
                        continue
                    if any(title == r['title'] for r in results):
                        continue
                    if link in seen_urls:
                        continue

                    seen_urls.add(link)
                    results.append({
                        "title": title[:150],
                        "url": link,
                        "snippet": "",
                        "source": "百度",
                    })

                    if len(results) >= max_results:
                        break

            # ---- Strategy 4: Last resort - scan all links ----
            if len(results) < 3:
                all_links = re.findall(
                    r'<a[^>]*href="(https?://(?!baidu\.com)[^"]*)"[^>]*>(.*?)</a>',
                    html, re.DOTALL,
                )
                for link, raw_title in all_links:
                    title = _clean_html(raw_title)
                    if len(title) < 6:
                        continue
                    if any(d in link for d in ['baidu.com', 'google.com', 'bing.com']):
                        continue
                    if any(title == r['title'] for r in results):
                        continue
                    if link in seen_urls:
                        continue

                    seen_urls.add(link)
                    results.append({
                        "title": title[:150],
                        "url": link,
                        "snippet": "",
                        "source": "百度",
                    })

                    if len(results) >= max_results:
                        break

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
    _search_diagnostics.append("Bing: starting")
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
            seen_urls = set()

            # Strategy 1: b_algo blocks
            blocks = re.findall(r'<li class="b_algo"[^>]*>(.*?)</li>', html, re.DOTALL)
            for block in blocks[:max_results]:
                title_match = re.search(
                    r'<h2[^>]*>\s*<a[^>]*href="([^"]*)"[^>]*>(.*?)</a>\s*</h2>',
                    block, re.DOTALL,
                )
                if not title_match:
                    continue

                link = title_match.group(1).strip()
                title = _clean_html(title_match.group(2))

                if not link or 'bing.com' in link or link in seen_urls:
                    continue

                snippet = ""
                snippet_match = re.search(
                    r'<p[^>]*>(.*?)</p>',
                    block, re.DOTALL,
                )
                if snippet_match:
                    snippet = _clean_html(snippet_match.group(1))[:400]

                seen_urls.add(link)
                if title:
                    results.append({
                        "title": title[:150],
                        "url": link,
                        "snippet": snippet,
                        "source": "Bing",
                    })

            # Strategy 2: broader pattern if no results
            if not results:
                all_links = re.findall(
                    r'<a[^>]*href="(https?://(?!bing\.com|microsoft\.com)[^"]*)"[^>]*>(.*?)</a>',
                    html, re.DOTALL,
                )
                for link, raw_title in all_links:
                    title = _clean_html(raw_title)
                    if len(title) < 6 or link in seen_urls:
                        continue
                    seen_urls.add(link)
                    results.append({
                        "title": title[:150],
                        "url": link,
                        "snippet": "",
                        "source": "Bing",
                    })
                    if len(results) >= max_results:
                        break

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
    _search_diagnostics.append("DDG Lite: starting")
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
            seen = set()

            # Grab all external links
            link_pattern = re.compile(
                r'<a[^>]*href="(https?://(?!duckduckgo\.com|ddg\.gg)[^"]*)"[^>]*>(.*?)</a>',
                re.DOTALL,
            )
            for match in link_pattern.finditer(html):
                link = match.group(1).strip()
                title = _clean_html(match.group(2))

                if link in seen or len(title) < 4:
                    continue
                seen.add(link)

                results.append({
                    "title": title[:150],
                    "url": link,
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
    _search_diagnostics.append("Wikipedia: starting")
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
    _search_diagnostics = []

    if not query.strip():
        return tool_error("Search query is required")

    all_results: List[Dict[str, str]] = []
    seen_urls: set = set()

    def add_results(new_results: List[Dict[str, str]]) -> None:
        for r in new_results:
            u = r.get("url", "")
            if u and u not in seen_urls:
                all_results.append(r)
                seen_urls.add(u)

    # Tier 1: Baidu (best for China)
    add_results(_search_baidu(query, max_results))

    # Tier 2: Bing
    if len(all_results) < max_results:
        add_results(_search_bing(query, max_results))

    # Tier 3: DDG Lite
    if len(all_results) < max_results:
        add_results(_search_ddg_lite(query, max_results))

    # Tier 4: Wikipedia
    if len(all_results) < max_results:
        add_results(_search_wikipedia(query, max_results))

    final = all_results[:max_results]

    if not final:
        return tool_result({
            "query": query,
            "results": [],
            "count": 0,
            "message": "未找到相关结果，请尝试不同的搜索词或用英文搜索",
            "diagnostics": _search_diagnostics,
        })

    result_data = {
        "query": query,
        "results": final,
        "count": len(final),
    }

    # Include diagnostics if some engines failed
    failed = [d for d in _search_diagnostics if "error" in d.lower() or "found 0" in d.lower()]
    if failed:
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
