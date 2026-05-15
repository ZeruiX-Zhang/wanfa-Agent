---
title: "Agent(智能体)"
type: concept
status: draft
created: 2026-05-07
updated: 2026-05-07
source_count: 1
confidence: low
evidence_quality: secondhand
tags:
  - agent
  - llm
  - architecture
---

# Agent(智能体)

> 速查词条: [[wiki/glossary/agent|Agent 速查词条]]

## Summary

在 LLM 应用语境下,Agent 指**能够自主规划、调用工具、与其他模型/服务协作、并保留状态来完成多步骤任务的系统**。它不是单次 prompt → response,而是有"决策循环"的应用。

> ⚠️ 当前定义来自一份 GPT 综述(secondhand),原文转述了 OpenAI 与 Anthropic 的官方文档,但**未给出可点击 URL**。本概念需要 Anthropic 与 OpenAI 一手文档 ingest 后才能升级 confidence。

## Key Points

- 核心区分:Agent = 规划 + 工具调用 + 状态管理 + 多步骤;普通 LLM 调用 = 单次 prompt-response。
- 行业重心从"prompt engineering"扩展到"context engineering"——管理系统指令、工具、外部数据、消息历史等完整上下文状态(出处:GPT 综述称引自 Anthropic,待核实)。
- 不是所有任务都该用 Agent。GPT 综述给出的判断框架:普通 LLM call → RAG → tool calling → workflow → autonomous agent → 人工审批,按风险与复杂度递增。

## Details

(待 Anthropic / OpenAI 一手文档 ingest 后展开。当前 Wiki 不做更细技术展开,以免传递 secondhand 信息。)

## Evidence

- `raw/articles/2026-05-07-gpt-how-to-become-top-ai-engineer.md`
- `wiki/sources/2026-05-07-gpt-how-to-become-top-ai-engineer.md`

Evidence status: **secondhand-via-gpt** — 必须找一手 OpenAI Agent 文档 + Anthropic "Building Effective Agents" 博文 ingest 后才能升级。

## Related

- [[rag]] — RAG 是 Agent 工具栏中"检索"那一类工具的实现
- [[tool-calling]] — Agent 能干活的核心机制
- [[context-engineering]] — Agent 设计的上层抽象
- [[evals]] — Agent 必须配的评估方法

## Open Questions

- "Agent" 是工程范式还是临时叫法?12-24 个月后这个词还存在吗?
- "Autonomous agent" 与 "workflow with tools" 的边界是什么?
