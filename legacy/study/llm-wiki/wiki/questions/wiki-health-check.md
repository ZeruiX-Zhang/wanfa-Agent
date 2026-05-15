---
title: "Wiki 健康度体检(2026-05-07)"
type: question
status: stable
created: 2026-05-07
updated: 2026-05-07
tags:
  - meta
  - lint
  - health-check
---

# Wiki 健康度体检(2026-05-07)

> 这份报告对应你刚装好 Obsidian、第一次打开 Graph View 的时刻。
> 它告诉你**图谱里能看到什么、不能看到什么、修了什么、为什么这样修**。

---

## Executive Summary

| 维度 | 数值 / 状态 |
|------|------------|
| 总页面数 | ~33 个 wiki 页面 + 8 个模板(模板不进图谱) |
| 双链总数 | 138+(本次 lint 后增加约 15) |
| 孤立节点 | **修前 5 个 → 修后 0 个**(全部连上) |
| 坏链 | **修前 3 个 → 修后 0 个**(全部修复) |
| 整体证据质量 | low(89% 节点带 `secondhand-via-gpt` 标签,等一手资料) |
| 主题集群 | 4 个清晰簇:RAG / Agent / 产品案例 / 元数据 |

---

## Problems Found(本次发现)

### 🔴 孤立节点(没人链向 + 自己也很少链出)

修前:
1. `wiki/glossary/rag.md`
2. `wiki/glossary/agent.md`
3. `wiki/glossary/evals.md`
4. `wiki/glossary/context-engineering.md`
5. `wiki/glossary/tool-calling.md`

它们是"速查词条",自己只链向对应 concept 页,但没有页链回来——在 Graph View 里会显示为漂浮的孤立小点。

**修复方式**:在每个 concept 页顶部加一行 "速查词条: [[wiki/glossary/xxx]]" 反向链。用全路径而不是裸文件名,避免与同名 concept 页歧义。

### 🟠 坏链(链向不存在的目标)

修前:
1. `[[index]]`(在 example-how-to-use-this-wiki)→ vault 里没有 index.md 在根目录,该页应链 `wiki/index.md`
2. `[[wiki/glossary/]]`(在 ai-engineering-map)→ 这是路径不是文件,改写为普通文字 + 反引号
3. `[[wiki/claims/]]`(在 inbox-processing-status)→ 同上

**修复方式**:全部改为正确链接或纯文本路径标记。

### 🟡 弱连接群(同主题页之间互链不全)

修前:5 个 RAG 问题页(rag-essence / rag-experts-mental-model / rag-experts-debates / rag-upper-and-lower-bounds / rag-vs-no-rag-ceilings)只是部分互链——其中 3 个页面缺 1-2 条横向链接。

**修复方式**:让 5 个 RAG 问题互相链全(完全图,K5),这样 Graph View 里它们会形成紧密簇。

类似地,4 个产品页(langchain / cursor / lovable / perplexity)修前几乎不互链,修后形成"产品案例"簇。

### ⚪ 完全空的目录(暂时性,非问题)

- `wiki/contradictions/` — 完全空,等出现真矛盾时才建
- `wiki/claims/` — 完全空,等找到一手报告再单独建
- `wiki/people/` — 只有 1 页(harrison-chase)
- `wiki/sources/` — 只有 2 页

这些不是问题,是 Wiki 早期状态。Graph View 不会显示空目录。

---

## Recommended Fixes(已全部完成)

| # | 修复 | 影响 |
|---|------|------|
| 1 | 5 个 concept 页顶部加 glossary 反向链 | 5 个孤立 glossary 节点连上 |
| 2 | 修 3 处坏链 | Graph View 不再有虚线节点 |
| 3 | 5 个 RAG 问题页完全互链 | 形成清晰的 RAG 集群 |
| 4 | 4 个产品页之间补横向链 | 形成清晰的"产品案例"集群 |
| 5 | top-ai-engineer-capabilities 加链 ai-engineering-map | 主题地图被反链 |
| 6 | inbox-processing-status 加链 example-how-to-use-this-wiki | example 不再孤立 |

---

## High-Priority Missing Pages

按"做了之后图谱信息密度提升最大"排序:

1. **一手 Anthropic / OpenAI 内容**——会大幅提升 [[agent]] [[context-engineering]] [[evals]] [[tool-calling]] 的 confidence
2. **`wiki/maps/rag-deep-dive-map.md`**——当 RAG 节点超过 8 个时建,把现有 5 个 RAG 问题织成深度学习路径
3. **`wiki/maps/learning-path-90-days.md`**——把 GPT 综述里的 90 天计划做成可视化路径

---

## Contradictions to Review

目前 0 条已识别矛盾。当 [[rag-experts-debates]] 拿到第一份证据后,应该会出现 3-5 条候选(长上下文 vs RAG / 微调 vs RAG / agentic vs naive RAG 等)。

---

## Orphan Pages(修复后状态)

✅ 修复后无孤立节点。

如果你打开 Obsidian Graph View 看到飘在外面的孤立小点,应该是:
- `raw/inbox/2026-05-07-0948-notes-如何成为顶级AI工程师.md`(已被 graph 配置排除,但 Obsidian 1.x 偶尔仍会显示一帧——刷新一下消失)
- `_templates/*`(已被 graph 配置排除)

---

## Broken or Weak Links(修复后状态)

✅ 已知坏链全部修复。

如果以后写新页面时担心拼错链接名,可以在 Obsidian 里:
- **设置 → 文件与链接 → "Detect all file extensions"** 开启,Obsidian 会标红坏链
- 或安装 **Linter** 社区插件(可选)

---

## Source Coverage Gaps

| 概念/问题 | 已有证据 | 缺什么 |
|----------|----------|--------|
| [[rag]] 与 5 个 RAG 问题 | 用户笔记 + GPT 综述(secondhand) | RAG 原论文(Lewis 2020)、Lilian Weng 博客 |
| [[agent]] | GPT 综述 | Anthropic Building Effective Agents、OpenAI Agent docs |
| [[context-engineering]] | GPT 综述 | Anthropic 关于 context engineering 的官博 |
| [[evals]] | GPT 综述 | OpenAI Evals 文档、LangSmith 文档 |
| [[tool-calling]] | GPT 综述 | OpenAI function calling 文档、MCP 协议 |
| [[harrison-chase]] | GPT 综述 | 至少一份他公开访谈或博客 |
| 产品页 ×4 | GPT 综述 | 各家官网/博客一手内容 |

---

## Next 5 Actions

按 ROI 排序,只做一件事就走第 1 件:

1. **🥇 ingest Anthropic "Building Effective Agents"** — 一篇升级 3 个概念页(agent / context-engineering / evals)
2. 🥈 ingest RAG 原论文(arXiv:2005.11401)— 升级 [[rag]] + 5 个 RAG 问题页
3. 🥉 ingest 任意一份 Harrison Chase / Jerry Liu 公开访谈 — 让 [[rag-experts-mental-model]] 不再纯 secondhand
4. 当 RAG 节点超过 8 个时,建 [[wiki/maps/rag-deep-dive-map]]
5. 把 GPT 综述的 90 天计划做成可视化主题地图(`wiki/maps/learning-path-90-days.md`)

---

## 怎么验证修复有效

打开 Obsidian → 按 <kbd>Ctrl</kbd> + <kbd>G</kbd> → 看图:

- 你应该看到**约 30 个主节点 + 几条主线**,而不是一堆散点
- 颜色应该按 .obsidian/graph.json 配色:🟡概念 / 🟠问题 / 🟫来源 / 🟤实体 / ✨地图
- **没有飘在边缘的小孤点**(除了 inbox 文件,如果显示了就刷新一下)
- 鼠标拖动节点会有"弹簧感",说明 forces 配置生效

如果 graph 颜色没生效:
- Settings → 关闭再打开 vault,或 Ctrl+P → "Reload app without saving"
