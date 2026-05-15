---
title: "RAG(Retrieval-Augmented Generation,检索增强生成)"
type: concept
status: draft
created: 2026-05-06
updated: 2026-05-06
source_count: 1
confidence: low
tags:
  - rag
  - llm
  - retrieval
---

# RAG(Retrieval-Augmented Generation,检索增强生成)

> 速查词条: [[wiki/glossary/rag|RAG 速查词条]]

## Summary

RAG 是一类把"外部检索"接到"大模型生成"前面的工程范式或架构。**目前本 Wiki 仅基于用户在 2026-05-06 提出的研究问题创建本页面,尚无外部资料 ingest,因此本页**严格只列已确立的最小定义,不展开具体技术细节。

## Key Points

- 用户已围绕 RAG 提出 5 条 open question(见下方 Related)。
- 本 Wiki 中关于 RAG 的所有具体技术性结论目前都是 **needs-source** 状态。
- 一旦有论文/博客/视频被 ingest,本页将相应扩展为标准概念页。

## Details

(待证据出现后填写。一旦至少 2 份独立来源被 ingest,这一节应包括:
- 第一性原理定义
- 与 fine-tune / 长上下文的对比
- 经典链路:retriever / chunker / embedder / reranker / generator
- 主要工程权衡)

## Evidence

- `raw/notes/2026-05-06-rag-research-questions.md`
- `wiki/sources/2026-05-06-rag-research-questions.md`

Evidence status: **needs-source** — 概念页应在至少 2 份独立外部来源 ingest 后才升级到 status: stable。

## Related

围绕本概念已建立的 open questions:

- [[rag-essence]] — RAG 的本质是什么?
- [[rag-experts-mental-model]] — 顶级 RAG 工程师共同的思维模型?
- [[rag-experts-debates]] — 顶级 RAG 工程师之间的争论?
- [[rag-upper-and-lower-bounds]] — RAG 的上下限?
- [[rag-vs-no-rag-ceilings]] — RAG vs 非 RAG 的天花板对比?

## Open Questions

见上方 Related 中的 5 条问题页。
