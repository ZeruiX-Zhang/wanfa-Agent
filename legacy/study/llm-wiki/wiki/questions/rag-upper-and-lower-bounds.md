---
title: "RAG 的能力上下限分别是什么?为什么会有这些边界?"
type: question
status: open
created: 2026-05-06
updated: 2026-05-06
source_count: 1
confidence: low
tags:
  - rag
  - open-question
  - bounds
  - limitations
---

# RAG 的能力上下限分别是什么?为什么会有这些边界?

## Direct Answer

**当前 Wiki 没有足够证据支持任何具体结论。**

用户的问题包含两个部分:

1. **下限**(low-effort 也能做好的事):简单实现就能达到的效果,以及为什么这么简单也能 work
2. **上限**(再怎么复杂也突破不了的事):工程边界和原理边界,以及它们为什么存在

回答这两端各自需要不同类型的证据。

## Reasoning

(待证据出现后填写)

可能的"下限"候选(待验证):

- 单文档问答(把文档塞进上下文,模型直接回答)
- 内部知识库的 FAQ 检索
- 代码仓库的语义搜索
- 简单的"参考资料注入"任务

可能的"上限"候选(待验证):

- 多跳推理(multi-hop reasoning):需要跨多个文档串联事实
- 时效性极强的问题(检索库还没来得及更新)
- 需要"全局综合"的问题(不是某个 chunk 能答的,而是要扫遍语料)
- 检索器召回失败导致的"沉默错误"(retriever 错了,generator 看不出来)

可能的"边界为什么存在"(待验证):

- chunking 把上下文切碎导致语义丢失
- embedding 空间无法表达细粒度概念区分
- generator 即使看到证据也可能忽略
- retriever 的训练分布与查询分布不匹配

以上**全部是假设**,需要论文 + 工程实战经验佐证。

## Evidence Used

- `raw/notes/2026-05-06-rag-research-questions.md`(用户问题原文)
- `wiki/sources/2026-05-06-rag-research-questions.md`(对应来源摘要)

Evidence status: **needs-source**

## Uncertainty

整个答案是 unknown。

## Related Pages

- [[rag]]
- [[rag-essence]]
- [[rag-experts-mental-model]]
- [[rag-experts-debates]]
- [[rag-vs-no-rag-ceilings]]

## Suggested Next Step

下面这类材料对回答此问题最有用,推荐丢进 inbox:

- "RAG failure modes" / "为什么我的 RAG 不 work" 这类工程复盘
- 关于 multi-hop QA 评测的论文(HotpotQA, MuSiQue 等)
- 大公司(如 Notion / Perplexity / 各种 enterprise search 厂商)的工程博客
- 反向案例:**不该用 RAG 但用了导致失败**的故事
