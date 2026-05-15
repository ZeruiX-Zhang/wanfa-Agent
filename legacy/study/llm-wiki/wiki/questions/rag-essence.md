---
title: "RAG 的本质是什么?"
type: question
status: open
created: 2026-05-06
updated: 2026-05-06
source_count: 1
confidence: low
tags:
  - rag
  - open-question
  - essence
---

# RAG 的本质是什么?

## Direct Answer

**当前 Wiki 没有足够证据支持任何具体结论。**

这是用户在 2026-05-06 提出的开放问题,Wiki 中尚无原始资料(论文、博客、访谈、视频)被 ingest,因此无法基于证据作答。

下面只列**已知的待研究方向**,不是答案:

- RAG 是否本质上等于"把检索结果当作 prompt 的一部分"?
- 它和"长上下文窗口"在第一性原理上是同一件事还是不同?
- 它和经典 IR(Information Retrieval)+ 模板填充的区别在哪里?
- 它是一种"架构",还是一种"工程范式",还是一种"权宜之计"?

## Reasoning

(待证据出现后填写)

## Evidence Used

- `raw/notes/2026-05-06-rag-research-questions.md`(用户问题原文)
- `wiki/sources/2026-05-06-rag-research-questions.md`
- `raw/articles/2026-05-07-gpt-how-to-become-top-ai-engineer.md`(secondhand,提供了"什么时候用 RAG"的判断框架)
- `wiki/sources/2026-05-07-gpt-how-to-become-top-ai-engineer.md`

Evidence status: **secondhand-via-gpt** — 仍需要 Lewis et al. 2020 原论文等一手来源才能真正回答"本质是什么"。

**目前唯一的间接证据**:GPT 综述把 RAG 列为 "什么时候用 LLM call / RAG / tool calling / workflow / agent" 判断阶梯中的一档——这暗示行业把 RAG 当作"工具调用之前的轻量增强",而不是单独范式。但这是 LLM 转述,不是定论。

## Uncertainty

整个回答都是 unknown。当前 Wiki 不具备回答能力。

## Related Pages

- [[rag]] — 概念页
- [[rag-experts-mental-model]]
- [[rag-experts-debates]]
- [[rag-upper-and-lower-bounds]]
- [[rag-vs-no-rag-ceilings]]

## Suggested Next Step

把以下任一资料丢进 inbox:

1. RAG 原论文: Lewis et al. 2020, "Retrieval-Augmented Generation for Knowledge-Intensive NLP Tasks"(arXiv:2005.11401)→ `raw/inbox/urls.md`
2. Lilian Weng 关于 LLM 与外部知识的博客 → `raw/inbox/urls.md`
3. 任何你看到的、对 RAG 给出"本质性"定义的文章/视频 → 对应的 inbox 入口
