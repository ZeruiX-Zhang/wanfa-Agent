---
title: "AI 应用工程主题地图"
type: map
status: stable
created: 2026-05-07
updated: 2026-05-07
tags:
  - map
  - ai-engineering
  - learning-path
---

# AI 应用工程主题地图

## Purpose

这张地图回答一个问题:**"如果我想从零开始研究 AI 应用工程,我应该按什么顺序看 Wiki 里这些页面?"**

它把当前 Wiki 中所有 AI 工程相关页面织成一条**有先后、有因果**的主线,而不是 Graph View 那种"全部摊平"。

> ⚠️ 当前 Wiki 中所有 AI 工程相关页面都是 secondhand(基于一份 GPT 综述),整个地图的 confidence 都是 low。地图的**结构**是稳的,但**节点内容**还需要一手资料填充。

---

## 主线脉络(从问题到能力)

```
"如何成为顶级 AI 工程师" 这个问题
        ↓
理解四个核心概念(RAG / Agent / Context / Tools)
        ↓
看这些概念在真实产品中如何被使用
        ↓
认识把这些概念变成产品的人和组织
        ↓
回到 RAG,深入它的 5 个核心问题
        ↓
形成自己的判断
```

---

## 节点(按主线顺序)

### 0. 入口

- [[top-ai-engineer-capabilities]] — 顶级 AI 应用工程师需要哪些能力?

这是承接你 GPT 综述的核心问题页。所有后续节点都是为了回答它而展开。

### 1. 四个核心概念(必须先理解)

按"由抽象到具体"的顺序读:

- [[context-engineering]] — 最上层方法论:管理模型整个"视野"
- [[agent]] — Context engineering 的具体形态:能多步骤行动的 LLM 应用
- [[tool-calling]] — Agent 用来"干活"的核心机制
- [[rag]] — Tool calling 的一种特例:检索这一类工具

每页都有对应的速查 glossary 词条(`wiki/glossary/`),读不下去的时候可以先看 glossary。

### 2. 配套必修(没它前面都白搭)

- [[evals]] — 没有评估的 AI 项目都是 demo

### 3. 真实产品案例(把概念照进现实)

按"从基础设施到端用户"顺序读:

- [[langchain]] — 让别人能造 AI app 的框架(基础设施)
- [[cursor]] — 把 AI 嵌入工程师工作流(开发者工具)
- [[perplexity]] — 把检索 + 引用 + LLM 重组成搜索体验(消费产品)
- [[lovable]] — 让非工程师也能用自然语言造 app(降低门槛)

启发性观察(来自 GPT 综述,secondhand):
> **顶级 AI 应用通常不是新玩具,而是原有工作流的高杠杆重构。**

### 4. 人物与组织

- [[harrison-chase]] — LangChain 联合创始人 + CEO
- [[anthropic]] — 提出 "Building Effective Agents" 与 context engineering 概念(占位)
- [[openai]] — Agent 与 function calling 的官方定义来源(占位)

> 这是你建立"顶级 RAG 工程师候选名单"的起点(见 [[rag-experts-mental-model]])。

### 5. 回到 RAG:5 个核心问题

把"想成为顶级 AI 工程师"具体落到一个领域(RAG),会撞到 5 道墙:

- [[rag-essence]] — 本质是什么?
- [[rag-experts-mental-model]] — 顶级实践者的思维模型?
- [[rag-experts-debates]] — 顶级实践者之间的争论?
- [[rag-upper-and-lower-bounds]] — RAG 能做到什么、突破不了什么?
- [[rag-vs-no-rag-ceilings]] — 用 RAG 与不用 RAG 各自的天花板?

---

## 主要 Sources

- [[2026-05-07-gpt-how-to-become-top-ai-engineer]] — 触发本地图的 GPT 综述
- [[2026-05-06-rag-research-questions]] — 用户原创的 5 条 RAG 研究问题

---

## 还缺什么(诚实清单)

这张地图当前最大的问题:**所有节点内容都基于一份 LLM 综述,没有一手证据**。

按补足后能让多少节点升级排序:

| 想 ingest 的资料 | 升级哪些节点 |
|------------------|--------------|
| Anthropic "Building Effective Agents" 博文 | [[agent]] / [[context-engineering]] / [[evals]] 同时升级 |
| RAG 原论文 (Lewis et al. 2020) | [[rag]] + 5 个 RAG 问题页 |
| OpenAI function calling 文档 | [[tool-calling]] |
| Harrison Chase / Jerry Liu 一手访谈 | [[harrison-chase]] / [[langchain]] / [[rag-experts-mental-model]] |

---

## 与其它地图的关系

(目前 wiki/maps/ 下只有这一张。当 RAG / Agent 各自的节点超过 8 个时,可以单独拆出 [[rag-deep-dive-map]] 与 [[agent-architecture-map]]。)
