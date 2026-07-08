# Web Tools (联网搜索工具)

4 个工具，提供搜索、抓取、百科查询功能。

## 工具列表

### web_search
搜索互联网，返回标题+URL+摘要列表。

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| query | string | ✓ | 搜索关键词 |
| num_results | int | | 结果数量，默认5，最大10 |
| language | string | | zh-CN / en |

**后端**: Bing (cn.bing.com) 默认，可通过 `SEARCH_BACKEND=duckduckgo` 切换。

### web_fetch
抓取页面正文，自动去噪（trafilatura），支持分段读取。

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| url | string | ✓ | 页面 URL |
| max_length | int | | 最大字符数，默认8000 |
| offset | int | | 起始位置，用于继续读取截断内容 |

### suggest_alternative_urls
web_fetch 返回 403 时，生成替代链接（Wikipedia 等）。

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| blocked_url | string | ✓ | 被拒的 URL |

### encyclopedia_search
搜索百科词条完整正文。与 `web_search` 的区别：
- `web_search`：搜整个互联网，返回摘要列表
- `encyclopedia_search`：搜百科网站，返回词条正文

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| query | string | ✓ | 词条关键词 |
| language | string | | zh-CN / en |
| max_length | int | | 最大字符数，默认8000 |
| skip_cache | bool | | 跳过缓存强制联网 |

**优先级链**: Wikipedia 中文 → 360百科 → 百度百科(仅摘要) → Wikipedia 英文

**缓存**: 结果自动保存到 `.encyclopedia_cache.json`，下次同词条优先读缓存。
