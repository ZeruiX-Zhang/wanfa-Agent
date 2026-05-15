---
name: deep-research
type: search_strategy
metadata:
  category: research
  label_zh: 深度研究
  label_en: Deep Research
  intent_signals:
    - 深入分析
    - 详细研究
    - 全面了解
    - 深度调研
    - 系统性分析
    - deep dive
    - comprehensive
    - thorough analysis
    - in-depth
    - detailed research
  source_rules:
    preferred_categories:
      - ai_tech
      - general
    min_trust_score: 0.8
    max_sources: 8
  score_weights:
    authority: 0.30
    freshness: 0.15
    relevance: 0.25
    evidence_density: 0.20
    uniqueness: 0.05
    verifiability: 0.05
  post_processing:
    - deduplicate_by_title
    - boost_peer_reviewed
    - require_citations
---

# 深度研究搜索策略

适用于需要全面、深入了解某个主题的搜索场景。该策略优先选择高权威性来源，增加检索源数量，并对结果执行严格的去重和引用要求。

## 适用场景

- 用户需要对某个技术或概念进行系统性研究
- 用户明确表达了"深入分析"、"全面了解"等意图
- 需要多角度、多来源的综合信息

## 策略特点

### 源选择
- 优先选择 AI 技术和通用知识类高可信来源
- 最低信任分数要求 0.8，确保来源质量
- 最多检索 8 个来源，覆盖面广

### 评分权重
- **权威性 (0.30)**：最高权重，确保结果来自权威来源
- **相关性 (0.25)**：高权重，确保结果与查询高度相关
- **证据密度 (0.20)**：重视信息密度，优先选择内容丰富的结果
- **时效性 (0.15)**：适度关注，允许经典内容
- **独特性 (0.05)**：轻微关注，避免过度重复
- **可验证性 (0.05)**：轻微关注，优先可验证的信息

### 后处理
- 按标题去重，避免同一内容的多个版本
- 提升同行评审内容的排名
- 要求结果包含引用来源
