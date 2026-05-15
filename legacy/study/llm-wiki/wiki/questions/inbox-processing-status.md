---
title: "Inbox Processing Status"
type: question
status: stable
created: 2026-05-06
updated: 2026-05-07
tags:
  - meta
  - inbox
  - howto
---

# Inbox Processing Status

---

## 最近一次处理

时间: 2026-05-07

## 本次摘要

- 成功导入: 1(GPT 综述长文 → 重新分类为 article)
- 失败: 0
- 跳过(重复): 0
- 待人工处理: 1(全 Wiki 缺一手证据,见下)

---

## 处理记录(累计,最近 200 条)

| 时间 | 来源 | 类型 | 结果 | 归档位置 / 失败原因 |
|------|------|------|------|---------------------|
| 2026-05-07 | `raw/inbox/2026-05-07-0948-notes-如何成为顶级AI工程师.md` (via inbox-uploader.html) | 用户标 note,实际为 GPT 长篇综述 → 重分类为 article | done(secondhand) | `raw/articles/2026-05-07-gpt-how-to-become-top-ai-engineer.md`<br>+ `wiki/sources/...`<br>+ 4 × `wiki/concepts/` (agent / context-engineering / evals / tool-calling)<br>+ 1 × `wiki/people/harrison-chase.md`<br>+ 4 × `wiki/projects/` (langchain / cursor / lovable / perplexity)<br>+ 2 × `wiki/organizations/` (anthropic / openai 占位)<br>+ 1 × `wiki/questions/top-ai-engineer-capabilities.md`<br>+ 4 × `wiki/glossary/`<br>+ 给已有 [[rag-essence]] [[rag-experts-mental-model]] 补 secondhand evidence |
| 2026-05-06 | `raw/inbox/notes.md` (5 行 RAG 研究问题) | note(用户原创研究问题) | done | `raw/notes/2026-05-06-rag-research-questions.md` 等 9 个页面 |

---

## 需要人工处理(check-list)

- [ ] **🔥 最优先:全 Wiki 没有一手来源**。当前所有 evidence 不是用户笔记就是 LLM 综述,confidence 全部 low。建议下一份 inbox **必须是一手资料**(论文 / 一手博客 / 实战访谈)。最低成本三个候选:
  - Anthropic ["Building Effective Agents"](https://www.anthropic.com/research/building-effective-agents) — 一篇就能给 [[agent]] [[context-engineering]] [[evals]] 三个概念页补证据
  - RAG 原论文 [arXiv:2005.11401](https://arxiv.org/abs/2005.11401) — 给 5 个 RAG 问题页补一手定义
  - OpenAI [function calling 文档](https://platform.openai.com/docs/guides/function-calling) — 给 [[tool-calling]] 概念页补证据
- [ ] GPT 综述里的 **6 组数据点**全部 secondhand,值得保留意识但暂不入 `wiki/claims/`:Stanford AI Index 2026、McKinsey 2025、MIT NANDA、Stack Overflow 2025、Cursor 估值、Lovable ARR — 等找到对应一手报告再单独建 claim 页
- [ ] [[anthropic]] 与 [[openai]] 当前是占位页,只是为了让其他页能 `[[link]]`。等到 ingest 一手资料后扩展为完整组织页

---

## 常见失败类型与对策

| 失败标签 | 含义 | 你可以怎么办 |
|----------|------|--------------|
| `failed: paywall` | 网页要登录或付费 | 用 inbox-uploader 文件标签拖原文进去,或 Web Clipper 在登录浏览器手动保存 |
| `failed: blocked` | 网站反爬 | 同上 |
| `failed: 404` | 链接已失效 | 找替代链接 |
| `needs-ocr` | PDF 扫描版 | OCR 后重新上传 |
| `needs-transcript` | 视频找不到字幕 | Whisper / 飞书妙记 转后上传 |
| `needs-fulltext` | 网页只抓到摘要 | 浏览器完整复制后粘 inbox |
| `needs-source` | 摘录没标来源 | 在 inbox 补来源 |
| `secondhand-via-gpt` | 来自 LLM 综述,不是一手资料 | 标注 confidence: low,等一手来源 ingest 后升级 |
| `skipped: duplicate of <path>` | 已经导过 | 不用做事 |

---

## 下一步建议

> 不熟悉 Wiki 怎么用?先看 [[example-how-to-use-this-wiki]]。

**最值得做的一件事**: 把这条粘到 `raw/inbox/urls.md`(或用 inbox-uploader 链接标签追加),然后说"处理 inbox":

```
- https://www.anthropic.com/research/building-effective-agents  Anthropic 官方:Building Effective Agents
```

为什么是这一条:
- 它是**一手来源**(Anthropic 官博),能把当前 [[agent]] / [[context-engineering]] / [[evals]] 三个 secondhand 概念页一次性升级到 firsthand
- 它是 GPT 综述里被反复引用却没给 URL 的源头,补上它能解决最大的 evidence 缺口
- 它和 RAG 原论文相比覆盖面更广(原论文只对 [[rag-essence]] 一题有用)
