---
title: "Tool Calling / Function Calling(工具调用)"
type: concept
status: draft
created: 2026-05-07
updated: 2026-05-07
source_count: 1
confidence: low
evidence_quality: secondhand
tags:
  - tool-calling
  - function-calling
  - llm
  - agent
---

# Tool Calling / Function Calling(工具调用)

> 速查词条: [[wiki/glossary/tool-calling|Tool Calling 速查]]

## Summary

Tool calling(也叫 function calling)是**让 LLM 能够调用外部函数、API、服务、数据库**的机制。模型在生成回答中插入"我现在想调用工具 X(参数 Y)",由宿主应用真正执行,把结果再喂回模型继续生成。

> ⚠️ Secondhand,GPT 综述称引自 OpenAI 官方文档但未给 URL。

## Key Points

- 是 Agent 能"干活而不只是说话"的核心机制。
- OpenAI 官方文档(原文转述)将工具范畴扩展到 web search、file search、function calling、remote MCP 等多种形式。
- 工具调用必须配套设计:权限范围、失败回退、输入 schema 校验、输出 schema 校验、日志、人工审批节点。

## Details

(待 OpenAI 一手 function calling 文档 ingest 后展开。)

## Evidence

- `raw/articles/2026-05-07-gpt-how-to-become-top-ai-engineer.md`
- `wiki/sources/2026-05-07-gpt-how-to-become-top-ai-engineer.md`

Evidence status: **secondhand-via-gpt**

## Related

- [[agent]]
- [[context-engineering]]

## Open Questions

- 不同模型(OpenAI / Anthropic / Gemini)的 tool calling API 差异有多大?能不能写一份 polyglot 适配层?
- MCP(Model Context Protocol)与传统 function calling 的关系是什么?
