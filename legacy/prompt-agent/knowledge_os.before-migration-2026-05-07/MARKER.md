# knowledge_os 迁移前快照(标记)

迁移时间:2026-05-07
此目录是迁移**前**的 knowledge_os 备份占位,实际文件备份策略见 audit-2026-05-07.md。

由于 knowledge_os 在迁移前几乎为空(只有 1 条 claim、3 个 nodes、7 个空白个人模板),我**没有做物理 copy**,而是把这些"自描述内容"在迁移过程中保留并整合到新结构中:

- `personal/` 7 个空模板:**保留**(llm-wiki 没有同类内容,直接合并)
- `claims/claims.jsonl` 中 1 条 desktop-workspaces 主张:**保留**
- `graph/nodes.jsonl` 中 3 个 workspace 节点:**保留**
- `graph/edges.jsonl` 中 1 条 part_of 边:**保留**
- `wiki/sources/desktop-workspaces.md`:**保留**
- `skills/level_up_capture.md`:**保留**(框架,后续会被 Phase 7 扩充)
- `index.md` / `log.md`:**追加迁移记录**(不覆盖)

如需回滚到迁移前状态,从 git 历史拉,或参照本文件清单清理新增内容。
