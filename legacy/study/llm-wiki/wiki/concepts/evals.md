---
title: "Evals(LLM/Agent 评估)"
type: concept
status: draft
created: 2026-05-07
updated: 2026-05-07
source_count: 1
confidence: low
evidence_quality: secondhand
tags:
  - evals
  - testing
  - llm
  - agent
---

# Evals(LLM / Agent 评估)

> 速查词条: [[wiki/glossary/evals|Evals 速查]]

## Summary

Evals 指**专门为 LLM / Agent 系统设计的测试方法**:用数据集、自动评分、人工审核、回归测试等手段来量化生成式 AI 系统的准确性、性能、可靠性。

GPT 综述给出的核心论点:**没有 evals 的 AI 项目通常只是 demo**。

> ⚠️ Secondhand。原文称引自 OpenAI 评估指南、LangChain Agent evaluation checklist、Microsoft Foundry Agent evaluators,但均未给 URL。

## Key Points

- 传统软件测试不够用:同一输入可能产生不同输出,需要专门方法。
- 可分类:offline(线下数据集)/ online(生产流量)/ ad-hoc(临时调试)。
- 应该接入 CI/CD,prompt 与工具定义必须版本化。

## Details(全部 secondhand,待一手核实)

GPT 综述提到顶级 AI 工程师必须会做的 evals 类型:

- golden dataset(黄金标准数据集)
- failure taxonomy(失败分类法)
- LLM-as-judge(用 LLM 当评分员)
- human review calibration(人审与机器分的对齐校准)
- tool-call accuracy eval(工具调用准确率)
- regression suite(回归测试集)
- prompt/version tracking
- production trace replay(生产 trace 回放)
- cost/latency/quality dashboard

## Evidence

- `raw/articles/2026-05-07-gpt-how-to-become-top-ai-engineer.md`
- `wiki/sources/2026-05-07-gpt-how-to-become-top-ai-engineer.md`

Evidence status: **secondhand-via-gpt**

## Related

- [[agent]]
- [[rag]] — RAG 系统的 retriever 准确率本身就是关键 eval 维度

## Open Questions

- LLM-as-judge 在哪些场景下可信、哪些场景下偏差严重?
- "tool-call accuracy" 业界有没有标准化数据集和评分方法?
