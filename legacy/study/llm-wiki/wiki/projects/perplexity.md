---
title: "Perplexity"
type: project
status: draft
created: 2026-05-07
updated: 2026-05-07
source_count: 1
confidence: low
evidence_quality: secondhand
tags:
  - project
  - search
  - rag
---

# Perplexity

## Summary

AI 答案引擎/搜索引擎——用户提问后搜索网络并给出"可验证来源支持的对话式答案"。GPT 综述把它作为"信息组织 + 信任机制"作为护城河的代表案例。

> ⚠️ Secondhand。原文称引自 Perplexity 官方帮助中心。

## Why It Matters in This Wiki

GPT 综述给的"启发":
> **AI 应用的护城河常在"信息组织方式"和"信任机制",不一定在模型参数。**

这是对 [[rag-essence]] 的间接启发——RAG 的核心价值可能不在"检索增强"本身,而在"可被引用、可被核实"。

## Evidence

- `raw/articles/2026-05-07-gpt-how-to-become-top-ai-engineer.md`
- `wiki/sources/2026-05-07-gpt-how-to-become-top-ai-engineer.md`

Evidence status: **secondhand-via-gpt**

## Related

- [[rag]]
- [[rag-essence]]
- [[cursor]] — 都是"重构原有工作流"的代表,搜索 vs 编程
- [[lovable]] — 同处 AI 应用层
- [[langchain]] — 后者是基础设施,前者是终端搜索产品

## Open Questions

- Perplexity 的引用机制具体怎么做?是 retrieval-then-cite,还是 generate-then-verify?
