---
name: mece
description: 用相互独立、完全穷尽（MECE）原则将复杂问题分解为不重叠、无遗漏的子问题。适用于问题太大需要拆解的场景。
metadata:
  category: problem_definition
  version: "1.0"
  author: reality-os
  visual_template: templates/tree-view.html
  label_zh: MECE 分解
  label_en: MECE Decomposition
  intent_signals:
    - "拆解"
    - "分解"
    - "太复杂"
    - "从哪入手"
    - "decompose"
    - "break down"
    - "structure"
    - "分类"
  applicable_when:
    - 问题太大，需要拆成可管理的子问题
    - 需要确保分析没有遗漏
    - 需要给团队分工
  not_applicable_when:
    - 问题已经足够小可以直接行动
    - 需要深挖因果链（用 five-whys）
  output_schema:
    type: object
    required:
      - original_problem
      - decomposition_axis
      - branches
      - coverage_check
    properties:
      original_problem: {type: string}
      decomposition_axis: {type: string}
      branches: {type: array, minItems: 2}
      coverage_check: {type: object}
  quality_checks:
    - 分支之间是否真的不重叠（ME）
    - 所有分支加起来是否覆盖了原问题（CE）
    - 分解轴是否有逻辑依据
  code_validators:
    - min_branches: 2
    - max_branches: 8
---

## 推理指令

你正在使用「MECE 分解法」将复杂问题拆解为互不重叠、完全穷尽的子问题。

### 规则
1. 先明确原问题的边界
2. 选择一个分解轴（按时间/按角色/按流程/按类型）
3. 沿该轴切分为 2-7 个分支
4. 检验：任意两个分支是否有重叠？所有分支加起来是否等于原问题？
5. 如果不满足 MECE，调整分解轴或合并/拆分分支

### 输出格式
- **原问题**: [一句话]
- **分解轴**: [选择的切分维度及理由]
- **分支**:
  1. [分支1名称]: [一句话描述范围]
  2. [分支2名称]: [一句话描述范围]
  ...
- **MECE 检验**:
  - 互斥性: [是否有重叠？如有，指出哪两个分支]
  - 完整性: [是否有遗漏？如有，指出缺什么]

### 常见分解轴
- 按流程阶段（输入→处理→输出）
- 按利益相关方（用户/团队/客户/平台）
- 按时间（短期/中期/长期）
- 按类型（技术/商业/运营/法务）
