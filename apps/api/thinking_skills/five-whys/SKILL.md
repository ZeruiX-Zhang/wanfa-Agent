---
name: five-whys
description: 通过连续追问「为什么」深挖根因，直到触及可行动的底层原因。适用于问题已发生需要追溯原因、表面原因不够深的场景。
metadata:
  category: root_cause
  version: "1.0"
  author: reality-os
  label_zh: 5 Whys 追问法
  label_en: 5 Whys
  intent_signals:
    - "为什么"
    - "根因"
    - "根本原因"
    - "底层"
    - "反复出现"
    - "why"
    - "root cause"
    - "underlying"
  applicable_when:
    - 问题已经发生，需要追溯原因
    - 表面原因明显但不够深
    - 同一问题反复出现
  not_applicable_when:
    - 问题还没发生（用 pre-mortem）
    - 需要在多个选项间做选择（用 decision-matrix）
    - 问题是结构性的而非因果链（用 fishbone）
  output_schema:
    type: object
    required:
      - why_chain
      - root_cause
      - minimum_action
    properties:
      why_chain: {type: array, minItems: 3}
      root_cause: {type: string, minLength: 10}
      minimum_action: {type: string}
  quality_checks:
    - 是否追问了至少 3 层
    - 每层是否有证据支撑或标注了假设
    - 根因是否可直接行动（而非另一个抽象概念）
    - 是否避免了把「责任人」当根因
  code_validators:
    - min_depth: 3
    - requires_evidence_markers: true
  visual_template: templates/why-chain.html
---

## 推理指令

你正在使用「5 Whys 追问法」分析问题。

### 规则
1. 从用户描述的表面问题开始
2. 每一层追问「为什么会这样？」
3. 每一层的回答必须基于证据或明确标注为假设 [?]
4. 追问到第 5 层或触及可直接行动的原因时停止
5. **绝不把「某人没做好」当根因**——要追问「为什么没做好」（是流程问题？激励问题？能力问题？）

### 输出格式
- **Why 1**: [表面问题] → 因为 [原因1] [✓ 或 ?]
- **Why 2**: [原因1] → 因为 [原因2] [✓ 或 ?]
- **Why 3**: [原因2] → 因为 [原因3] [✓ 或 ?]
- ...
- **根因**: [最底层可行动的原因]
- **最小验证行动**: [一句话，本周可执行]

### 常见陷阱
- ❌ 停在「因为他没做好」→ 要继续问为什么没做好
- ❌ 每层都是同一个意思的换种说法 → 要确保每层真的深入了一步
- ❌ 跳跃太大（从表面直接到哲学层面）→ 每层只深入一步

### 证据需求
- 问题的具体表现（什么时候、多严重）
- 已知的直接原因
- 历史上类似问题的处理记录（如有）
