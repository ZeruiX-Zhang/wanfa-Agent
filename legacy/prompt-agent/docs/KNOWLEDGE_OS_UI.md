# Knowledge OS UI

知识系统用于查看、搜索、审核和修正 Level Up 沉淀下来的知识。

## Sources

资料页显示 `knowledge_os/wiki/sources` 中的 source pages。

列表显示：

- 标题
- 文件名
- collection
- tags
- created_at
- source url domain

支持搜索、编辑标题、删除条目、打开 Markdown 和打开 Knowledge OS 文件夹。列表不显示超长绝对路径。

## Claims

断言页读取 `knowledge_os/claims/claims.jsonl`。

支持：

- 搜索 claim
- 按 status 过滤
- 编辑 claim text / status / confidence
- 查看 evidence / source_page
- 删除 claim

状态包括 `needs_review`、`supported`、`contradicted`、`outdated`、`disputed`。

## Graph Review

图谱审核页读取 `knowledge_os/graph/review_queue.jsonl`。

每个 review item 显示来源标题、摘要、claims 数量、nodes 数量、edges 数量、状态和创建时间。

操作：

- Approve：写入 graph nodes / edges
- Reject：标记 rejected
- Detail：查看 claims、nodes、edges、evidence
- Edit：通过 API 修改后再批准

## Graph

MVP 使用表格视图。

Nodes：

- id
- type
- name
- aliases
- source

Edges：

- from
- type
- to
- confidence
- source

## Personal

个人资料页读取 `knowledge_os/wiki/personal`。

文件：

- `profile.md`
- `preferences.md`
- `goals.md`
- `current_projects.md`
- `writing_style.md`
- `learning_style.md`
- `decision_history.md`

个性化关闭时，Prompt 不读取这些文件；用户仍然可以编辑和保存。

## Logs

日志页读取 `knowledge_os/log.md`，用于查看最近 Level Up、Prompt 是否使用 Knowledge OS、迁移和个性化读取相关记录。

## 审核 Level Up 结果

1. 右键或接口执行 Level Up。
2. Sources 页面查看保存的 source page。
3. Claims 页面检查抽取的 claim。
4. Graph Review 页面打开详情。
5. 修改不准确内容。
6. Approve 后写入 graph。

