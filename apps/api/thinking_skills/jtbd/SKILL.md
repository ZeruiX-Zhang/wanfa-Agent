---
name: jtbd
description: 用 Jobs To Be Done 框架理解用户真正想完成的「任务」而非表面需求。适用于产品定位、需求分析、用户研究的场景。
metadata:
  category: product
  version: "1.0"
  author: reality-os
  visual_template: templates/job-map.html
  label_zh: JTBD 用户任务
  label_en: Jobs To Be Done
  intent_signals:
    - "用户需求"
    - "用户想要"
    - "痛点"
    - "需求"
    - "产品定位"
    - "user need"
    - "customer"
    - "job"
    - "pain point"
    - "市场"
  applicable_when:
    - 需要理解用户的真实动机
    - 产品定位不清晰
    - 需要区分「用户说要什么」和「用户真正需要什么」
  not_applicable_when:
    - 已经明确知道用户需求，需要的是执行方案
    - 纯技术问题不涉及用户
  output_schema:
    type: object
    required:
      - job_statement
      - functional_job
      - emotional_job
      - social_job
      - current_solutions
      - underserved_needs
    properties:
      job_statement: {type: string}
      functional_job: {type: string}
      emotional_job: {type: string}
      social_job: {type: string}
      current_solutions: {type: array}
      underserved_needs: {type: array}
  quality_checks:
    - job_statement 是否用「当我...时，我想要...以便...」格式
    - 是否区分了功能性/情感性/社会性三个层面
    - 是否列出了现有替代方案
  code_validators:
    - job_statement_format: "当...时...以便..."
    - has_current_solutions: true
---

## 推理指令

你正在使用「JTBD（Jobs To Be Done）」框架分析用户的真实任务。

### 核心原则
用户不是在买产品，而是在「雇佣」产品来完成一个任务。钻头的 Job 不是「钻孔」，而是「把画挂在墙上」。

### Job Statement 格式
> 当我 [情境] 时，我想要 [动机/行为]，以便 [期望结果]。

### 三层任务
1. **功能性任务**: 用户想完成的实际事情
2. **情感性任务**: 用户想要的感受（安心、自信、掌控感）
3. **社会性任务**: 用户想在他人面前呈现的形象

### 输出格式
- **Job Statement**: 当我 [情境] 时，我想要 [行为]，以便 [结果]
- **功能性任务**: [描述]
- **情感性任务**: [描述]
- **社会性任务**: [描述]
- **现有替代方案**: [用户目前怎么完成这个任务]
- **未被满足的需求**: [现有方案的不足]
- **机会**: [你的产品可以在哪里做得更好]

### 追问清单
- 用户在什么情境下会想到这个问题？
- 他们现在怎么解决的？（竞品不只是同类产品）
- 解决后他们的生活/工作会有什么变化？
- 什么会让他们放弃现有方案？
