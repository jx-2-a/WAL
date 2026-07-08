"""WAL GUI 主题 — 颜色、字体规格"""

# ── 颜色 ───────────────────────────────────────────
BG_DARK      = "#1a1a2e"
BG_MID       = "#16213e"
BG_INPUT     = "#0f3460"
FG_PRIMARY   = "#e0e0e0"
FG_SECONDARY = "#a0a0c0"
FG_ACCENT    = "#e94560"
FG_GREEN     = "#50fa7b"
FG_YELLOW    = "#f0c040"

# ── 字体规格（tkinter 原生元组格式，避免创建 root 前实例化）──
FONT_FAMILY = "Cascadia Code"
FONT_NORMAL = (FONT_FAMILY, 11)
FONT_BOLD   = (FONT_FAMILY, 11, "bold")
FONT_BOLD_14 = (FONT_FAMILY, 14, "bold")
FONT_SMALL  = (FONT_FAMILY, 10)
FONT_SIZE   = 11  # 向后兼容
