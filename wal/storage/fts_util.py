"""FTS5 中文全文搜索分词工具

问题根因：SQLite 内置 unicode61 分词器**不做中文词切分**，把一整段连续
汉字当作**一个 token**（如「青石在山中苏醒」整体是 1 个词）。所以对任意
中文子串（人名「青见」、双字词「苏醒」）的 MATCH 都命中不了——新建项目
上中文全文搜索恒空。

方案（索引 / 查询统一）：
- 索引时 `fts_prepare()`：给每段连续汉字之间插入空格，使每个汉字成为
  unicode61 的独立 token；
- 查询时 `fts_query()`：对查询词做同样变换，unicode61 把查询拆成逐字
  token 后隐式 AND，任意长度的中文词都能命中（含单字、人名、短语）。

展示说明：FTS 表里存的是「预分词」文本，**不直接用于显示**。搜索结果的
snippet / 标题 / 出场角色一律 JOIN 回真实的 scenes / chapters 表取值，
避免预分词空格污染展示（如标题「第一章 苏醒」被折叠成「第一章苏醒」）。

统一性：老库（如青石）的旧 contentless FTS 索引在迁移时 DROP 并照本
方案重建，新旧库行为完全一致。

权衡：逐字 token 使多字查询退化为「各字同时出现」的 AND 匹配，可能带回
部分无关场景（召回高、精确度一般）。对以 LLM 读片段为主的检索场景足够；
如需更高精度可后续升级为逐字 token + 短语查询（`"苏 醒"`）。
"""

import re

# CJK 基本区 + 扩展A + 兼容表意文字（汉字）
_CJK_RUN = re.compile(r'[一-鿿㐀-䶿豈-﫿]+')
# 含引号/冒号(列过滤)/加权(^)等结构的高级查询 → 原样透传（逐字拆会破坏语义）
_FTS_STRUCTURAL = re.compile(r'["():]')
_FTS_BOOL = {"AND", "OR", "NOT", "NEAR"}


def fts_prepare(text: str) -> str:
    """索引文本预处理：把每段连续汉字拆成逐字 token（空格分隔）

    非汉字部分（拉丁字母、数字、标点）原样保留，unicode61 照常处理。
    """
    if not text:
        return text or ""
    return _CJK_RUN.sub(lambda m: " ".join(m.group(0)), text)


def fts_query(query: str) -> str:
    """查询词预处理：逐项处理，汉字拆字 + 保留 FTS 运算符

    - 布尔运算符（AND/OR/NOT/NEAR）、括号、后缀 `*`（前缀查询）原样保留：
      `青见 AND 沈书言` → `青 见 AND 沈 书 言`，可命中；
    - 含引号（短语）、冒号（列过滤）、`^`（加权）→ 原样透传，交给 FTS 本身
      （这类查询里的中文因 unicode61 不分词而无法逐字命中，属已知局限）。
    """
    if not query:
        return query or ""
    if _FTS_STRUCTURAL.search(query):
        return query
    out = []
    for p in query.split():
        u = p.upper()
        if u in _FTS_BOOL:
            out.append(u)
            continue
        pre = post = ""
        if p.startswith("("):
            pre = "("
            p = p[1:]
        if p.endswith(")"):
            post = ")"
            p = p[:-1]
        if p.endswith("*"):
            post = "*" + post
            p = p[:-1]
        out.append(pre + fts_prepare(p) + post)
    return " ".join(out)
