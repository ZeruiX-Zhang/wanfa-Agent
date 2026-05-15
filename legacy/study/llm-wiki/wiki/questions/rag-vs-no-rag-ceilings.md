---
title: "用 RAG 与不用 RAG,各自的天花板出现在什么场景?"
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
  - tradeoff
---

# 用 RAG 与不用 RAG,各自的天花板出现在什么场景?

## Direct Answer

**当前 Wiki 没有足够证据支持任何具体结论。**

这个问题是 [[rag-upper-and-lower-bounds]] 的"对比版"——把 RAG 和"不 RAG"放在一起,看各自在哪类场景上撞墙、为什么。

## Reasoning

(待证据出现后填写)

提前列一份对比框架(只是结构,不是答案):

| 维度 | RAG 的天花板出现场景 | 不用 RAG(纯 LLM 或微调)的天花板出现场景 |
|------|-----------------------|-------------------------------------------|
| 知识时效 | retriever 库未更新 | 模型知识截止日期之后的事 |
| 知识规模 | embedding/index 工程成本暴涨 | 模型参数无法塞下海量长尾知识 |
| 知识私密性 | 检索系统能控制权限 | fine-tune 暴露训练数据风险 |
| 多跳推理 | 单轮检索抓不全证据 | 长上下文又贵又慢,且"中间遗忘" |
| 解释性 | 可以引用片段 | 黑箱,溯源难 |
| 时延与成本 | 多了一次检索往返 | 长上下文推理成本高 |

| 维度 | RAG 的能力出现限制的原因 | 不 RAG 的能力出现限制的原因 |
|------|--------------------------|------------------------------|
| 工程 | chunking/index/rerank 的链路误差累积 | context window 物理上限 |
| 算法 | retriever 与 generator 训练目标不一致 | 注意力机制对长文本退化 |
| 数据 | 检索库的覆盖度和清洗质量 | 训练数据的覆盖度 |

以上**仅为框架占位**,具体内容必须由 ingest 后的来源填充。

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
- [[rag-upper-and-lower-bounds]]

## Suggested Next Step

寻找"对比类"材料:

- 关于"long context vs RAG"的实证研究(2024 年起这类文章很多)
- 关于"fine-tune vs RAG"的工程权衡文章
- 业界已部署系统的复盘(为什么选 / 为什么不选 RAG)
