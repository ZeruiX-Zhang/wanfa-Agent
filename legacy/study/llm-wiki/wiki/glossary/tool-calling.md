---
title: "Tool Calling / Function Calling"
type: glossary
status: draft
created: 2026-05-07
updated: 2026-05-07
tags:
  - glossary
  - tool-calling
---

# Tool Calling / Function Calling

**一句话**: 让 LLM 能调用外部函数/API/服务的机制。模型在生成中产出"我要调用工具 X(参数 Y)",由宿主应用真正执行,把结果再喂回模型。

**核心配套**: 权限范围、失败回退、输入/输出 schema 校验、日志、人工审批节点。

详见 [[tool-calling]] 概念页。

Evidence status: **secondhand-via-gpt**
