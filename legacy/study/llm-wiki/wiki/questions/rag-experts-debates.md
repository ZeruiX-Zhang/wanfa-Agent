---
title: "顶级 RAG 工程师之间存在哪些争论?"
type: question
status: open
created: 2026-05-06
updated: 2026-05-06
source_count: 1
confidence: low
tags:
  - rag
  - open-question
  - debates
  - contradictions
---

# 顶级 RAG 工程师之间存在哪些争论?

## Direct Answer

**当前 Wiki 没有足够证据支持任何具体结论。**

要回答这个问题,需要先回答前一个 [[rag-experts-mental-model]] —— 在没有"顶级工程师群体"画像的前提下,无法判定"他们之间"在争什么。

## Reasoning

(待证据出现后填写)

业界确实存在多组对立观点,但 Wiki 尚未 ingest 任何一份能引用的来源,所以以下方向只作为**未来要查证的候选议题**列出:

- **长上下文 vs RAG**:有了 1M+ tokens 的上下文窗口后,RAG 是否还有必要?
- **微调 vs RAG**:把领域知识 fine-tune 进模型 vs 检索注入,各自的边界在哪?
- **agentic RAG vs naive RAG**:多轮检索 + 工具调用是否一定优于单轮 retrieve-then-generate?
- **embedding-based vs hybrid (BM25 + dense)**:稠密向量是否始终更好?
- **chunking 策略之争**:固定窗口 / 语义切分 / 层级 chunking 哪个更鲁棒?
- **rerank 必要性**:rerank 模型是关键组件还是可省略?

每一条争论一旦有证据落地,应该转为 `wiki/contradictions/` 下的一页。

## Evidence Used

- `raw/notes/2026-05-06-rag-research-questions.md`(用户问题原文)
- `wiki/sources/2026-05-06-rag-research-questions.md`(对应来源摘要)

Evidence status: **needs-source**

## Uncertainty

整个答案是 unknown。上面列出的 6 个方向只是**待查议题**,不是已知争论。

## Related Pages

- [[rag]]
- [[rag-experts-mental-model]]
- [[rag-vs-no-rag-ceilings]]

## Suggested Next Step

每当你看到任何文章/视频里有"两个工程师对 RAG 看法不同"的迹象,把它丢进 `raw/inbox/urls.md` 或 `raw/inbox/clippings.md`(摘录金句 + 来源)。Claude 在 ingest 时会自动创建 `wiki/contradictions/` 页面。
