"""Web Search Tool for Hermes Android.

Uses link-extraction approach that doesn't depend on CSS classes.
Desktop Baidu as primary (server-rendered, not JS-based like mobile).
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

HEADERS_DESKTOP = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
    "Accept-Encoding": "gzip, deflate",
}

_search_diagnostics: List[str] = []


def _clean_html(text: str) -> str:
    """Remove HTML tags and clean up text."""
    text = re.sub(r'<[^>]+>', '', text)
    text = text.replace('&nbsp;', ' ').replace('&amp;', '&')
    text = text.replace('&lt;', '<').replace('&gt;', '>')
    text = text.replace('&quot;', '"').replace('&#39;', "'")
    text = re.sub(r'\s+', ' ', text).strip()
    return text


def _resolve_baidu_url(url: str, client: httpx.Client = None) -> str:
    """Resolve Baidu redirect URLs to real URLs."""
    if 'baidu.com/link' not in url:
        return url

    parsed = urllib.parse.urlparse(url)
    params = urllib.parse.parse_qs(parsed.query)
    if 'url' in params:
        return params['url'][0]

    try:
        c = client or httpx.Client(
            timeout=httpx.Timeout(5.0, connect=3.0),
            follow_redirects=False,
            headers=HEADERS_DESKTOP,
        )
        resp = c.get(url)
        if resp.status_code in (301, 302, 303, 307):
            location = resp.headers.get('location', '')
            if location and 'baidu.com' not in location:
                return location
    except Exception:
        pass

    return url


def _is_navigation_title(title: str) -> bool:
    """Check if a title is navigation text, not a search result.

    Key insight: Chinese characters are information-dense.
    A 3-char Chinese title is meaningful (like "午间新闻").
    Only filter very short or obvious navigation text.
    """
    if not title:
        return True

    # Filter purely symbolic/numeric titles (less than 3 meaningful chars)
    chinese_chars = len(re.findall(r'[\u4e00-\u9fff]', title))
    total_meaningful = chinese_chars + len(re.findall(r'[a-zA-Z0-9]', title))
    if total_meaningful < 2:
        return True

    # Obvious navigation keywords
    nav_patterns = [
        r'^登录$', r'^注册$', r'^下载$', r'^安装$', r'^客户端$',
        r'^首页$', r'^更多$', r'^换一换$', r'^下一页$', r'^上一页$',
        r'^百度一下$', r'^百度首页$', r'^使用百度前必读$',
        r'^意见反馈$', r'^举报$', r'^相关搜索$',
    ]
    for p in nav_patterns:
        if re.match(p, title):
            return True

    return False


# ---------------------------------------------------------------------------
# Baidu Desktop Search (PRIMARY - server-rendered HTML)
# ---------------------------------------------------------------------------

def _search_baidu(query: str, max_results: int = 8) -> List[Dict[str, str]]:
    """Search Baidu Desktop.

    Desktop version uses server-side rendering, so search results
    are in the initial HTML (unlike mobile which may use JS).
    """
    results = []
    _search_diagnostics.append(f"Baidu: query='{query}'")
    try:
        url = "https://www.baidu.com/s"
        params = {"wd": query, "rn": "20", "ie": "utf-8"}
        with httpx.Client(
            timeout=httpx.Timeout(15.0, connect=8.0),
            follow_redirects=True,
            headers=HEADERS_DESKTOP,
        ) as client:
            resp = client.get(url, params=params)
            html = resp.text
            _search_diagnostics.append(f"Baidu: HTTP {resp.status_code}, {len(html)} chars")

            if resp.status_code != 200:
                return results

            seen = set()

            # ---- Strategy 1: <h3> links (highest confidence) ----
            # Baidu ALWAYS puts result titles in <h3> tags
            h3_pattern = re.compile(
                r'<h3[^>]*>\s*<a[^>]*href="([^"]*)"[^>]*>(.*?)</a>',
                re.DOTALL,
            )
            h3_count = 0
            for match in h3_pattern.finditer(html):
                link = match.group(1).strip()
                title = _clean_html(match.group(2))
                h3_count += 1

                if _is_navigation_title(title) or link in seen:
                    continue

                seen.add(link)
                real_url = _resolve_baidu_url(link, client)
                results.append({
                    "title": title[:150],
                    "url": real_url,
                    "snippet": "",
                    "source": "百度",
                })

                if len(results) >= max_results:
                    break

            _search_diagnostics.append(f"Baidu: h3 matches={h3_count}, results={len(results)}")

            # ---- Strategy 2: All <a> links with href containing baidu.com/link ----
            if len(results) < max_results:
                link_pattern = re.compile(
                    r'<a[^>]*href="(https?://[^"]*baidu\.com/link[^"]*)"[^>]*>(.*?)</a>',
                    re.DOTALL,
                )
                link_count = 0
                for match in link_pattern.finditer(html):
                    link = match.group(1).strip()
                    title = _clean_html(match.group(2))
                    link_count += 1

                    if _is_navigation_title(title) or link in seen:
                        continue

                    seen.add(link)
                    real_url = _resolve_baidu_url(link, client)
                    results.append({
                        "title": title[:150],
                        "url": real_url,
                        "snippet": "",
                        "source": "百度",
                    })

                    if len(results) >= max_results:
                        break

                _search_diagnostics.append(f"Baidu: baidu/link matches={link_count}, total={len(results)}")

            # ---- Strategy 3: ALL external links (broadest fallback) ----
            if len(results) < 3:
                all_link_pattern = re.compile(
                    r'<a[^>]*href="(https?://[^"]*)"[^>]*>(.*?)</a>',
                    re.DOTALL,
                )
                all_count = 0
                for match in all_link_pattern.finditer(html):
                    link = match.group(1).strip()
                    title = _clean_html(match.group(2))
                    all_count += 1

                    # Skip Baidu internal (but NOT /link redirects)
                    if 'baidu.com' in link and '/link' not in link:
                        continue

                    if _is_navigation_title(title) or link in seen:
                        continue

                    seen.add(link)
                    results.append({
                        "title": title[:150],
                        "url": link,
                        "snippet": "",
                        "source": "百度",
                    })

                    if len(results) >= max_results:
                        break

                _search_diagnostics.append(f"Baidu: all links scanned={all_count}, total={len(results)}")

    except Exception as e:
        _search_diagnostics.append(f"Baidu: error - {e}")
        logger.error(f"Baidu search error: {e}")

    return results


# ---------------------------------------------------------------------------
# Wikipedia Search
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
                    _search_diagnostics.append(f"Wikipedia {lang}: HTTP {resp.status_code}")
                    continue
                data = resp.json()
                count = len(data.get("query", {}).get("search", []))
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
                _search_diagnostics.append(f"Wikipedia {lang}: {count} results")
        except Exception as e:
            _search_diagnostics.append(f"Wikipedia {lang}: error - {e}")

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
            headers=HEADERS_DESKTOP,
        ) as client:
            resp = client.get(url)
            if resp.status_code != 200:
                return f"HTTP Error: {resp.status_code}"

            content_type = resp.headers.get("content-type", "")
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

    # Tier 1: Baidu Desktop
    add_results(_search_baidu(query, max_results))

    # Tier 2: Wikipedia
    if len(all_results) < max_results:
        add_results(_search_wikipedia(query, max_results))

    final = all_results[:max_results]

    # ALWAYS include diagnostics so we can debug
    result_data = {
        "query": query,
        "results": final,
        "count": len(final),
        "diagnostics": _search_diagnostics,
    }

    if not final:
        result_data["message"] = "未找到相关结果，请尝试不同的搜索词"

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
    return tool_result({"url": url, "content": content, "length": len(content)})


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
            "description": "Search the web for information using Baidu and Wikipedia.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Search query in natural language"},
                    "max_results": {"type": "integer", "description": "Maximum number of results (default: 5)"},
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
            "description": "Fetch and read the content of a web page.",
            "parameters": {
                "type": "object",
                "properties": {
                    "url": {"type": "string", "description": "URL to fetch"},
                    "max_chars": {"type": "integer", "description": "Maximum characters to return (default: 5000)"},
                },
                "required": ["url"],
            },
        },
    },
    description="Fetch and read web page content",
    emoji="🌐",
)
