---
name: finance-validator
type: validation
metadata:
  category: finance
  label_zh: 金融知识验证
  label_en: Finance Knowledge Validator
  domains:
    - finance
    - investment
    - stock
    - banking
    - insurance
  rules:
    fact_consistency:
      contradiction_keywords:
        - 涨
        - 跌
        - 盈利
        - 亏损
        - 增长
        - 下降
    timeliness:
      max_age_days: 30
    completeness:
      required_sections:
        - 数据来源
        - 时间范围
        - 风险提示
      min_title_length: 8
      min_body_length: 100
    source_credibility:
      trusted_domains:
        - bloomberg.com
        - ft.com
        - sec.gov
        - reuters.com
        - wsj.com
        - cnbc.com
        - eastmoney.com
        - sse.com.cn
        - szse.cn
      min_trust_score: 0.7
---

# 金融知识验证规则

本 Skill 定义金融领域知识条目的验证规则，确保入库的金融信息准确、及时且来源可靠。

## 验证维度

### 事实一致性
金融数据中常见的矛盾信号包括同一标的的涨跌描述冲突、盈亏数据不一致等。当新入库内容与已有知识在高重叠度下出现矛盾关键词时，标记为潜在冲突。

### 时效性
金融信息时效性要求极高，默认最大有效期为 30 天。超过此阈值的市场数据、行情分析等内容将被标记为过期。

### 完整性
金融知识条目必须包含数据来源（确保可溯源）、时间范围（明确数据适用期）和风险提示（合规要求）。标题至少 8 字符，正文至少 100 字符。

### 来源可信度
仅信任主流金融数据源和监管机构网站。未知来源的金融信息需要更高的审核标准，最低信任分数为 0.7。
