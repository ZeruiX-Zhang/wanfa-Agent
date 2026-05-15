---
title: "顶级 RAG 工程师共同的思维模型是什么?"
type: question
status: open
created: 2026-05-06
updated: 2026-05-06
source_count: 1
confidence: low
tags:
  - rag
  - open-question
  - mental-model
  - practitioners
---

# 顶级 RAG 工程师共同的思维模型是什么?

## Direct Answer

**当前 Wiki 没有足够证据支持任何具体结论。**

要回答这个问题,Wiki 至少需要:

1. 一组可被合理称为"顶级 RAG 工程师"的人(以及为什么算"顶级"的判定依据)
2. 他们公开表达过的关于 RAG 的观点(博客、播客、访谈、推文、技术大会演讲)
3. 跨多个来源的一致性 / 重叠模式

以上三类材料目前 Wiki 中**全部为零**。

## Reasoning

(待证据出现后填写)

可能的回答框架(不是答案,只是待验证的假设):

- 把 RAG 看作"上下文工程"而非"搜索系统"?
- 把 retrieval 质量当作首要瓶颈,而不是 generation 质量?
- 把 chunking、embedding、reranking 视为三个独立可优化的工程模块?
- 把 RAG 视为可被微调或长上下文逐步替代的过渡方案?

## Evidence Used

- `raw/notes/2026-05-06-rag-research-questions.md`(用户问题原文)
- `wiki/sources/2026-05-06-rag-research-questions.md`
- `raw/articles/2026-05-07-gpt-how-to-become-top-ai-engineer.md`(secondhand,提供了候选人物清单)
- `wiki/sources/2026-05-07-gpt-how-to-become-top-ai-engineer.md`

Evidence status: **secondhand-via-gpt**(从 needs-source 升级,但仅靠一份 LLM 综述,仍需一手访谈)

候选人物已建页:
- [[harrison-chase]] / [[langchain]] — "做让别人更容易做 AI app 的基础设施"
- [[cursor]] — "嵌入真实工作流而非做新玩具"
- [[lovable]] / [[perplexity]] — 案例参考

## Uncertainty

- 谁算"顶级工程师"本身就是开放定义,需要先确立判定标准。
- 即使找到他们的公开发言,"思维模型"通常需要从多次表述中归纳,不是一篇博客能给出的。

## Related Pages

- [[rag]]
- [[rag-essence]]
- [[rag-experts-debates]]
- [[rag-upper-and-lower-bounds]]
- [[rag-vs-no-rag-ceilings]]

## Suggested Next Step

先做**人物清单**,而不是直接找答案:

- 把任何你认为可能是"顶级 RAG 工程师"的人名,粘到 `raw/inbox/notes.md` 里作为一条新笔记。
- 或者把他们的博客/Twitter/播客链接粘到 `raw/inbox/urls.md`。
- Claude 在下次 ingest 时会建 `wiki/people/` 页面,逐步累积证据。

候选起点(由 Wiki 列出而非证据支持):Jerry Liu (LlamaIndex)、Harrison Chase (LangChain)、Lance Martin (LangChain)、Greg Kamradt、相关 LLM 应用初创公司创始人。
