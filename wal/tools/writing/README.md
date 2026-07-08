# Writing Tools (写作工具)

52 个写作模式工具，按功能分类：

## 故事状态
| 工具 | 参数 | 说明 |
|------|------|------|
| `get_story_status` | — | 查看故事全貌：章节数、完成度、总字数 |
| `get_chapter_context` | chapter_number | 获取章节的完整写作上下文 |
| `get_chapter_context_text` | chapter_number | 精简版上下文（纯文本，适合粘贴给 LLM） |

## 章节/卷管理
| 工具 | 参数 | 说明 |
|------|------|------|
| `add_chapter` | title, [words, summary, notes, volume] | 添加新章节 |
| `delete_chapter` | number | 删除章节 |
| `set_chapter_status` | number, status | 设置章节状态 |
| `update_chapter_info` | number, **kwargs | 更新章节信息 |
| `add_volume` | title, [part_id, summary, theme, notes] | 添加卷 |
| `delete_volume` | volume_id | 删除卷 |
| `update_volume` | volume_id, **kwargs | 更新卷 |
| `list_volumes` | [part_id] | 列出所有卷 |
| `get_volume_context` | volume_id | 获取卷的写作上下文 |
| `add_part` | title, [summary, notes] | 添加部/篇 |

## 剧情管理
| 工具 | 参数 | 说明 |
|------|------|------|
| `list_plot_lines` | — | 列出所有剧情线及进度 |
| `plot_health_check` | — | 主线支线健康度检查 |
| `get_plot_tree` | — | 剧情层级树状图 |
| `add_plot_line` | title, [type, desc, theme] | 添加剧情线 |
| `update_plot_line` | plot_id, **kwargs | 更新剧情线 |
| `delete_plot_line` | plot_id | 删除剧情线 |
| `update_plot_point` | plot_id, point_id, status | 更新情节点状态 |
| `suggest_next_scene` | chapter_number | 基于剧情状态给出场景建议 |

## 伏笔
| 工具 | 参数 | 说明 |
|------|------|------|
| `add_foreshadowing` | description, [chapter, target, urgency, ...] | 添加伏笔 |
| `resolve_foreshadowing` | fw_id, chapter, [notes] | 回收伏笔 |
| `check_foreshadowing_health` | — | 伏笔健康度检查 |
| `update_foreshadowing` | fw_id, **kwargs | 更新伏笔 |

## 角色管理
| 工具 | 参数 | 说明 |
|------|------|------|
| `list_characters` | [role] | 列出所有角色 |
| `get_character` | char_id | 获取角色完整档案 |
| `add_character` | char_name, [role, bg, motivation] | 添加角色 |
| `update_character` | char_id, **kwargs | 更新角色 |
| `delete_character` | char_id | 删除角色 |
| `character_relationship_map` | — | 角色关系图谱 |
| `add_character_relationship` | char_a, char_b, type, [desc] | 添加关系 |
| `create_character_snapshot` | char_id, chapter, [...] | 创建角色快照 |
| `get_character_evolution` | char_id | 角色发展轨迹 |

## 场景导出
| 工具 | 参数 | 说明 |
|------|------|------|
| `write_scene_content` | chapter, scene_index, content | 写入场景正文 |
| `delete_scene` | chapter, scene_index | 删除场景 |
| `get_chapter_artifacts` | chapter | 获取章节产物 |

## 导出
| 工具 | 参数 | 说明 |
|------|------|------|
| `export_outline` | — | 导出大纲文本 |
| `export_chapter` | chapter, [format, offset, max_length] | 导出单章 |
| `export_novel_files` | output_dir, [mode, fmt, split, structure] | 导出全书文件 |
| `generate_chapter_summary` | chapter | 生成章节摘要 |
| `quick_review` | start, end, [topic] | 快速回顾 |

## 搜索/索引
| 工具 | 参数 | 说明 |
|------|------|------|
| `search_story_index` | query, [limit] | FTS5 全文搜索 |
| `update_story_info` | **kwargs | 更新故事元信息 |
| `set_writing_style` | style_text | 设置写作风格指南 |
| `add_custom_document` | title, content, [tags] | 添加自定义文档 |
| `get_custom_document` | doc_id | 获取文档 |
| `list_custom_documents` | [tags] | 列出文档 |
| `update_custom_document` | doc_id, **kwargs | 更新文档 |
| `delete_custom_document` | doc_id | 删除文档 |
