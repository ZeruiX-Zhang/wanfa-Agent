---
title: "Wiki Index"
type: map
status: stable
created: 2026-05-06
updated: 2026-05-06
tags:
  - index
  - navigation
---

# Wiki Index

## Purpose

这是我的个人通用学习型 Wiki,基于 Karpathy 的 LLM Wiki 思路:
- `raw/` 存原始资料(只读、不可改)
- `wiki/` 存我从原始资料中提炼出来的结构化页面
- 由 Claude(在 CLAUDE.md 的规则下)长期维护、扩充、互链

主题暂未限定。随着我把资料丢进 `raw/`,主题地图会自然涌现。

---

## ★ 最常用的入口:Inbox(收件箱)

不知道资料该放哪?**统统扔到 `raw/inbox/`**,然后对 Claude 说 **"处理 inbox"**。

- [[inbox-processing-status]] — 看上次导了什么、有什么失败了、接下来要做什么
- 各类资料的具体放法,见 `raw/inbox/README.md`

---

## Main Maps

> 主题地图(把多个相关页面组织成一张全景图或学习路径)。
> Graph View 是自动平铺所有连接,主题地图是从中抽出"一条主线"。

- [[ai-engineering-map]] — AI 应用工程主题地图(2026-05-07,串联当前 17 个 AI 工程相关页面成一条学习主线)

---

## Core Concepts

> 可被反复链接的核心概念。

- [[rag]] — Retrieval-Augmented Generation(检索增强生成,draft)
- [[agent]] — Agent / 智能体(draft, secondhand)
- [[context-engineering]] — 上下文工程(draft, secondhand)
- [[evals]] — LLM/Agent 评估(draft, secondhand)
- [[tool-calling]] — 工具调用 / Function Calling(draft, secondhand)

---

## Key Questions

> 我反复会问、答案会随证据更新的问题。

- [[example-how-to-use-this-wiki]] — 这个 Wiki 该怎么用?(示例页,可作为模板)
- [[inbox-processing-status]] — 收件箱当前状态、最近一次导入、待人工处理
- [[wiki-health-check]] — Wiki 健康度体检 + Graph View 验证清单(2026-05-07)

### RAG 研究问题(2026-05-06 用户提出,均为 open)

- [[rag-essence]] — RAG 的本质是什么?(已补 secondhand 间接证据)
- [[rag-experts-mental-model]] — 顶级 RAG 工程师共同的思维模型?(已补候选人物)
- [[rag-experts-debates]] — 顶级 RAG 工程师之间的争论?
- [[rag-upper-and-lower-bounds]] — RAG 的上下限及成因?
- [[rag-vs-no-rag-ceilings]] — RAG vs 非 RAG 各自的天花板?

### 职业方向(2026-05-07 GPT 综述触发)

- [[top-ai-engineer-capabilities]] — 顶级 AI 应用工程师需要哪些能力?(secondhand)

---

## People

> 重要的研究者、作者、人物。

- [[harrison-chase]] — LangChain 联合创始人 + CEO(占位,secondhand)

---

## Organizations

> 公司、机构、研究组、社区。

- [[anthropic]] — Claude 模型提供方(占位,secondhand)
- [[openai]] — GPT 模型与开发者平台(占位,secondhand)

---

## Projects

> 项目、产品、系统、计划。

- [[langchain]] — LLM 应用开发框架(secondhand)
- [[cursor]] — AI 代码编辑器(Anysphere,secondhand)
- [[lovable]] — AI app builder(secondhand)
- [[perplexity]] — AI 答案引擎(secondhand)

---

## Important Claims

> 原子级、可被多页面引用的事实主张。

- (待创建)

---

## Contradictions / Needs Review

> 来源之间的冲突、未解决的争议。

- (待创建)

---

## Recent Sources

> 最近 ingest 的来源摘要。

- [[2026-05-07-gpt-how-to-become-top-ai-engineer]] — GPT 综述:如何成为顶级 AI 应用工程师(secondhand,2026-05-07 ingest)
- [[2026-05-06-rag-research-questions]] — 用户首批 RAG 研究问题清单(5 条 open question)

---

## Glossary

> 短小的术语词条。

- [[rag]] — Retrieval-Augmented Generation
- [[agent]] — Agent 速查
- [[context-engineering]] — Context Engineering 速查
- [[evals]] — Evals 速查
- [[tool-calling]] — Tool Calling / Function Calling 速查

---

## Maintenance Notes

- Last lint: 未做
- Last inbox import: 2026-05-07(导入 1 篇 GPT 综述 → 5 个新概念页 + 1 个新 question 页 + 1 个人物页 + 4 个项目页 + 2 个组织占位页 + 4 个 glossary,并给已有 RAG 问题补 secondhand 证据)
- Major gaps:
  - **整个 Wiki 没有一手来源**——所有内容都是用户笔记 + 一份 GPT 综述,所有 confidence 都是 low
  - Anthropic / OpenAI 一手文档完全缺失,但被 Wiki 多处引用
  - 没有任何主题地图(`wiki/maps/`)
- Next recommended actions:
  1. **最高优先**:ingest 一份一手资料,从根本上改善 evidence 质量。最低成本起点:Anthropic "Building Effective Agents" 博文 → 它能同时给 [[agent]] / [[context-engineering]] / [[evals]] 三个概念页都补一手证据
  2. ingest RAG 原论文(arXiv:2005.11401)给 5 个 RAG 问题页补一手证据
  3. ingest 任意一份 Harrison Chase / Cursor 创始人 / Jerry Liu 的访谈,把 [[rag-experts-mental-model]] 从"全 secondhand"提升一档
