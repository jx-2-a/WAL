"""联网搜索工具 — web_search + web_fetch

搜索后端：DuckDuckGo Lite（零配置，无需 API Key，无需 Docker）
  - 直接抓取 lite.duckduckgo.com 的 HTML 页面并解析
  - DDG Lite 是无 JS 版本，HTML 极简，不易触发反爬

正文提取：trafilatura（智能去噪），失败时降级到正则提取
"""

import json
import re
import html as html_mod

import httpx
from loguru import logger


# ============================================================
#  DuckDuckGo Lite 搜索（默认后端，零配置）
# ============================================================

def _search_duckduckgo(query: str, num_results: int = 5) -> dict:
    """使用 DuckDuckGo Lite 搜索（HTML 抓取 → 解析）

    DDG Lite 是 DuckDuckGo 的无 JS 版本，专为旧浏览器设计，
    HTML 结构极其简单，比主站更不容易触发反爬。
    """
    params = {
        "q": query,
        "kl": "cn-zh",  # 中文结果优先
    }

    try:
        with httpx.Client(timeout=httpx.Timeout(15.0), follow_redirects=True) as client:
            resp = client.post(
                "https://lite.duckduckgo.com/lite/",
                data=params,
                headers={
                    "User-Agent": (
                        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                        "AppleWebKit/537.36 (KHTML, like Gecko) "
                        "Chrome/125.0.0.0 Safari/537.36"
                    ),
                    "Accept": "text/html,application/xhtml+xml",
                    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
                },
            )
            resp.raise_for_status()
            html_text = resp.text
    except httpx.HTTPStatusError as e:
        logger.warning(f"DuckDuckGo HTTP {e.response.status_code}")
        return {
            "error": f"DuckDuckGo 返回 HTTP {e.response.status_code}",
            "hint": "DuckDuckGo 暂时不可用，请稍后重试",
        }
    except httpx.TimeoutException:
        logger.warning("DuckDuckGo timeout")
        return {
            "error": "DuckDuckGo 请求超时",
            "hint": "网络连接过慢，请稍后重试",
        }
    except Exception as e:
        logger.warning(f"DuckDuckGo error: {e}")
        return {
            "error": f"DuckDuckGo 搜索失败：{e}",
            "hint": "请检查网络连接",
        }

    results = _parse_ddg_lite_html(html_text, num_results)

    if not results:
        return {
            "query": query,
            "backend": "duckduckgo_lite",
            "results": [],
            "hint": "未找到结果，请尝试修改搜索词",
        }

    return {
        "query": query,
        "backend": "duckduckgo_lite",
        "results": results,
    }


def _parse_ddg_lite_html(html_text: str, num_results: int) -> list[dict]:
    """解析 DuckDuckGo Lite 的 HTML 结果页

    DDG Lite 结构（极简表格）：
      <table>
        <tr><td>Web Results</td></tr>
        <tr class="result">
          <td>
            <a rel="nofollow" href="URL">TITLE</a>
            <span class="link-text">domain</span>
          </td>
        </tr>
        <tr class="result-snippet">
          <td class="result-snippet">SNIPPET</td>
        </tr>
      </table>
    """
    results = []

    # 1. 提取所有带 rel="nofollow" 的结果链接（DDG 对外链统一加此标记）
    link_rows = re.finditer(
        r'<a\s[^>]*?\brel\s*=\s*[\'\"]?nofollow[\'\"]?[^>]*?\bhref\s*=\s*[\'\"](https?://[^\'\"]+)[\'\"][^>]*?>(.*?)</a>',
        html_text, re.DOTALL | re.IGNORECASE
    )

    for m in link_rows:
        if len(results) >= num_results:
            break

        url = html_mod.unescape(m.group(1).strip())
        title = html_mod.unescape(re.sub(r'<[^>]+>', '', m.group(2)).strip())
        title = re.sub(r'\s+', ' ', title).strip()

        # 跳过 DDG 自身链接和无效结果
        if not url.startswith('http') or len(title) < 3:
            continue
        if any(skip in url.lower() for skip in [
            'duckduckgo.com', 'spreadprivacy.com', 'duck.com',
        ]):
            continue
        if results and url == results[-1]["url"]:
            continue

        # 在链接后面 2000 字符内找摘要（snippet 通常紧随其后）
        snippet = ""
        tail = html_text[m.start():m.start() + 2000]
        s_match = re.search(
            r'<td[^>]*?class\s*=\s*[\'\"][^\'\"]*result-snippet[^\'\"]*[\'\"][^>]*?>(.*?)</td>',
            tail, re.DOTALL | re.IGNORECASE
        )
        if s_match:
            snippet = re.sub(r'<[^>]+>', '', s_match.group(1)).strip()
            snippet = html_mod.unescape(snippet)
            snippet = re.sub(r'\s+', ' ', snippet)[:300]

        results.append({"title": title, "url": url, "snippet": snippet})

    # 2. 后备：如果 rel=nofollow 没匹配到，尝试表格中所有外部链接
    if not results:
        for m in re.finditer(
            r'<a\s[^>]*?\bhref\s*=\s*"(https?://[^"]+)"[^>]*?>(.*?)</a>',
            html_text, re.DOTALL | re.IGNORECASE
        ):
            if len(results) >= num_results:
                break

            url = html_mod.unescape(m.group(1).strip())
            title = html_mod.unescape(re.sub(r'<[^>]+>', '', m.group(2)).strip())
            title = re.sub(r'\s+', ' ', title).strip()

            if not url.startswith('http') or len(title) < 5:
                continue
            if any(skip in url.lower() for skip in [
                'duckduckgo.com', 'spreadprivacy.com',
            ]):
                continue

            results.append({"title": title, "url": url, "snippet": ""})

    return results


# ============================================================
#  web_search — 对外统一接口
# ============================================================

def web_search(query: str, project_name: str = "",
               num_results: int = 5, language: str = "zh-CN") -> dict:
    """搜索互联网，返回标题+URL+摘要

    使用 DuckDuckGo Lite，零配置，直接可用。

    Args:
        query: 搜索关键词。建议具体、描述性。
        project_name: 项目名称（用于日志）
        num_results: 返回结果数量（默认5，最大10）
        language: 语言偏好（保留参数，DDG Lite 通过 kl=cn-zh 固定中文）

    Returns:
        {"query": "...", "backend": "duckduckgo_lite", "results": [...]}
        或 {"error": "...", "hint": "..."}
    """
    num_results = min(max(num_results, 1), 10)
    return _search_duckduckgo(query, num_results)


# ============================================================
#  web_fetch — 抓取页面正文
# ============================================================

def _extract_content_trafilatura(html_text: str, url: str) -> tuple[str, str]:
    """使用 trafilatura 提取正文，返回 (title, content)"""
    try:
        import trafilatura
        extracted = trafilatura.extract(
            html_text,
            output_format="json",
            include_comments=False,
            include_tables=False,
            with_metadata=True,
            url=url,
        )
        if extracted:
            meta = json.loads(extracted)
            title = meta.get("title", "")
            content = meta.get("text", "") or meta.get("raw_text", "")
            if content.strip():
                return title, content
    except Exception as e:
        logger.warning(f"trafilatura extract failed: {e}")

    return "", ""


def _extract_title_fallback(html_text: str, url: str) -> str:
    """从 HTML <title> 标签提取标题"""
    try:
        match = re.search(r'<title[^>]*>(.*?)</title>', html_text, re.IGNORECASE | re.DOTALL)
        if match:
            title = html_mod.unescape(match.group(1).strip())
            title = re.sub(r'\s+', ' ', title)
            return title
    except Exception:
        pass
    return url


def _extract_content_fallback(html_text: str) -> str:
    """降级方案：剥离 HTML 标签，提取纯文本"""
    # 移除 script / style / noscript
    text = re.sub(r'<(script|style|noscript|iframe|svg)[^>]*>.*?</\1>',
                  '', html_text, flags=re.DOTALL | re.IGNORECASE)
    # 移除所有 HTML 标签
    text = re.sub(r'<[^>]+>', ' ', text)
    # 解码 HTML 实体
    text = html_mod.unescape(text)
    # 合并空白
    text = re.sub(r'\n\s*\n', '\n\n', text)
    text = re.sub(r'[ \t]+', ' ', text)
    lines = [l.strip() for l in text.splitlines() if l.strip()]
    return '\n'.join(lines)


def web_fetch(url: str, project_name: str = "", max_length: int = 3000) -> dict:
    """抓取指定 URL 的页面正文内容

    使用 trafilatura 智能提取正文（去除导航/广告等噪音）。
    如果 trafilatura 提取失败，自动降级为纯文本提取。

    Args:
        url: 要抓取的页面 URL，必须以 http:// 或 https:// 开头
        project_name: 项目名称（用于日志）
        max_length: 返回最大字符数（默认3000，最大8000）

    Returns:
        {"url": "...", "title": "...", "content": "...", "truncated": bool}
    """
    max_length = min(max(max_length, 500), 8000)

    # 验证 URL 格式
    if not re.match(r'^https?://', url):
        return {"error": f"Invalid URL: {url}", "hint": "URL 必须以 http:// 或 https:// 开头"}

    # 抓取 HTML
    try:
        with httpx.Client(
            timeout=httpx.Timeout(20.0),
            follow_redirects=True,
            max_redirects=5,
        ) as client:
            resp = client.get(
                url,
                headers={
                    "User-Agent": (
                        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                        "AppleWebKit/537.36 (KHTML, like Gecko) "
                        "Chrome/125.0.0.0 Safari/537.36"
                    ),
                    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
                },
            )
            resp.raise_for_status()
            html_text = resp.text

    except httpx.HTTPStatusError as e:
        logger.warning(f"Fetch HTTP {e.response.status_code}: {url}")
        return {"error": f"抓取失败：HTTP {e.response.status_code}", "url": url}
    except httpx.TimeoutException:
        logger.warning(f"Fetch timeout: {url}")
        return {"error": "抓取超时", "url": url, "hint": "页面加载时间过长，请稍后重试"}
    except Exception as e:
        logger.warning(f"Fetch error: {e} for {url}")
        return {"error": f"抓取失败：{e}", "url": url}

    # 提取正文
    title, content = _extract_content_trafilatura(html_text, url)

    # 降级：trafilatura 提取失败时手动处理
    if not content or not content.strip():
        logger.info(f"trafilatura returned empty for {url}, using fallback")
        content = _extract_content_fallback(html_text)

    if not title:
        title = _extract_title_fallback(html_text, url)

    # 截断
    truncated = len(content) > max_length
    if truncated:
        content = content[:max_length] + "\n\n... (页面过长，已截断)"

    return {
        "url": url,
        "title": title,
        "content": content,
        "truncated": truncated,
        "content_length": len(content),
    }
