"""联网搜索工具 — web_search + web_fetch

搜索后端：DuckDuckGo Lite（零配置，无需 API Key，无需 Docker）
  - 直接抓取 lite.duckduckgo.com 的 HTML 页面并解析
  - DDG Lite 是无 JS 版本，HTML 极简，不易触发反爬

正文提取：trafilatura（智能去噪），失败时降级到正则提取
"""

import json
import os
import re
import html as html_mod

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
        return _search_duckduckgo(query, num_results)
    else:
        # bing / auto → Bing first
        result = _search_bing(query, num_results)
        # 如果 Bing 失败且设置了 duckduckgo 或 auto，可尝试 DDG 降级
        if "error" in result and backend == "auto":
            logger.info("Bing failed, falling back to DuckDuckGo")
            return _search_duckduckgo(query, num_results)
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
                hint_lines.append(f"1. 用 web_search(query=\"{query}\") 搜索同一主题，选择其他来源（如 Wikipedia、.gov、.edu 等友好站点）")
                hint_lines.append("2. 检查之前 web_search 返回的其他结果中有无可替代的链接")
            else:
                hint_lines.append("1. 用 web_search 搜索同一主题，选择其他来源")
                hint_lines.append("2. 尝试 Wikipedia、.gov、.edu 等对自动化访问更友好的站点")
                hint_lines.append("3. 如果之前搜索过，检查其他搜索结果中有无可替代的链接")
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
