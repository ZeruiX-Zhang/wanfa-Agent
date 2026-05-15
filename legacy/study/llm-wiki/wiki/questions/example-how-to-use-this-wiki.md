---
title: "这个 Wiki 该怎么用?"
type: question
status: stable
created: 2026-05-06
updated: 2026-05-06
source_count: 0
confidence: high
tags:
  - meta
  - example
  - howto
---

# 这个 Wiki 该怎么用?

> 这是一个示例页面,既回答了"怎么用",也展示了一份完整的 Wiki 页该长什么样。
> 你可以把它当作以后所有"问题型"页面的模板。

## Direct Answer

把它当成一个**长期、可生长**的个人知识库:

1. 我把任何想保存的资料(文章、论文、视频转录、自己的笔记)丢到 `raw/` 对应子目录。
2. 让 Claude 按 `CLAUDE.md` 里的 **Ingest Workflow** 处理它。
3. Claude 会:
   - 在 `wiki/sources/` 生成一份摘要页,带元数据、主张、关键概念
   - 把抽出来的概念、人物、组织、项目分别写到对应文件夹
   - 用 `[[页面名]]` 形式把它们互相链接
   - 更新 `wiki/index.md` 和 `wiki/log.md`
4. 我有问题就直接问 Claude(**Query Workflow**),它会基于 Wiki 而不是凭空作答,并区分"有证据"、"证据弱"、"来源冲突"、"完全没记录"。
5. 时间久了,我让 Claude 跑一次 **Lint Workflow**,它会自动找出矛盾页、孤立页、缺证据的主张。

## Reasoning

为什么是这个流程而不是"直接让 AI 总结"?

- **可溯源**:每页底部都列了证据(`raw/...` 路径)。如果某天对结论怀疑,我能回到原文核对,而不是相信 AI 的转述。
- **抗错乱**:`raw/` 不可改是核心规则。AI 即使搞错了一次摘要,我也不会丢掉原始材料。
- **能积累**:同一个概念在多份资料里都出现时,概念页会被反复增补、互链,而不是分散成 10 份重复摘要。
- **能发现矛盾**:专门有 `wiki/contradictions/` 文件夹来强制我直面"两份资料不一致"——这是大多数 AI 摘要工具会回避的事。
- **轻量**:就是一堆 Markdown,Obsidian/VS Code/记事本都能打开,不依赖任何特殊数据库。

## Evidence Used

- `CLAUDE.md`(本项目根目录,定义了 AI 行为规则和工作流)
- `wiki/log.md`(2026-05-06 bootstrap 条目,记录了系统初始化过程)

## Uncertainty

- 长期使用后 Wiki 规模会有多大?目前未知。CLAUDE.md 给了一个粗略阈值:超过 200 页 + 文件导航不够用时,再考虑加 RAG。
- 我自己有多大的频率会回过头去维护(lint、补证据)?这取决于使用习惯,Wiki 设计上鼓励但不强迫。

## Related Pages

- [[wiki/index|Wiki 总导航]]
- (以后会有更多链接,例如具体的概念、来源摘要)

## Suggested Next Step

把你想要整理的**第一份资料**放进 `raw/` 对应子目录,然后在新对话里说:

> 请阅读 CLAUDE.md,然后按 Ingest Workflow 处理 raw/articles/(你的文件名).md。

Claude 会一步步告诉你它在做什么、改了哪些文件、你需要检查什么。

---

## Open Questions

- 当资料量上来后,index.md 是否够用,还是要拆成多个二级 index?
- 是否要给页面加 `priority` 字段(高/中/低)以便日常优先复习高优先级?
