---
name: five-w-two-h
description: 用 What/Why/Who/When/Where/How/How much 七个维度全面定义问题。适用于问题模糊、需要厘清边界、初次接触新领域的场景。
metadata:
  category: problem_definition
  version: "1.0"
  author: reality-os
  visual_template: templates/problem-grid.html
  label_zh: 5W2H 问题定义
  label_en: 5W2H Problem Definition
  intent_signals:
    - "是什么"
    - "怎么定义"
    - "什么问题"
    - "搞清楚"
    - "define"
    - "what is"
    - "clarify"
    - "scope"
  applicable_when:
    - 问题模糊，需要厘清边界
    - 初次接触一个新领域或新项目
    - 团队对问题的理解不一致
  not_applicable_when:
    - 问题已经很清晰，需要的是解决方案
    - 需要深挖根因（用 five-whys）
    - 需要做决策（用 decision-matrix）
  output_schema:
    type: object
    required:
      - what
      - why
      - who
      - when
      - where
      - how
      - how_much
      - problem_statement
    properties:
      what: {type: string}
      why: {type: string}
      who: {type: string}
      when: {type: string}
      where: {type: string}
      how: {type: string}
      how_much: {type: string}
      problem_statement: {type: string}
  quality_checks:
    - 七个维度是否都有实质内容（非空泛）
    - 是否区分了事实和假设
    - 最终 problem_statement 是否精准且可验证
  code_validators:
    - all_fields_non_empty: true
    - problem_statement_min_length: 20
---

## 推理指令

你正在使用「5W2H 问题定义法」帮助用户厘清问题边界。

### 规则
1. 逐一回答七个维度，每个维度用 1-3 句话
2. 事实标注 ✓，假设标注 [?]
3. 如果某个维度信息不足，明确标注「需要补充」而非编造
4. 最后综合七个维度，输出一句精准的 Problem Statement

### 输出格式
- **What（是什么）**: [描述问题本身]
- **Why（为什么重要）**: [不解决会怎样]
- **Who（谁相关）**: [利益相关方]
- **When（时间维度）**: [截止时间/紧迫度]
- **Where（在哪里发生）**: [场景/环境]
- **How（怎么发生的）**: [过程/机制]
- **How much（多大规模）**: [量化影响]

**Problem Statement**: [一句话精准定义]

### 证据需求
- 用户对问题的初始描述
- 相关背景信息（如有）
- 利益相关方信息（如有）
