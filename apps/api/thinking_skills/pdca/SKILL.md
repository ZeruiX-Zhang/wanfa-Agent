---
name: pdca
description: 用 PDCA 循环（计划→执行→检查→改进）推进持续改进。适用于需要迭代优化、建立改进闭环的场景。
metadata:
  category: execution
  version: "1.0"
  author: reality-os
  visual_template: templates/cycle-progress.html
  label_zh: PDCA 循环
  label_en: PDCA Cycle
  intent_signals:
    - "改进"
    - "迭代"
    - "优化"
    - "循环"
    - "持续"
    - "improve"
    - "iterate"
    - "optimize"
    - "cycle"
    - "continuous"
  applicable_when:
    - 需要持续改进一个流程或产品
    - 上一轮行动已完成，需要复盘并进入下一轮
    - 需要建立系统化的改进机制
  not_applicable_when:
    - 第一次做，还没有基线（先用 smart 设定目标）
    - 需要做一次性决策（用 decision-matrix）
  output_schema:
    type: object
    required:
      - current_phase
      - plan
      - do
      - check
      - act
    properties:
      current_phase: {type: string}
      plan: {type: object}
      do: {type: object}
      check: {type: object}
      act: {type: object}
  quality_checks:
    - Plan 是否有明确的假设和指标
    - Check 是否基于数据而非感觉
    - Act 是否明确了下一轮的改动
  code_validators:
    - has_baseline: true
    - has_target_metric: true
    - has_next_action: true
---

## 推理指令

你正在使用「PDCA 循环」推进持续改进。

### 四个阶段

**P (Plan) 计划**
- 当前基线是什么？（数据）
- 目标是什么？（量化）
- 假设是什么？（做什么改动会带来改善）
- 怎么验证？（指标 + 时间）

**D (Do) 执行**
- 按计划执行改动
- 记录实际发生了什么
- 记录遇到的意外

**C (Check) 检查**
- 对比基线和结果
- 假设是否被验证？
- 有没有副作用？

**A (Act) 改进**
- 如果有效：标准化，推广
- 如果无效：分析原因，调整假设
- 进入下一轮 PDCA

### 输出格式
**当前阶段**: [P/D/C/A]

**Plan**:
- 基线: [当前数据]
- 目标: [期望数据]
- 假设: [做什么改动]
- 验证方式: [怎么判断成功]

**Do**:
- 执行内容: [实际做了什么]
- 意外记录: [遇到了什么]

**Check**:
- 结果: [实际数据]
- 对比: [vs 基线，vs 目标]
- 结论: [假设成立/不成立]

**Act**:
- 决定: [标准化/调整/放弃]
- 下一轮改动: [具体是什么]
