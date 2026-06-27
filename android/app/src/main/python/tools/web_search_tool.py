"""Web Search Tool for Hermes Android.

Uses a link-extraction approach instead of CSS class matching.
This is robust against HTML structure changes.

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


def _clean_html(text: str) -> str:
    """Remove HTML tags and clean up text."""
    text = re.sub(r'<[^>]+>', '', text)
    text = text.replace('&nbsp;', ' ').replace('&amp;', '&')
    text = text.replace('&lt;', '<').replace('&gt;', '>')
    text = text.replace('&quot;', '"').replace('&#39;', "'")
    text = text.replace('&#34;', '"').replace('&#x27;', "'")
    text = re.sub(r'\s+', ' ', text).strip()
    return text


def _is_navigation_link(title: str, url: str) -> bool:
    """Determine if a link is navigation/chrome rather than a search result.

    Uses heuristics based on title length, content, and URL patterns.
    Works regardless of HTML structure changes.
    """
    # Short titles are almost always navigation
    if len(title) < 8:
        return True

    # Common navigation keywords
    nav_keywords = [
        '登录', '注册', '下载', '安装', '客户端', '首页', '更多',
        '换一换', '下一页', '上一页', '百度一下', '百度首页',
        '使用百度', '意见反馈', '举报', '加入VIP', '购买',
        '相关搜索', '大家还在搜', '为您推荐',
    ]
    for kw in nav_keywords:
        if title.startswith(kw) or title == kw:
            return True

    # URLs that are definitely internal navigation
    parsed = urllib.parse.urlparse(url)
    host = parsed.hostname or ""
    path = parsed.path or ""

    # Baidu internal pages (NOT baidu.com/link which is a result redirect)
    if 'baidu.com' in host:
        if '/link' in path or '/from' in path:
            return False  # These ARE search results
        if path in ('/', '') and 'baidu.com' in host:
            return True  # Homepage
        if any(p in path for p in ['/s?', '/home', '/gaoji', '/hao/', '/passport', '/v?']):
            return True

    return False


def _extract_all_links(html: str) -> List[Dict[str, str]]:
    """Extract ALL <a> tags from HTML with their href and text.

    This is the fundamental building block - it doesn't depend on
    any specific HTML structure or CSS classes.
    """
    links = []
    # Match <a> tags with href attribute
    pattern = re.compile(
        r'<a[^>]*href=["\']([^"\']*)["\'][^>]*>(.*?)</a>',
        re.DOTALL,
    )

    for match in pattern.finditer(html):
        url = match.group(1).strip()
        title = _clean_html(match.group(2))

        if not url or not title:
            continue

        # Skip anchor links, javascript, and relative paths without domain
        if url.startswith('#') or url.startswith('javascript:') or url.startswith('mailto:'):
            continue

        # Make relative URLs absolute (we'll skip these anyway, but just in case)
        if not url.startswith(('http://', 'https://')):
            continue

        links.append({"url": url, "title": title})

    return links


def _resolve_baidu_url(url: str, client: httpx.Client = None) -> str:
    """Resolve Baidu redirect URLs to real URLs."""
    if 'baidu.com/link' not in url and 'baidu.com/from' not in url:
        return url

    # Try to extract URL from query params first (faster)
    parsed = urllib.parse.urlparse(url)
    params = urllib.parse.parse_qs(parsed.query)
    if 'url' in params:
        return params['url'][0]

    # Follow redirect
    try:
        c = client or httpx.Client(
            timeout=httpx.Timeout(5.0, connect=3.0),
            follow_redirects=False,
            headers=HEADERS_MOBILE,
        )
        resp = c.get(url)
        if resp.status_code in (301, 302, 303, 307):
            location = resp.headers.get('location', '')
            if location and 'baidu.com' not in location:
                return location
    except Exception:
        pass

    return url


def _smart_filter_links(
    links: List[Dict[str, str]],
    max_results: int = 8,
    prefer_domains: List[str] = None,
) -> List[Dict[str, str]]:
    """Smart filter: separate search results from navigation links.

    Strategy:
    1. Filter out obvious navigation links
    2. Deduplicate by URL
    3. Score links by likelihood of being a result
    4. Return top results
    """
    seen_urls = set()
    results = []

    for link in links:
        title = link["title"]
        url = link["url"]

        # Skip navigation
        if _is_navigation_link(title, url):
            continue

        # Deduplicate
        if url in seen_urls:
            continue
        seen_urls.add(url)

        # Score this link (higher = more likely a result)
        score = 0

        # Longer titles are more likely results
        score += min(len(title), 50)

        # Baidu redirect URLs are almost always results
        if 'baidu.com/link' in url or 'baidu.com/from' in url:
            score += 100

        # External domains are more likely results than search engine domains
        host = urllib.parse.urlparse(url).hostname or ""
        if not any(d in host for d in ['baidu.com', 'bing.com', 'google.com']):
            score += 50

        # Prefer news/content sites if specified
        if prefer_domains:
            for d in prefer_domains:
                if d in host:
                    score += 30

        # Title contains Chinese characters (likely content)
        if re.search(r'[\u4e00-\u9fff]', title):
            score += 10

        results.append({
            "title": title[:150],
            "url": url,
            "score": score,
        })

    # Sort by score descending
    results.sort(key=lambda x: x["score"], reverse=True)

    # Return top results, remove score
    return [{"title": r["title"], "url": r["url"]} for r in results[:max_results]]


# ---------------------------------------------------------------------------
# Baidu Mobile Search
# ---------------------------------------------------------------------------

def _search_baidu(query: str, max_results: int = 8) -> List[Dict[str, str]]:
    """Search Baidu Mobile using link extraction approach."""
    results = []
    _search_diagnostics.append(f"BaiduMobile: query='{query}'")
    try:
        url = "https://m.baidu.com/s"
        params = {"word": query, "rn": "20"}
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

            # Step 1: Extract ALL links
            all_links = _extract_all_links(html)
            _search_diagnostics.append(f"BaiduMobile: extracted {len(all_links)} raw links")

            # Step 2: Smart filter
            filtered = _smart_filter_links(all_links, max_results * 3)

            # Step 3: Resolve Baidu redirect URLs
            for link in filtered[:max_results]:
                real_url = _resolve_baidu_url(link["url"], client)
                results.append({
                    "title": link["title"],
                    "url": real_url,
                    "snippet": "",
                    "source": "百度",
                })

            _search_diagnostics.append(f"BaiduMobile: found {len(results)} results")

    except Exception as e:
        _search_diagnostics.append(f"BaiduMobile: error - {e}")
        logger.error(f"Baidu mobile search error: {e}")

    return results


# ---------------------------------------------------------------------------
# Baidu Desktop Search (backup)
# ---------------------------------------------------------------------------

def _search_baidu_desktop(query: str, max_results: int = 8) -> List[Dict[str, str]]:
    """Search Baidu Desktop using link extraction approach."""
    results = []
    _search_diagnostics.append("BaiduDesktop: starting")
    try:
        url = "https://www.baidu.com/s"
        params = {"wd": query, "rn": "20", "ie": "utf-8"}
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

            # Desktop Baidu: prioritize <h3> links (these are definitely result titles)
            h3_links = []
            h3_pattern = re.compile(
                r'<h3[^>]*>\s*<a[^>]*href="([^"]*)"[^>]*>(.*?)</a>',
                re.DOTALL,
            )
            for match in h3_pattern.finditer(html):
                link = match.group(1).strip()
                title = _clean_html(match.group(2))
                if title and link:
                    h3_links.append({"url": link, "title": title})

            _search_diagnostics.append(f"BaiduDesktop: {len(h3_links)} h3 links found")

            if h3_links:
                # h3 links are high-confidence results
                seen = set()
                for link in h3_links:
                    if link["url"] in seen or _is_navigation_link(link["title"], link["url"]):
                        continue
                    seen.add(link["url"])
                    real_url = _resolve_baidu_url(link["url"], client)
                    results.append({
                        "title": link["title"][:150],
                        "url": real_url,
                        "snippet": "",
                        "source": "百度",
                    })
                    if len(results) >= max_results:
                        break
            else:
                # Fallback: extract all links and filter
                all_links = _extract_all_links(html)
                _search_diagnostics.append(f"BaiduDesktop: {len(all_links)} raw links")
                filtered = _smart_filter_links(all_links, max_results)
                for link in filtered:
                    real_url = _resolve_baidu_url(link["url"], client)
                    results.append({
                        "title": link["title"],
                        "url": real_url,
                        "snippet": "",
                        "source": "百度",
                    })

            _search_diagnostics.append(f"BaiduDesktop: found {len(results)} results")

    except Exception as e:
        _search_diagnostics.append(f"BaiduDesktop: error - {e}")
        logger.error(f"Baidu desktop search error: {e}")

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

    # Tier 1: Baidu Mobile
    add_results(_search_baidu(query, max_results))

    # Tier 2: Baidu Desktop (different HTML, may find different results)
    if len(all_results) < max_results:
        add_results(_search_baidu_desktop(query, max_results))

    # Tier 3: Wikipedia
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
            "description": "Search the web for information. Uses Baidu and Wikipedia. Returns results with titles, URLs, and snippets.",
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
            "description": "Fetch and read the content of a web page. Returns the text content of the page.",
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
