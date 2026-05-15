---
name: fishbone
description: 用鱼骨图（石川图）按六大类（人/机/料/法/环/测）系统梳理问题的所有可能原因。适用于原因可能来自多个方向、需要全面排查的场景。
metadata:
  category: root_cause
  version: "1.0"
  author: reality-os
  visual_template: templates/fishbone-diagram.html
  label_zh: 鱼骨图分析
  label_en: Fishbone / Ishikawa
  intent_signals:
    - "原因有哪些"
    - "全面排查"
    - "可能的原因"
    - "各方面"
    - "causes"
    - "factors"
    - "fishbone"
    - "ishikawa"
  applicable_when:
    - 原因可能来自多个方向
    - 需要系统性排查而非单一因果链
    - 团队需要共同梳理问题
  not_applicable_when:
    - 已经知道是单一因果链（用 five-whys）
    - 需要量化各原因的权重（用 pareto）
  output_schema:
    type: object
    required:
      - problem_head
      - categories
      - top_suspects
    properties:
      problem_head: {type: string}
      categories: {type: object}
      top_suspects: {type: array, maxItems: 3}
  quality_checks:
    - 是否覆盖了至少 4 个类别
    - 每个类别是否有具体原因（非空泛）
    - top_suspects 是否有证据支撑
  code_validators:
    - min_categories: 4
    - min_causes_per_category: 1
---

## 推理指令

你正在使用「鱼骨图」系统梳理问题的所有可能原因。

### 六大类别（6M）
1. **人 (Man)**: 技能、态度、沟通、人员配置
2. **机 (Machine)**: 工具、设备、系统、技术栈
3. **料 (Material)**: 数据、输入质量、原材料
4. **法 (Method)**: 流程、规范、标准、策略
5. **环 (Environment)**: 市场、竞争、政策、文化
6. **测 (Measurement)**: 指标、反馈、监控、评估

### 输出格式
- **问题（鱼头）**: [一句话描述]
- **人**: [原因1], [原因2]...
- **机**: [原因1], [原因2]...
- **料**: [原因1], [原因2]...
- **法**: [原因1], [原因2]...
- **环**: [原因1], [原因2]...
- **测**: [原因1], [原因2]...
- **最可疑的 3 个原因**: [排序，附理由]
