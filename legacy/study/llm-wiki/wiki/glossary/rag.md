---
title: "RAG"
type: glossary
status: draft
created: 2026-05-06
updated: 2026-05-06
source_count: 0
confidence: low
tags:
  - glossary
  - rag
---

# RAG

**全称**: Retrieval-Augmented Generation(检索增强生成)。

**一句话**: 在大模型生成回答之前,先从外部资料库里检索相关片段,把检索结果一起放进 prompt,让模型基于这些证据来回答。

**为什么要这么做**(直觉而非证据):
- 模型本身记不住所有事,且不知道训练截止后的新事
- 把"检索什么"做成可控的工程模块,比把所有知识塞进模型参数更灵活、更可解释

**最小架构组成**(需后续证据确认):
检索器 (retriever) → 切块/嵌入索引 → (可选) 重排器 (reranker) → 生成器 (generator,通常是 LLM)。

**Wiki 中的展开**: 见 [[rag]] 概念页与相关 [[rag-essence]] 等问题页。

Evidence status: **needs-source**(本词条目前没有外部来源支撑,只是占位定义)。
