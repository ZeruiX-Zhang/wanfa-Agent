---
name: decision-matrix
description: 用加权评分矩阵在多个选项间做结构化决策。适用于有多个备选方案需要客观比较的场景。
metadata:
  category: decision
  version: "1.0"
  author: reality-os
  label_zh: 决策矩阵
  label_en: Decision Matrix
  intent_signals:
    - "选哪个"
    - "比较"
    - "哪个更好"
    - "取舍"
    - "decide"
    - "compare"
    - "which one"
    - "tradeoff"
    - "versus"
  applicable_when:
    - 有 2 个以上备选方案
    - 需要客观比较而非拍脑袋
    - 决策涉及多个评估维度
  not_applicable_when:
    - 只有一个选项（不需要比较）
    - 需要深挖原因（用 five-whys）
    - 信息严重不足无法评分
  output_schema:
    type: object
    required:
      - criteria
      - options
      - scores
      - recommendation
    properties:
      criteria: {type: array, minItems: 3}
      options: {type: array, minItems: 2}
      scores: {type: array}
      recommendation: {type: string}
  quality_checks:
    - 标准是否覆盖了关键维度
    - 权重分配是否有依据
    - 评分是否有证据支撑
    - 是否做了敏感性分析（改变权重后结论是否翻转）
  code_validators:
    - min_criteria: 3
    - min_options: 2
    - weights_sum_to_one: true
  visual_template: templates/matrix.html
---

## 推理指令

你正在使用「决策矩阵」帮助用户在多个选项间做结构化决策。

### 步骤
1. **确定评估标准**（3-7 个维度）
2. **分配权重**（所有权重加起来 = 1.0）
3. **逐项评分**（1-5 分，必须有理由）
4. **计算加权总分**
5. **敏感性检查**：如果最重要的标准权重 ±20%，结论是否翻转？

### 输出格式
**标准与权重**:
| 标准 | 权重 | 理由 |
|------|------|------|
| ... | 0.3 | ... |

**评分矩阵**:
| 选项 | 标准1 (×0.3) | 标准2 (×0.25) | ... | 加权总分 |
|------|-------------|--------------|-----|---------|
| A | 4 (1.2) | 3 (0.75) | ... | 3.85 |
| B | 3 (0.9) | 5 (1.25) | ... | 4.10 |

**推荐**: [选项] — [一句话理由]
**敏感性**: [改变哪个权重会翻转结论]

### 注意
- 权重由用户决定（Agent 只能建议，不能替用户定）
- 评分必须有证据或标注 [?]
- 如果两个选项分差 < 5%，建议用户补充信息再决策
