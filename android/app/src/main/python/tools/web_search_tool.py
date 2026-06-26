"""Web Search Tool for Hermes Android.

Provides web search capability using httpx.
Uses Baidu Mobile (simpler HTML) as primary, with fallback engines.
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

HEADERS_MOBILE = {
    "User-Agent": "Mozilla/5.0 (Linux; Android 14; Pixel 8) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.6422.113 Mobile Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
}

HEADERS_DESKTOP = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
}

_search_diagnostics: List[str] = []

# Domains that are NOT real search results (navigation, login, ads, etc.)
JUNK_DOMAINS = {
    'baidu.com', 'bing.com', 'google.com', 'microsoft.com',
    'qq.com', 'weixin.qq.com', 'wx.qq.com', 'taobao.com',
    'jd.com', 'tmall.com', 'alipay.com', 'alibaba.com',
    'douyin.com', 'tiktok.com', 'weibo.com', 'zhihu.com',
    'apple.com', 'play.google.com', 'github.com',
    'login.', 'passport.', 'account.', 'auth.',
    'ad.', 'ads.', 'adv.', 'click.', 'track.',
    'm.baidu.com', 'wap.baidu.com',
}

# Title patterns that indicate junk links
JUNK_TITLE_PATTERNS = [
    r'^登录', r'^注册', r'^下载', r'^安装', r'^APP',
    r'^客户端', r'^首页$', r'^首页$', r'^更多',
    r'^百度', r'^搜索', r'^换一换',
]


def _clean_html(text: str) -> str:
    """Remove HTML tags and clean up text."""
    text = re.sub(r'<[^>]+>', '', text)
    text = text.replace('&nbsp;', ' ').replace('&amp;', '&')
    text = text.replace('&lt;', '<').replace('&gt;', '>')
    text = text.replace('&quot;', '"').replace('&#39;', "'")
    text = text.replace('&#34;', '"').replace('&#x27;', "'")
    text = re.sub(r'\s+', ' ', text).strip()
    return text


def _is_junk_url(url: str) -> bool:
    """Check if a URL is a junk/navigation link."""
    try:
        parsed = urllib.parse.urlparse(url)
        host = parsed.hostname or ""
        for d in JUNK_DOMAINS:
            if host == d or host.endswith('.' + d):
                return True
    except Exception:
        pass
    return False


def _is_junk_title(title: str) -> bool:
    """Check if a title looks like navigation rather than a search result."""
    if len(title) < 6:
        return True
    for pattern in JUNK_TITLE_PATTERNS:
        if re.match(pattern, title):
            return True
    return False


# ---------------------------------------------------------------------------
# Baidu Mobile Search (primary - simpler HTML)
# ---------------------------------------------------------------------------

def _search_baidu_mobile(query: str, max_results: int = 8) -> List[Dict[str, str]]:
    """Search Baidu Mobile - much simpler HTML than desktop version."""
    results = []
    _search_diagnostics.append(f"BaiduMobile: query='{query}'")
    try:
        url = "https://m.baidu.com/s"
        params = {
            "word": query,
            "pn": "0",
            "rn": str(min(max_results * 2, 20)),
        }
        with httpx.Client(
            timeout=httpx.Timeout(15.0, connect=8.0),
            follow_redirects=True,
            headers=HEADERS_MOBILE,
        ) as client:
            resp = client.get(url, params=params)
            _search_diagnostics.append(f"BaiduMobile: HTTP {resp.status_code}, {len(resp.text)} chars")

            if resp.status_code != 200:
                return results

            html = resp.text
            seen = set()

            # Baidu Mobile results are in <div class="result"> blocks
            # Each has a <a href="...">Title</a> inside
            # The structure is much simpler than desktop

            # Strategy 1: Look for result containers with data-log
            # <div class="result" data-log="..."> ... <a href="...">Title</a> ...
            result_blocks = re.findall(
                r'<div[^>]*class="[^"]*result[^"]*"[^>]*>(.*?)</div>',
                html, re.DOTALL,
            )

            for block in result_blocks:
                # Find the main link
                link_match = re.search(
                    r'<a[^>]*href="(https?://[^"]*)"[^>]*>(.*?)</a>',
                    block, re.DOTALL,
                )
                if not link_match:
                    continue

                link = link_match.group(1).strip()
                title = _clean_html(link_match.group(2))

                if _is_junk_url(link) or _is_junk_title(title) or link in seen:
                    continue

                # Find snippet (usually in a <p> or <span> after the link)
                snippet = ""
                snippet_match = re.search(
                    r'<(?:p|span)[^>]*>(.*?)</(?:p|span)>',
                    block[block.find('</a>'):],  # Search after the title link
                    re.DOTALL,
                )
                if snippet_match:
                    snippet = _clean_html(snippet_match.group(1))[:400]
                    if len(snippet) < 10:
                        snippet = ""

                seen.add(link)
                results.append({
                    "title": title[:150],
                    "url": link,
                    "snippet": snippet,
                    "source": "百度",
                })

                if len(results) >= max_results:
                    break

            # Strategy 2: Broader - find all links that look like results
            if len(results) < max_results:
                all_links = re.findall(
                    r'<a[^>]*href="(https?://[^"]*)"[^>]*>(.*?)</a>',
                    html, re.DOTALL,
                )
                for link, raw_title in all_links:
                    title = _clean_html(raw_title)

                    if _is_junk_url(link) or _is_junk_title(title) or link in seen:
                        continue
                    if any(title == r['title'] for r in results):
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

            _search_diagnostics.append(f"BaiduMobile: found {len(results)} results")

    except Exception as e:
        _search_diagnostics.append(f"BaiduMobile: error - {e}")
        logger.error(f"Baidu mobile search error: {e}")

    return results


# ---------------------------------------------------------------------------
# Baidu Desktop Search (backup)
# ---------------------------------------------------------------------------

def _search_baidu_desktop(query: str, max_results: int = 8) -> List[Dict[str, str]]:
    """Search Baidu Desktop - as backup if mobile fails."""
    results = []
    _search_diagnostics.append("BaiduDesktop: starting")
    try:
        url = "https://www.baidu.com/s"
        params = {"wd": query, "rn": str(min(max_results * 2, 20)), "ie": "utf-8"}
        with httpx.Client(
            timeout=httpx.Timeout(15.0, connect=8.0),
            follow_redirects=True,
            headers=HEADERS_DESKTOP,
        ) as client:
            resp = client.get(url, params=params)
            _search_diagnostics.append(f"BaiduDesktop: HTTP {resp.status_code}, {len(resp.text)} chars")

            if resp.status_code != 200:
                return results

            html = resp.text
            seen = set()

            # Desktop Baidu: find all <h3> tags with links (these are always result titles)
            h3_pattern = re.compile(
                r'<h3[^>]*>\s*<a[^>]*href="([^"]*)"[^>]*>(.*?)</a>\s*</h3>',
                re.DOTALL,
            )
            for match in h3_pattern.finditer(html):
                link = match.group(1).strip()
                title = _clean_html(match.group(2))

                # Baidu redirect URLs are ok (they resolve)
                if _is_junk_title(title) or link in seen:
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

            _search_diagnostics.append(f"BaiduDesktop: found {len(results)} results")

    except Exception as e:
        _search_diagnostics.append(f"BaiduDesktop: error - {e}")
        logger.error(f"Baidu desktop search error: {e}")

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
            headers=HEADERS_DESKTOP,
        ) as client:
            resp = client.get(url, params=params)
            _search_diagnostics.append(f"Bing: HTTP {resp.status_code}, {len(resp.text)} chars")

            if resp.status_code != 200:
                return results

            html = resp.text
            seen = set()

            # Strategy 1: b_algo blocks
            blocks = re.findall(r'<li class="b_algo"[^>]*>(.*?)</li>', html, re.DOTALL)
            for block in blocks[:max_results * 2]:
                title_match = re.search(
                    r'<h2[^>]*>\s*<a[^>]*href="([^"]*)"[^>]*>(.*?)</a>\s*</h2>',
                    block, re.DOTALL,
                )
                if not title_match:
                    continue

                link = title_match.group(1).strip()
                title = _clean_html(title_match.group(2))

                if _is_junk_url(link) or _is_junk_title(title) or link in seen:
                    continue

                snippet = ""
                snippet_match = re.search(r'<p[^>]*>(.*?)</p>', block, re.DOTALL)
                if snippet_match:
                    snippet = _clean_html(snippet_match.group(1))[:400]

                seen.add(link)
                results.append({
                    "title": title[:150],
                    "url": link,
                    "snippet": snippet,
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
            headers=HEADERS_MOBILE,
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

    # Tier 1: Baidu Mobile (simplest HTML, works in China)
    add_results(_search_baidu_mobile(query, max_results))

    # Tier 2: Baidu Desktop (backup if mobile returns few results)
    if len(all_results) < max_results:
        add_results(_search_baidu_desktop(query, max_results))

    # Tier 3: Bing
    if len(all_results) < max_results:
        add_results(_search_bing(query, max_results))

    # Tier 4: Wikipedia
    if len(all_results) < max_results:
        add_results(_search_wikipedia(query, max_results))

    final = all_results[:max_results]

    if not final:
        return tool_result({
            "query": query,
            "results": [],
            "count": 0,
            "message": "未找到相关结果，请尝试不同的搜索词",
            "diagnostics": _search_diagnostics,
        })

    result_data = {
        "query": query,
        "results": final,
        "count": len(final),
    }

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
            "description": "Search the web for information. Uses Baidu, Bing and Wikipedia. Returns results with titles, URLs, and snippets.",
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
