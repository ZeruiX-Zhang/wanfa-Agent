---
title: "Context Engineering(上下文工程)"
type: concept
status: draft
created: 2026-05-07
updated: 2026-05-07
source_count: 1
confidence: low
evidence_quality: secondhand
tags:
  - context-engineering
  - prompt-engineering
  - llm
---

# Context Engineering(上下文工程)

> 速查词条: [[wiki/glossary/context-engineering|Context Engineering 速查]]

## Summary

Context Engineering 指**管理一个 LLM 应用的整个上下文状态**——系统指令、可用工具、记忆、外部检索数据、消息历史、会话状态——而不仅仅是写好一句 prompt。

> ⚠️ 此定义来自 GPT 综述,原文称引自 Anthropic 但未给 URL。Wiki 视为 secondhand。

## Key Points

- 是对"prompt engineering"的扩展和取代:不再把模型行为归结为"写好 prompt 就行"。
- 关注点:**喂给模型看到的所有东西**——指令、工具描述、外部数据、对话历史、记忆——以及它们的组织方式、优先级、压缩策略。
- 这是 Agent 设计的底层方法论。

## Details

(待 Anthropic 一手 "Building Effective Agents" 博文 ingest 后展开。)

GPT 综述提到的对照:

| Prompt Engineering | Context Engineering |
|--------------------|---------------------|
| 关注一句指令的措辞 | 关注模型整个"视野"的组装 |
| 静态 | 动态、随会话演化 |
| 单点优化 | 系统性设计 |

(以上对照表也是 secondhand,需要核实。)

## Evidence

- `raw/articles/2026-05-07-gpt-how-to-become-top-ai-engineer.md`
- `wiki/sources/2026-05-07-gpt-how-to-become-top-ai-engineer.md`

Evidence status: **secondhand-via-gpt**

## Related

- [[agent]]
- [[rag]] — RAG 是 context engineering 的一种具体形态(动态注入检索结果)
- [[tool-calling]]

## Open Questions

- "Context Engineering" 是 Anthropic 创造的特定术语,还是行业共识?
- 它和 "system prompt design" / "memory architecture" 等已有概念是同义还是子集?
