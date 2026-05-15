---
name: mvp
description: 设计最小可行产品（MVP）的验证路径：假设→实验→指标→截止时间。适用于创业验证、新功能上线前的场景。
metadata:
  category: product
  version: "1.0"
  author: reality-os
  visual_template: templates/experiment-card.html
  label_zh: MVP 设计
  label_en: MVP Design
  intent_signals:
    - "最小"
    - "验证"
    - "MVP"
    - "试一下"
    - "快速"
    - "validate"
    - "minimum"
    - "prototype"
    - "experiment"
    - "测试市场"
  applicable_when:
    - 有一个想法需要用最小成本验证
    - 不确定用户是否会买单
    - 需要在资源有限时快速学习
  not_applicable_when:
    - 已经验证过需求，需要的是完整产品设计
    - 纯学术研究不涉及市场验证
  output_schema:
    type: object
    required:
      - hypothesis
      - mvp_description
      - success_metric
      - failure_signal
      - timeline
      - cost
    properties:
      hypothesis: {type: string}
      mvp_description: {type: string}
      success_metric: {type: string}
      failure_signal: {type: string}
      timeline: {type: string}
      cost: {type: object}
  quality_checks:
    - hypothesis 是否可证伪
    - success_metric 是否可量化
    - timeline 是否在 2 周以内
    - 是否明确了失败后的下一步
  code_validators:
    - has_hypothesis: true
    - has_metric: true
    - has_timeline: true
    - has_failure_signal: true
---

## 推理指令

你正在使用「MVP 设计」帮助用户设计最小可行验证。

### 核心原则
MVP 不是「功能最少的产品」，而是「能验证核心假设的最小实验」。可以是一个落地页、一次访谈、一个手动服务。

### 输出格式
- **核心假设**: [一句话，可证伪]
- **MVP 形态**: [具体做什么，不做什么]
- **成功指标**: [量化，如「3/10 用户愿意付费」]
- **失败信号**: [什么结果说明假设错了]
- **时间线**: [最多 2 周]
- **成本**: 时间 [X小时]，金钱 [¥X]，精力 [高/中/低]
- **如果成功**: [下一步是什么]
- **如果失败**: [pivot 方向或止损]

### MVP 类型参考
- **落地页 MVP**: 写一个页面看有没有人注册
- **手动 MVP**: 人工提供服务看用户是否满意
- **视频 MVP**: 录一个演示视频看反馈
- **众筹 MVP**: 预售看有没有人付费
- **访谈 MVP**: 直接问 5-10 个目标用户
