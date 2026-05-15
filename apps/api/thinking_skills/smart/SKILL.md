---
name: smart
description: 用 SMART 原则（具体/可衡量/可达成/相关/有时限）检验和改写目标。适用于目标模糊、需要落地执行的场景。
metadata:
  category: execution
  version: "1.0"
  author: reality-os
  visual_template: templates/goal-checker.html
  label_zh: SMART 目标
  label_en: SMART Goals
  intent_signals:
    - "目标"
    - "计划"
    - "怎么落地"
    - "具体化"
    - "goal"
    - "plan"
    - "objective"
    - "target"
    - "actionable"
  applicable_when:
    - 目标模糊需要具体化
    - 需要把愿望转化为可执行的计划
    - 需要检验现有目标是否合格
  not_applicable_when:
    - 还不知道目标是什么（先用 problem-statement）
    - 需要在多个目标间选择（用 decision-matrix）
  output_schema:
    type: object
    required:
      - original_goal
      - smart_goal
      - s_specific
      - m_measurable
      - a_achievable
      - r_relevant
      - t_time_bound
      - pass_fail
    properties:
      original_goal: {type: string}
      smart_goal: {type: string}
      s_specific: {type: object}
      m_measurable: {type: object}
      a_achievable: {type: object}
      r_relevant: {type: object}
      t_time_bound: {type: object}
      pass_fail: {type: object}
  quality_checks:
    - 改写后的目标是否满足全部 5 个维度
    - 是否有量化指标
    - 是否有明确截止时间
  code_validators:
    - has_metric: true
    - has_deadline: true
    - all_dimensions_addressed: true
---

## 推理指令

你正在使用「SMART 目标法」检验和改写用户的目标。

### 五个维度
- **S (Specific)**: 具体做什么？谁做？在哪里？
- **M (Measurable)**: 怎么衡量成功？数字是什么？
- **A (Achievable)**: 以现有资源能做到吗？差什么？
- **R (Relevant)**: 和更大的目标有什么关系？为什么现在做？
- **T (Time-bound)**: 截止时间是什么？里程碑是什么？

### 输出格式
**原始目标**: [用户原话]

**SMART 检验**:
| 维度 | 通过? | 分析 | 改写建议 |
|------|-------|------|---------|
| S 具体 | ✓/✗ | ... | ... |
| M 可衡量 | ✓/✗ | ... | ... |
| A 可达成 | ✓/✗ | ... | ... |
| R 相关 | ✓/✗ | ... | ... |
| T 有时限 | ✓/✗ | ... | ... |

**改写后的 SMART 目标**: [一句话]

### 常见问题
- ❌「做一个好产品」→ ✓「在 30 天内上线 MVP 并获得 5 个付费用户」
- ❌「提高效率」→ ✓「将部署时间从 2 小时缩短到 15 分钟，本月底前完成」
- ❌「学好英语」→ ✓「3 个月内雅思口语从 5.5 提升到 6.5，每天练习 30 分钟」
