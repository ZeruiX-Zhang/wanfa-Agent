---
title: "RAG 研究问题清单"
source_type: note
url: ""
author: "Simone (用户本人)"
collected_date: 2026-05-06
processed_date: 2026-05-06
inbox_origin: "raw/inbox/notes.md(2026-05-06 首次填写)"
status: raw-imported
language: zh
tags:
  - rag
  - research-questions
  - draft
---

# RAG 研究问题清单

## 背景

用户在 inbox 第一次填写笔记时,一次性写下了 5 个关于 RAG(Retrieval-Augmented Generation,检索增强生成)的研究方向问题。这些问题不是已有结论,而是用户**主动提出、希望长期追踪和回答的问题**。

## 原始问题(逐条)

1. RAG 到底是什么,请说出它的本质。
2. 现在做 RAG 的最顶级的工程师,他们共同的思维模型是什么。
3. 他们之间是否有争论?他们各自的论点和论据是什么。
4. RAG 技术目前最主要的难点和无法突破的点(上限)在哪,能够不那么复杂地做的很好的事(下限)又在哪?上下限出现的主要原因是什么。
5. 做 RAG 和不 RAG 的场景,它们各自什么时候有比较明显的上限(天花板)?这两种技术出现上限的原因和限制条件是什么。

## 问题之间的结构

可以归纳为四个层次,从抽象到落地:

- **本质层**:问题 1 — RAG 的定义和第一性原理
- **思维模型层**:问题 2 — 顶级工程师对 RAG 的共同心智模型
- **论争层**:问题 3 — 这个领域内部的主要分歧
- **能力边界层**:问题 4、5 — RAG 与非 RAG 各自的上下限

## 备注

- 这是一份"问题地图"而非"答案清单"。Wiki 处理时应该:
  - 为每条问题生成 `wiki/questions/` 下的独立页面,带 `status: open`
  - 用 `[[RAG]]` 概念页串联所有问题
  - 在 `wiki/questions/` 中以本笔记作为共同 evidence
- 后续填充答案时,每个问题页都需要 evidence(论文、博客、访谈、产品文档等),目前 evidence 缺失。
