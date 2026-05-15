---
name: quick-lookup
type: search_strategy
metadata:
  category: lookup
  label_zh: 快速查询
  label_en: Quick Lookup
  intent_signals:
    - 快速查询
    - 简单问题
    - 是什么
    - 怎么做
    - 如何
    - 什么意思
    - what is
    - how to
    - quick question
    - define
    - meaning of
  source_rules:
    preferred_categories:
      - general
      - ai_tech
    min_trust_score: 0.6
    max_sources: 3
  score_weights:
    authority: 0.15
    freshness: 0.20
    relevance: 0.40
    evidence_density: 0.10
    uniqueness: 0.05
    verifiability: 0.10
  post_processing:
    - deduplicate_by_title
    - prefer_concise
---

# 快速查询搜索策略

适用于用户提出简单、直接的问题，需要快速获得准确答案的场景。该策略优先选择高相关性结果，减少检索源数量以提升响应速度。

## 适用场景

- 用户提出定义类问题（"什么是 X"、"X 是什么意思"）
- 用户提出操作类问题（"怎么做"、"如何实现"）
- 需要快速、简洁的答案而非深度分析

## 策略特点

### 源选择
- 选择通用知识和技术类来源
- 最低信任分数要求 0.6，平衡速度与质量
- 最多检索 3 个来源，快速聚焦

### 评分权重
- **相关性 (0.40)**：最高权重，确保结果直接回答问题
- **时效性 (0.20)**：较高权重，优先最新信息
- **权威性 (0.15)**：适度关注，不过度限制来源
- **可验证性 (0.10)**：适度关注，确保答案可靠
- **证据密度 (0.10)**：轻微关注，简洁优先
- **独特性 (0.05)**：最低权重，少量来源无需过度去重

### 后处理
- 按标题去重，避免重复结果
- 优先选择简洁、直接的内容
