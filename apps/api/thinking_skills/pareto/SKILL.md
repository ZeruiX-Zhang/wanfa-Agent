---
name: pareto
description: 用 80/20 法则识别贡献最大的少数关键因素。适用于资源有限需要聚焦、需要找到杠杆点的场景。
metadata:
  category: root_cause
  version: "1.0"
  author: reality-os
  visual_template: templates/pareto-chart.html
  label_zh: 帕累托 80/20
  label_en: Pareto 80/20
  intent_signals:
    - "最重要的"
    - "聚焦"
    - "优先"
    - "关键少数"
    - "80/20"
    - "prioritize"
    - "focus"
    - "most impactful"
  applicable_when:
    - 有多个因素需要排序
    - 资源有限需要聚焦
    - 需要找到投入产出比最高的切入点
  not_applicable_when:
    - 只有一个因素
    - 需要全面覆盖不能遗漏（用 mece）
  output_schema:
    type: object
    required:
      - items
      - vital_few
      - cumulative_threshold
    properties:
      items: {type: array, minItems: 3}
      vital_few: {type: array}
      cumulative_threshold: {type: number}
  quality_checks:
    - 是否有量化数据支撑排序
    - vital_few 是否真的占了 80% 的影响
    - 是否给出了聚焦建议
  code_validators:
    - items_sorted_descending: true
    - has_percentage: true
---

## 推理指令

你正在使用「帕累托 80/20 法则」识别关键少数。

### 规则
1. 列出所有因素及其量化影响（频次/金额/时间/严重度）
2. 按影响从大到小排序
3. 计算累计百分比
4. 找到累计达到 80% 的分界线
5. 分界线以上的是「关键少数」，建议优先处理

### 输出格式
| 排名 | 因素 | 影响量 | 占比 | 累计 |
|------|------|--------|------|------|
| 1 | ... | ... | ...% | ...% |
| 2 | ... | ... | ...% | ...% |
...

**关键少数（占 80% 影响的因素）**: [列表]
**建议聚焦**: [一句话行动建议]

### 注意
- 如果没有精确数据，用估算值并标注 [?]
- 帕累托不是万能的——有些问题每个因素权重差不多
