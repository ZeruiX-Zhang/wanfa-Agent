---
name: tech-validator
type: validation
metadata:
  category: tech
  label_zh: 技术知识验证
  label_en: Tech Knowledge Validator
  domains:
    - tech
    - programming
    - software
    - ai
    - cloud
    - devops
  rules:
    fact_consistency:
      contradiction_keywords:
        - deprecated
        - 废弃
        - 不推荐
        - 已移除
        - breaking change
        - 不兼容
    timeliness:
      max_age_days: 180
    completeness:
      required_sections:
        - 适用版本
        - 使用示例
      min_title_length: 5
      min_body_length: 80
    source_credibility:
      trusted_domains:
        - github.com
        - stackoverflow.com
        - docs.python.org
        - developer.mozilla.org
        - learn.microsoft.com
        - cloud.google.com
        - aws.amazon.com
        - arxiv.org
        - pytorch.org
        - huggingface.co
      min_trust_score: 0.5
---

# 技术知识验证规则

本 Skill 定义技术领域知识条目的验证规则，确保入库的技术文档、代码示例和架构方案准确且具有时效性。

## 验证维度

### 事实一致性
技术领域中常见的矛盾信号包括 API 废弃声明与使用建议冲突、版本不兼容描述等。当新内容引用已被标记为 deprecated 的技术方案时，需要特别关注。

### 时效性
技术文档的有效期相对较长（180 天），但框架版本更新、API 变更等内容仍需定期刷新。超过阈值的技术方案可能已不适用于最新版本。

### 完整性
技术知识条目应包含适用版本信息（确保读者知道适用范围）和使用示例（便于实践参考）。标题至少 5 字符，正文至少 80 字符。

### 来源可信度
信任主流技术文档站点、开源社区和学术平台。技术领域对来源的信任阈值相对宽松（0.5），因为许多有价值的技术内容来自个人博客和社区论坛。
