---
name: problem-statement
description: 将模糊的困惑改写为精准、可验证、有约束的问题陈述。适用于用户说不清自己到底要解决什么的场景。
metadata:
  category: problem_definition
  version: "1.0"
  author: reality-os
  visual_template: templates/reframe-card.html
  label_zh: 问题陈述改写
  label_en: Problem Statement
  intent_signals:
    - "说不清"
    - "到底是什么问题"
    - "帮我理清"
    - "问题是"
    - "formulate"
    - "reframe"
    - "real problem"
  applicable_when:
    - 用户的描述含混，需要提炼核心问题
    - 需要把抱怨转化为可行动的问题
    - 需要区分症状和根本问题
  not_applicable_when:
    - 问题已经很清晰
    - 需要全面覆盖多个维度（用 five-w-two-h）
  output_schema:
    type: object
    required:
      - surface_statement
      - reframed_statement
      - constraints
      - success_criteria
      - assumptions
    properties:
      surface_statement: {type: string}
      reframed_statement: {type: string}
      constraints: {type: array}
      success_criteria: {type: array}
      assumptions: {type: array}
  quality_checks:
    - reframed_statement 是否比 surface_statement 更精准
    - 是否明确了约束条件
    - success_criteria 是否可验证
  code_validators:
    - reframed_different_from_surface: true
    - has_constraints: true
    - has_success_criteria: true
---

## 推理指令

你正在使用「问题陈述改写法」帮助用户从模糊描述中提炼精准问题。

### 规则
1. 先原样记录用户的表面描述（surface_statement）
2. 识别其中的隐含假设和模糊词
3. 改写为包含「谁 + 在什么约束下 + 要达到什么可验证的结果」的精准陈述
4. 列出改写过程中发现的约束条件和假设

### 输出格式
- **表面描述**: [用户原话]
- **改写后的问题**: [精准版本，包含主体、约束、可验证目标]
- **约束条件**: [列表]
- **成功标准**: [可验证的标准列表]
- **隐含假设**: [需要验证的假设列表，标注 [?]]

### 改写原则
- 把「我想做 X」改为「在 Y 约束下，如何用最小成本验证 X 是否可行」
- 把「X 不好」改为「X 的哪个具体指标低于什么基准」
- 把「怎么办」改为「在什么条件下，什么结果算成功」
