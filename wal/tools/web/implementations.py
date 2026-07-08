"""联网搜索工具 — web_search + web_fetch

搜索后端：DuckDuckGo Lite（零配置，无需 API Key，无需 Docker）
  - 直接抓取 lite.duckduckgo.com 的 HTML 页面并解析
  - DDG Lite 是无 JS 版本，HTML 极简，不易触发反爬

正文提取：trafilatura（智能去噪），失败时降级到正则提取
"""

import json
import os
import re
import time
import html as html_mod
from pathlib import Path
from urllib.parse import quote, urlparse

import httpx
from loguru import logger


# ============================================================
#  通用浏览器请求头（模拟 Chrome 125，降低被反爬拦截的概率）
# ============================================================

_BASE_HEADERS: dict[str, str] = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/125.0.0.0 Safari/537.36"
    ),
    "Accept": (
        "text/html,application/xhtml+xml,application/xml;q=0.9,"
        "image/avif,image/webp,image/apng,*/*;q=0.8,"
        "application/signed-exchange;v=b3;q=0.7"
    ),
    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
    "Cache-Control": "max-age=0",
    "Sec-Ch-Ua": '"Google Chrome";v="125", "Chromium";v="125", "Not/A.Brand";v="24"',
    "Sec-Ch-Ua-Mobile": "?0",
    "Sec-Ch-Ua-Platform": '"Windows"',
    "Sec-Fetch-Dest": "document",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-Site": "none",
    "Sec-Fetch-User": "?1",
    "Upgrade-Insecure-Requests": "1",
    "DNT": "1",
}

_FETCH_HEADERS: dict[str, str] = {
    **_BASE_HEADERS,
    "Sec-Fetch-Site": "cross-site",  # web_fetch 跨站导航
}

_SEARCH_HEADERS: dict[str, str] = {
    **_BASE_HEADERS,
    "Sec-Fetch-Site": "same-origin",  # web_search 始终访问同一站点
}


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
                headers=_SEARCH_HEADERS,
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
#  Bing 搜索（默认后端，cn.bing.com 国内直连）
# ============================================================

def _search_bing(query: str, num_results: int = 5) -> dict:
    """使用 Bing 搜索（cn.bing.com，国内无需 VPN）

    抓取 Bing 搜索结果页的 HTML，解析出标题+URL+摘要。
    """
    params = {
        "q": query,
        "setlang": "zh-cn",
        "count": str(min(num_results + 3, 15)),
    }

    try:
        with httpx.Client(timeout=httpx.Timeout(15.0), follow_redirects=True) as client:
            resp = client.get(
                "https://cn.bing.com/search",
                params=params,
                headers=_SEARCH_HEADERS,
            )
            resp.raise_for_status()
            html_text = resp.text
    except httpx.HTTPStatusError as e:
        logger.warning(f"Bing HTTP {e.response.status_code}")
        if e.response.status_code == 403:
            return {
                "error": "Bing 返回 HTTP 403（访问被拒）",
                "hint": "Bing 暂时限制了请求，请稍后重试或设置 SEARCH_BACKEND=duckduckgo",
            }
        return {
            "error": f"Bing 返回 HTTP {e.response.status_code}",
            "hint": "请稍后重试",
        }
    except httpx.TimeoutException:
        logger.warning("Bing timeout")
        return {
            "error": "Bing 请求超时",
            "hint": "网络连接过慢，请稍后重试",
        }
    except Exception as e:
        logger.warning(f"Bing error: {e}")
        return {
            "error": f"Bing 搜索失败：{e}",
            "hint": "请检查网络连接，或设置 SEARCH_BACKEND=duckduckgo",
        }

    results = _parse_bing_html(html_text, num_results)

    if not results:
        return {
            "query": query,
            "backend": "bing",
            "results": [],
            "hint": "未找到结果，请尝试修改搜索词",
        }

    return {
        "query": query,
        "backend": "bing",
        "results": results,
    }


def _parse_bing_html(html_text: str, num_results: int) -> list[dict]:
    """解析 Bing 搜索结果页 HTML

    Bing 结构（2024）：
      <li class="b_algo">
        <h2><a href="URL">Title</a></h2>
        <div class="b_caption">
          <p>snippet text</p>
        </div>
      </li>

    部分结果可能省略 snippet 或有额外标记，解析会做降级处理。
    """
    results = []

    # 按 <li class="b_algo"> 切分结果块
    algo_blocks = re.split(
        r'<(?:li|div)\s[^>]*?\bclass\s*=\s*[\'\"]b_algo[\'\"][^>]*?>',
        html_text, flags=re.IGNORECASE
    )

    for block in algo_blocks[1:]:  # 第一个分段是 b_algo 之前的内容，跳过
        if len(results) >= num_results:
            break

        # 提取标题链接：<h2> 内的第一个 <a href="...">...</a>
        title = ""
        url = ""
        h2_match = re.search(
            r'<h2[^>]*>(.*?)</h2>', block, re.DOTALL | re.IGNORECASE
        )
        if h2_match:
            h2_content = h2_match.group(1)
            a_match = re.search(
                r'<a\s[^>]*?\bhref\s*=\s*[\'\"](https?://[^\'\"]+)[\'\"][^>]*?>(.*?)</a>',
                h2_content, re.DOTALL | re.IGNORECASE
            )
            if a_match:
                url = html_mod.unescape(a_match.group(1).strip())
                title = html_mod.unescape(re.sub(r'<[^>]+>', '', a_match.group(2)).strip())
                title = re.sub(r'\s+', ' ', title).strip()

        # 跳过无效结果
        if not url or not url.startswith('http') or len(title) < 3:
            continue
        if any(skip in url.lower() for skip in ['bing.com', 'microsoft.com/bing']):
            continue

        # 提取摘要：<div class="b_caption"> 内的 <p> 或纯文本
        snippet = ""
        caption_match = re.search(
            r'<div[^>]*?\bclass\s*=\s*[\'\"]b_caption[\'\"][^>]*?>(.*?)</div>',
            block, re.DOTALL | re.IGNORECASE
        )
        if caption_match:
            caption = caption_match.group(1)
            # 优先取 <p> 标签内容
            p_match = re.search(r'<p[^>]*>(.*?)</p>', caption, re.DOTALL | re.IGNORECASE)
            if p_match:
                snippet = p_match.group(1)
            else:
                snippet = caption
            snippet = re.sub(r'<[^>]+>', '', snippet).strip()
            snippet = html_mod.unescape(snippet)
            snippet = re.sub(r'\s+', ' ', snippet)

        # 降级：找不到 b_caption 时在 h2 后面找任何文本
        if not snippet and h2_match:
            after_h2 = block[h2_match.end():h2_match.end() + 1500]
            text = re.sub(r'<[^>]+>', ' ', after_h2)
            text = html_mod.unescape(text)
            text = re.sub(r'\s+', ' ', text).strip()
            if len(text) > 30:
                snippet = text[:300]

        results.append({
            "title": title,
            "url": url,
            "snippet": snippet[:300] if snippet else "",
        })

    return results


# ============================================================
#  web_search — 对外统一接口（多后端调度）
# ============================================================

def _get_search_backend() -> str:
    """读取 SEARCH_BACKEND 环境变量，返回后端标识

    - "bing": Bing 搜索（默认，cn.bing.com 国内直连，全球可用）
    - "duckduckgo": DuckDuckGo Lite（需 VPN，适合海外环境）
    - "auto": 自动选择（先 Bing 后 DDG，暂未实现，退化为 bing）
    """
    backend = os.getenv("SEARCH_BACKEND", "bing").strip().lower()
    if backend not in ("bing", "duckduckgo", "auto"):
        logger.warning(f"Unknown SEARCH_BACKEND={backend}, falling back to bing")
        backend = "bing"
    return backend


def _tag_preferred_sources(results: list[dict]) -> list[dict]:
    """标记优先抓取来源（Wikipedia 等对自动化友好的站点）

    在结果的 note 字段中添加提示，引导 AI 优先选择这些链接。
    """
    for r in results:
        url = r.get("url", "").lower()
        if "wikipedia.org" in url:
            r["note"] = "⭐ 优先抓取：Wikipedia 对自动化访问友好，内容详实"
        elif "zhihu.com" in url or "baidu.com" in url:
            r["note"] = "⚠️ 可能反爬：该站点可能拒绝自动化访问（403）"
    return results


def web_search(query: str, project_name: str = "",
               num_results: int = 5, language: str = "zh-CN") -> dict:
    """搜索互联网，返回标题+URL+摘要

    后端选择（环境变量 SEARCH_BACKEND）：
      - bing（默认）：cn.bing.com，国内直连，无需 VPN
      - duckduckgo：DuckDuckGo Lite，海外可用
      - auto：自动选择（暂退化为 bing）

    Args:
        query: 搜索关键词。建议具体、描述性。
        project_name: 项目名称（用于日志）
        num_results: 返回结果数量（默认5，最大10）
        language: 语言偏好（Bing 通过 setlang=zh-cn；DDG 通过 kl=cn-zh）

    Returns:
        {"query": "...", "backend": "bing|duckduckgo_lite", "results": [...]}
        或 {"error": "...", "hint": "..."}
    """
    num_results = min(max(num_results, 1), 10)
    backend = _get_search_backend()

    if backend == "duckduckgo":
        result = _search_duckduckgo(query, num_results)
    else:
        # bing / auto → Bing first
        result = _search_bing(query, num_results)
        # 如果 Bing 失败且设置了 duckduckgo 或 auto，可尝试 DDG 降级
        if "error" in result and backend == "auto":
            logger.info("Bing failed, falling back to DuckDuckGo")
            return _search_duckduckgo(query, num_results)

    # 标记优先抓取来源
    if "results" in result:
        result["results"] = _tag_preferred_sources(result["results"])

    return result


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


def _extract_query_from_url(url: str) -> str | None:
    """从 URL 中提取搜索关键词，用于 403 提示 agent 搜索替代来源

    支持的 URL 模式：
      - baike.baidu.com/item/韩立/2508547  → "韩立"
      - zh.wikipedia.org/wiki/韩立          → "韩立"
      - 通用路径包含中文                      → 提取中文部分

    Returns:
        提取的关键词，如果无法提取则返回 None
    """
    from urllib.parse import urlparse, unquote

    try:
        parsed = urlparse(url)
        path = unquote(parsed.path).strip("/")

        # 百度百科: /item/关键词/数字ID
        if "baike.baidu.com" in parsed.netloc:
            m = re.search(r'^item/([^/]+)', path)
            if m:
                return m.group(1)

        # Wikipedia: /wiki/关键词
        if "wikipedia.org" in parsed.netloc:
            m = re.search(r'^wiki/([^/]+)', path)
            if m:
                return m.group(1).replace("_", " ")

        # 通用：提取路径中的中文片段（最有可能是标题/关键词）
        cjk_chunks = re.findall(r'[一-鿿㐀-䶿]{2,}', path)
        if cjk_chunks:
            return max(cjk_chunks, key=len)

        # 通用：最后一段路径作为关键词（英文字段）
        segments = [s for s in path.split("/") if s and len(s) > 2]
        if segments:
            candidate = segments[-1].replace("-", " ").replace("_", " ")
            if len(candidate) >= 3:
                return candidate

    except Exception:
        pass

    return None


def _search_360baike(query: str) -> str | None:
    """搜索 360 百科，返回第一条真实文章 URL

    360 百科的文章 URL 是数字 ID 格式（/doc/2158819-2284216.html），
    不能用关键词拼接，必须真正搜索后提取。
    """
    from urllib.parse import quote

    search_url = f"https://baike.so.com/search?q={quote(query)}"
    try:
        with httpx.Client(timeout=httpx.Timeout(15.0), follow_redirects=True) as client:
            resp = client.get(search_url, headers=_SEARCH_HEADERS)
            resp.raise_for_status()
            html_text = resp.text
    except Exception as e:
        logger.warning(f"360百科搜索失败: {e}")
        return None

    # 提取第一个 /doc/ 链接（真正的文章 URL）
    # 注意：360 百科的 href 是完整绝对 URL，如 href="https://baike.so.com/doc/5646701-32384702.html"
    m = re.search(r'href="(https?://baike\.so\.com/doc/\d+-\d+\.html)"', html_text)
    if m:
        return m.group(1)

    logger.warning("360百科搜索页未找到 /doc/ 链接")
    return None


def suggest_alternative_urls(blocked_url: str) -> dict:
    """当 web_fetch 被拒（403）时，根据被封 URL 生成替代链接

    从 URL 中提取关键词，生成 Wikipedia 等对抓取友好的替代来源。
    通常在 web_fetch 返回 403 后调用，用返回的链接重试 web_fetch。

    Wikipedia 直接拼接 URL（/wiki/关键词 格式固定）。
    百度百科→360百科 需要真正搜索提取真实文章 URL（360 用数字 ID 不能拼接）。

    Args:
        blocked_url: 被拒绝访问的 URL（即 web_fetch 返回 403 的那个链接）

    Returns:
        {"alternatives": [...], "_next": "请立即...web_fetch(...)..."}
    """
    from urllib.parse import quote, urlparse

    query = _extract_query_from_url(blocked_url)
    if not query:
        return {"alternatives": [], "_next": "无法从 URL 提取关键词，请用 web_search 搜索同一主题"}

    alternatives: list[dict] = []
    parsed = urlparse(blocked_url)

    # Wikipedia（中文）：百度百科的最佳替代
    wiki_zh = f"https://zh.wikipedia.org/wiki/{quote(query)}"
    alternatives.append({
        "title": f"{query} - Wikipedia (中文)",
        "url": wiki_zh,
        "note": "Wikipedia 对自动化访问友好，推荐优先尝试",
    })

    # Wikipedia（英文）：备选
    wiki_en = f"https://en.wikipedia.org/wiki/{quote(query.replace(' ', '_'))}"
    alternatives.append({
        "title": f"{query} - Wikipedia (English)",
        "url": wiki_en,
        "note": "英文维基，内容可能更详细",
    })

    # 百度百科 → 360百科（需搜索提取真实文章 URL，360 用数字 ID 不能拼接）
    if "baike.baidu.com" in parsed.netloc:
        logger.info(f"搜索 360百科: {query}")
        baike360_url = _search_360baike(query)
        if baike360_url:
            alternatives.append({
                "title": f"{query} - 360百科",
                "url": baike360_url,
                "note": "360百科，反爬相对宽松（已自动搜索获取真实文章链接）",
            })
        else:
            # 降级：返回搜索页 URL
            alternatives.append({
                "title": f"{query} - 360百科搜索",
                "url": f"https://baike.so.com/search?q={quote(query)}",
                "note": "⚠️ 自动搜索未能提取文章链接，返回搜索页供手动选择",
            })

    return {
        "query": query,
        "alternatives": alternatives,
        "_next": (
            f"请立即依次尝试 web_fetch 抓取以下链接（第1条失败就试第2条，以此类推）：\n"
            + "\n".join(f"  {i+1}. web_fetch(url=\"{a['url']}\")  -- {a['note']}"
                       for i, a in enumerate(alternatives))
        ),
    }


def web_fetch(url: str, project_name: str = "", max_length: int = 8000,
              offset: int = 0) -> dict:
    """抓取指定 URL 的页面正文内容

    使用 trafilatura 智能提取正文（去除导航/广告等噪音）。
    如果 trafilatura 提取失败，自动降级为纯文本提取。
    支持 offset 分段读取：首次调用 offset=0，若返回 truncated=true，
    可用 next_offset 继续读取后续内容，实现"滚动"效果。

    Args:
        url: 要抓取的页面 URL，必须以 http:// 或 https:// 开头
        project_name: 项目名称（用于日志）
        max_length: 返回最大字符数（默认8000，范围500~8000）
        offset: 起始字符位置（默认0从开头开始）。用于继续读取被截断的内容

    Returns:
        {"url": "...", "title": "...", "content": "...", "truncated": bool,
         "offset": int, "next_offset": int, "total_length": int}
    """
    max_length = min(max(max_length, 500), 8000)
    offset = max(offset, 0)

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
                headers=_FETCH_HEADERS,
            )
            resp.raise_for_status()
            html_text = resp.text

    except httpx.HTTPStatusError as e:
        sc = e.response.status_code
        logger.warning(f"Fetch HTTP {sc}: {url}")
        if sc == 403:
            query = _extract_query_from_url(url)
            hint_lines = [
                "该网站（如百度百科、知乎等）有严格的反爬机制，请尝试以下替代方案：",
            ]
            if query:
                hint_lines.append(f"1. 调用 suggest_alternative_urls(blocked_url=\"{url}\") 获取替代链接，然后用 web_fetch 抓取")
                hint_lines.append(f"2. 或用 web_search(query=\"{query}\") 搜索同一主题，选其他来源")
            else:
                hint_lines.append("1. 调用 suggest_alternative_urls(blocked_url=\"<原URL>\") 获取替代链接重试")
                hint_lines.append("2. 或用 web_search 搜索同一主题，选其他来源")
            hint_lines.append("3. 实在不行就跳过本条，继续写作——参考信息不是必需的")

            return {
                "error": "抓取失败：HTTP 403（网站拒绝访问）",
                "url": url,
                "hint": "\n".join(hint_lines),
                "suggested_search": query or None,
            }
        if sc == 429:
            return {
                "error": f"抓取失败：HTTP 429（请求过于频繁）",
                "url": url,
                "hint": "请等待几秒后重试",
            }
        return {"error": f"抓取失败：HTTP {sc}", "url": url}
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

    # 截断（支持 offset 分段读取）
    total_len = len(content)
    truncated = (offset + max_length) < total_len
    content = content[offset:offset + max_length]
    next_offset = offset + len(content) if truncated else None

    if offset > 0:
        content = f"[续：第 {offset + 1} 字符起]\n\n{content}"

    if truncated:
        content += (
            f"\n\n... (已显示 {offset + max_length}/{total_len} 字符，"
            f"后续还有 {total_len - offset - max_length} 字符)"
        )

    return {
        "url": url,
        "title": title,
        "content": content,
        "truncated": truncated,
        "offset": offset,
        "next_offset": next_offset,
        "total_length": total_len,
        "content_length": len(content),
    }


# ============================================================
#  百科搜索 — encyclopedia_search
#  优先级：Wikipedia 中文 → 360百科 → 百度百科 API → Wikipedia 英文
#  独立于 web_search（网页搜索），由 agent 自主选择用哪个
#  结果自动本地缓存，下次同词条优先读缓存
# ============================================================

_WIKI_API = {
    "zh": "https://zh.wikipedia.org/w/api.php",
    "en": "https://en.wikipedia.org/w/api.php",
}

_WIKI_SITE = {
    "zh": "https://zh.wikipedia.org",
    "en": "https://en.wikipedia.org",
}

# 百科缓存文件路径
_CACHE_PATH = Path(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))) / ".encyclopedia_cache.json"


def _get_baidu_api_key() -> str | None:
    """从 .env 文件或环境变量读取 Baidu_API_Key"""
    # 尝试从项目根目录 .env 读取
    env_paths = [
        Path(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))) / ".env",
        Path(os.getcwd()) / ".env",
    ]
    for env_path in env_paths:
        try:
            with open(env_path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line.startswith("Baidu_API_Key="):
                        return line.split("=", 1)[1].strip()
        except FileNotFoundError:
            continue
    return os.getenv("Baidu_API_Key")


def _search_baidu_baike_api(query: str, top_k: int = 3) -> list[dict]:
    """通过百度百科 AppBuilder API 搜索词条"""
    api_key = _get_baidu_api_key()
    if not api_key:
        logger.warning("未配置 Baidu_API_Key，跳过百度百科 API")
        return []

    url = "https://appbuilder.baidu.com/v2/baike/lemma/get_list_by_title"
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    params = {"lemma_title": query, "top_k": top_k}

    try:
        with httpx.Client(timeout=httpx.Timeout(15.0)) as client:
            resp = client.get(url, params=params, headers=headers)
            resp.raise_for_status()
            data = resp.json()
    except Exception as e:
        logger.warning(f"百度百科 API 搜索失败: {e}")
        return []

    results = data.get("result", [])
    if not results:
        return []

    return [
        {
            "lemma_id": r["lemma_id"],
            "lemma_title": r.get("lemma_title", ""),
            "lemma_desc": r.get("lemma_desc", ""),
            "url": r.get("url", ""),
            "is_default": r.get("is_default", 0),
        }
        for r in results
    ]


def _get_baidu_baike_content(lemma_id: int) -> dict | None:
    """通过百度百科 AppBuilder API 获取词条内容（仅摘要 + card 信息框）"""
    api_key = _get_baidu_api_key()
    if not api_key:
        return None

    url = "https://appbuilder.baidu.com/v2/baike/lemma/get_content"
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    params = {"search_type": "lemmaId", "search_key": lemma_id}

    try:
        with httpx.Client(timeout=httpx.Timeout(15.0)) as client:
            resp = client.get(url, params=params, headers=headers)
            resp.raise_for_status()
            data = resp.json()
    except Exception as e:
        logger.warning(f"百度百科 API 获取内容失败: {e}")
        return None

    result = data.get("result", {})
    if not result:
        return None

    return {
        "lemma_id": result.get("lemma_id"),
        "lemma_title": result.get("lemma_title", ""),
        "lemma_desc": result.get("lemma_desc", ""),
        "url": result.get("url", ""),
        "summary": result.get("summary", ""),
        "abstract_plain": result.get("abstract_plain", ""),
        "card": result.get("card", []),
    }


def _search_wikipedia(query: str, lang: str = "zh", limit: int = 5) -> list[dict]:
    """用 MediaWiki API 搜索词条，返回 [{title, pageid, snippet, url}, ...]"""
    api_url = _WIKI_API.get(lang, _WIKI_API["zh"])
    site_url = _WIKI_SITE.get(lang, _WIKI_SITE["zh"])

    params = {
        "action": "query", "list": "search", "srsearch": query,
        "srlimit": limit, "format": "json",
    }
    try:
        with httpx.Client(timeout=httpx.Timeout(15.0)) as client:
            resp = client.get(api_url, params=params, headers={
                "User-Agent": "WAL/1.0 (encyclopedia lookup; writing assistant)"
            })
            resp.raise_for_status()
            data = resp.json()
    except Exception as e:
        logger.warning(f"Wikipedia {lang} search failed: {e}")
        return []

    results = []
    for r in data.get("query", {}).get("search", []):
        title = r.get("title", "")
        results.append({
            "title": title,
            "pageid": r.get("pageid"),
            "snippet": r.get("snippet", ""),
            "url": f"{site_url}/wiki/{quote(title.replace(' ', '_'))}",
        })
    return results


def _get_wikipedia_extract(title: str | None = None, pageid: int | None = None,
                            lang: str = "zh", exintro: bool = False,
                            max_chars: int = 8000) -> dict | None:
    """用 MediaWiki API 获取词条纯文本内容"""
    api_url = _WIKI_API.get(lang, _WIKI_API["zh"])
    site_url = _WIKI_SITE.get(lang, _WIKI_SITE["zh"])

    params = {
        "action": "query", "prop": "extracts", "explaintext": 1,
        "exintro": 1 if exintro else 0, "exchars": max_chars, "format": "json",
    }
    if pageid is not None:
        params["pageids"] = pageid
    elif title is not None:
        params["titles"] = title
    else:
        return None

    try:
        with httpx.Client(timeout=httpx.Timeout(15.0)) as client:
            resp = client.get(api_url, params=params, headers={
                "User-Agent": "WAL/1.0 (encyclopedia lookup; writing assistant)"
            })
            resp.raise_for_status()
            data = resp.json()
    except Exception as e:
        logger.warning(f"Wikipedia {lang} extract failed: {e}")
        return None

    pages = (data.get("query", {}) or {}).get("pages", {})
    if not pages:
        return None

    for pid, page in pages.items():
        if int(pid) < 0:
            continue
        extract = page.get("extract", "")
        if extract.strip():
            return {
                "title": page.get("title", title or ""),
                "pageid": page.get("pageid", pid),
                "extract": extract,
                "url": f"{site_url}/wiki/{quote(page.get('title', title or '').replace(' ', '_'))}",
            }

    return None


def _is_disambiguation_zh(text: str) -> bool:
    """检测中文维基消歧义页"""
    markers = ["可以指", "消歧义", "可能指：", "可以指："]
    head = text[:200]
    return any(m in head for m in markers) or len(text) < 80


def _is_disambiguation_en(text: str) -> bool:
    """检测英文维基消歧义页"""
    markers = ["may refer to:", "disambiguation", "commonly refers to:"]
    head = text[:250]
    return any(m in head.lower() for m in markers) or len(text) < 80


def _is_english_query(query: str) -> bool:
    """判断查询是否主要为英文/拉丁字符"""
    latin_chars = sum(1 for c in query if c.isascii() and c.isalpha())
    total_chars = sum(1 for c in query if c.isalpha())
    if total_chars == 0:
        return False
    return latin_chars / total_chars > 0.5


def _enc_wikipedia_zh(query: str, max_length: int = 8000) -> dict:
    """Wikipedia 中文 — MediaWiki API 搜索→获取第1条正文"""
    search_results = _search_wikipedia(query, lang="zh", limit=5)
    if not search_results:
        return {"error": "Wikipedia 中文搜索无结果", "query": query, "source": "wikipedia_zh"}

    best = search_results[0]
    logger.info(f"Wiki ZH: {best['title']} (pageid={best['pageid']})")

    data = _get_wikipedia_extract(pageid=best["pageid"], lang="zh",
                                   exintro=False, max_chars=max_length)
    if not data:
        return {"error": "Wikipedia 中文获取内容失败", "query": query, "source": "wikipedia_zh"}

    content = data["extract"]
    is_disambig = _is_disambiguation_zh(content)

    return {
        "source": "wikipedia_zh",
        "query": query,
        "url": data["url"],
        "title": data["title"],
        "content": content[:max_length],
        "truncated": len(content) > max_length,
        "offset": 0,
        "next_offset": max_length if len(content) > max_length else None,
        "total_length": len(content),
        "content_length": min(len(content), max_length),
        "is_disambiguation": is_disambig,
        "search_candidates": search_results[:5],
    }


def _enc_360baike(query: str, max_length: int = 8000) -> dict:
    """360百科 — HTML 搜索→提取真实 /doc/ 链接→抓取"""
    baike360_url = _search_360baike(query)
    if not baike360_url:
        return {"error": "360百科搜索未找到文章链接", "query": query, "source": "360baike"}
    result = web_fetch(baike360_url, max_length=max_length)
    if "content" in result:
        result["source"] = "360baike"
        result["query"] = query
    return result


def _enc_baidu_baike(query: str, max_length: int = 8000) -> dict:
    """百度百科 API — 搜索→取第1条→获取摘要"""
    api_key = _get_baidu_api_key()
    if not api_key:
        return {"error": "未配置 Baidu_API_Key", "query": query, "source": "baidu_baike"}

    baidu_results = _search_baidu_baike_api(query, top_k=3)
    if not baidu_results:
        return {"error": "百度百科 API 无结果", "query": query, "source": "baidu_baike"}

    best = next((r for r in baidu_results if r["is_default"] == 1), baidu_results[0])
    logger.info(f"百度百科: {best['lemma_title']} (id={best['lemma_id']})")
    content_data = _get_baidu_baike_content(best["lemma_id"])
    if content_data and content_data.get("abstract_plain", "").strip():
        content = content_data["abstract_plain"]
        return {
            "source": "baidu_baike",
            "query": query,
            "url": content_data.get("url", ""),
            "title": content_data.get("lemma_title", query),
            "content": content,
            "truncated": len(content) > max_length,
            "offset": 0,
            "next_offset": max_length if len(content) > max_length else None,
            "total_length": len(content),
            "content_length": min(len(content), max_length),
        }
    return {"error": "百度百科 API 返回空内容", "query": query, "source": "baidu_baike"}


def _enc_wikipedia_en(query: str, max_length: int = 8000) -> dict:
    """Wikipedia 英文 — MediaWiki API 搜索→获取第1条正文"""
    search_results = _search_wikipedia(query, lang="en", limit=5)
    if not search_results:
        return {"error": "Wikipedia 英文搜索无结果", "query": query, "source": "wikipedia_en"}

    best = search_results[0]
    logger.info(f"Wiki EN: {best['title']} (pageid={best['pageid']})")

    data = _get_wikipedia_extract(pageid=best["pageid"], lang="en",
                                   exintro=False, max_chars=max_length)
    if not data:
        return {"error": "Wikipedia 英文获取内容失败", "query": query, "source": "wikipedia_en"}

    content = data["extract"]
    is_disambig = _is_disambiguation_en(content)

    return {
        "source": "wikipedia_en",
        "query": query,
        "url": data["url"],
        "title": data["title"],
        "content": content[:max_length],
        "truncated": len(content) > max_length,
        "offset": 0,
        "next_offset": max_length if len(content) > max_length else None,
        "total_length": len(content),
        "content_length": min(len(content), max_length),
        "is_disambiguation": is_disambig,
        "search_candidates": search_results[:5],
    }


# ============================================================
#  本地缓存 — 优先本地，减少重复联网
# ============================================================

def _load_encyclopedia_cache() -> dict:
    """加载百科缓存"""
    if _CACHE_PATH.exists():
        try:
            with open(_CACHE_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            logger.warning(f"百科缓存读取失败: {e}")
    return {}


def _save_encyclopedia_cache(cache: dict):
    """保存百科缓存"""
    try:
        with open(_CACHE_PATH, "w", encoding="utf-8") as f:
            json.dump(cache, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.warning(f"百科缓存保存失败: {e}")


def _cache_key(query: str, language: str) -> str:
    """生成缓存键：query|language（归一化）"""
    q = query.strip().lower()
    return f"{q}|{language}"


def encyclopedia_search(query: str, language: str = "zh-CN",
                        max_length: int = 8000,
                        skip_cache: bool = False) -> dict:
    """搜索百科词条，返回正文内容（而非网页搜索的摘要链接）

    本工具与 web_search 的区别：
      - web_search：搜索整个互联网，返回标题+URL+摘要列表，适合查最新信息、多方观点
      - encyclopedia_search：搜索百科类网站（Wikipedia/360/百度），返回完整词条正文，
        适合查固定知识、设定参考、角色/地点/概念的定义

    Agent 应根据需求自主判断用哪个：
      - 查世界观设定（历史、地理、种族、功法等）→ encyclopedia_search
      - 查最新新闻、多方观点、非百科内容 → web_search
      - 不确定时两个都调用，互相补充

    优先级：Wikipedia 中文 → 360百科 → 百度百科 API（仅摘要）→ Wikipedia 英文
    结果自动缓存到本地，下次同词条优先读缓存（不消耗网络请求）。

    Args:
        query: 词条关键词
        language: 语言偏好（zh-CN / en），默认 zh-CN
        max_length: 返回最大字符数，默认 8000
        skip_cache: 跳过缓存强制联网搜索，默认 False

    Returns:
        {"source": "wikipedia_zh|360baike|baidu_baike|wikipedia_en",
         "title": "...", "url": "...", "content": "...", "from_cache": bool, ...}
    """
    # ---- 检查缓存 ----
    if not skip_cache:
        cache = _load_encyclopedia_cache()
        key = _cache_key(query, language)
        if key in cache:
            cached = cache[key]
            logger.info(f"[百科] 缓存命中: {query} → {cached.get('source')} ({cached.get('title', '')})")
            cached["from_cache"] = True
            return cached

    is_english = _is_english_query(query)
    tried: list[str] = []
    result: dict = {}

    # ---- Priority 1: Wikipedia 中文 (MediaWiki API) ----
    logger.info(f"[百科] 1/4 Wikipedia 中文: {query}")
    result = _enc_wikipedia_zh(query, max_length=max_length)
    tried.append("wikipedia_zh")
    if "content" in result and result.get("content_length", 0) > 100:
        result["from_cache"] = False
        _save_to_cache(query, language, result)
        return result
    logger.info(f"[百科] Wikipedia 中文失败: {result.get('error', '内容过短')}")

    # ---- Priority 2: 360百科 ----
    logger.info(f"[百科] 2/4 360百科: {query}")
    result = _enc_360baike(query, max_length=max_length)
    tried.append("360baike")
    if "content" in result and result.get("content_length", 0) > 100:
        result["from_cache"] = False
        _save_to_cache(query, language, result)
        return result
    logger.info("[百科] 360百科失败")

    # ---- Priority 3: 百度百科 API（仅摘要） ----
    logger.info(f"[百科] 3/4 百度百科 API: {query}")
    result = _enc_baidu_baike(query, max_length=max_length)
    tried.append("baidu_baike")
    if "content" in result and result.get("content_length", 0) > 100:
        result["from_cache"] = False
        _save_to_cache(query, language, result)
        return result
    logger.info("[百科] 百度百科 API 失败")

    # ---- Priority 4: Wikipedia 英文（仅英文查询） ----
    if is_english:
        logger.info(f"[百科] 4/4 Wikipedia 英文: {query}")
        result = _enc_wikipedia_en(query, max_length=max_length)
        tried.append("wikipedia_en")
        if "content" in result and result.get("content_length", 0) > 100:
            result["from_cache"] = False
            _save_to_cache(query, language, result)
            return result
        logger.info("[百科] Wikipedia 英文失败")

    return {
        "error": "所有百科来源均未找到该词条",
        "query": query,
        "tried": tried,
        "hint": f'试试 web_search(query="{query}") 搜索网页获取信息',
    }


def _save_to_cache(query: str, language: str, result: dict):
    """将成功的百科结果保存到本地缓存"""
    try:
        cache = _load_encyclopedia_cache()
        key = _cache_key(query, language)
        cache[key] = {
            "source": result.get("source"),
            "title": result.get("title"),
            "url": result.get("url"),
            "content": result.get("content"),
            "content_length": result.get("content_length"),
            "is_disambiguation": result.get("is_disambiguation"),
            "search_candidates": result.get("search_candidates"),
            "saved_at": time.time(),
        }
        _save_encyclopedia_cache(cache)
        logger.info(f"[百科缓存] 已保存: {query} → {result.get('source')}")
    except Exception as e:
        logger.warning(f"[百科缓存] 保存失败: {e}")
