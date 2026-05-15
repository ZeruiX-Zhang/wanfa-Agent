---
name: pre-mortem
description: 假设项目已经失败，倒推最可能的失败原因并提前制定预防措施。适用于重大决策前、项目启动前需要识别风险的场景。
metadata:
  category: decision
  version: "1.0"
  author: reality-os
  visual_template: templates/risk-wall.html
  label_zh: 预演失败
  label_en: Pre-mortem
  intent_signals:
    - "风险"
    - "可能失败"
    - "万一"
    - "最坏情况"
    - "risk"
    - "fail"
    - "what if"
    - "worst case"
    - "预防"
  applicable_when:
    - 即将做重大决策或启动项目
    - 需要提前识别盲点
    - 团队过于乐观需要泼冷水
  not_applicable_when:
    - 问题已经发生（用 five-whys 或 postmortem）
    - 需要在选项间做选择（用 decision-matrix）
  output_schema:
    type: object
    required:
      - project_description
      - failure_scenarios
      - prevention_actions
    properties:
      project_description: {type: string}
      failure_scenarios: {type: array, minItems: 3}
      prevention_actions: {type: array}
  quality_checks:
    - 是否列出了至少 3 个不同类型的失败场景
    - 每个场景是否有具体的预防措施
    - 是否覆盖了技术、市场、执行三个维度
  code_validators:
    - min_scenarios: 3
    - each_scenario_has_prevention: true
---

## 推理指令

你正在使用「预演失败（Pre-mortem）」帮助用户提前识别风险。

### 核心思路
假设现在是 6 个月后，这个项目已经彻底失败了。回头看，最可能是什么原因导致的？

### 步骤
1. 明确项目/决策的描述
2. 想象它已经失败，列出 5-7 个最可能的失败原因
3. 按严重度和可能性排序
4. 为前 3 个制定具体的预防措施或早期预警信号

### 输出格式
**项目描述**: [一句话]

**失败场景**（按可能性排序）:
| # | 失败原因 | 可能性 | 严重度 | 预警信号 |
|---|---------|--------|--------|---------|
| 1 | ... | 高/中/低 | 致命/严重/轻微 | ... |

**预防措施**:
1. 针对场景1: [具体行动]
2. 针对场景2: [具体行动]
3. 针对场景3: [具体行动]

### 常见失败类型
- 市场：没人要、定价错、时机不对
- 技术：做不出来、性能不够、依赖不可控
- 执行：团队不够、资金断裂、关键人离开
- 竞争：巨头入场、开源替代、法规变化
