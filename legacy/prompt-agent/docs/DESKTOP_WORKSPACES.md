# Desktop Workspaces

PromptAgent 桌面端有三个主要工作区。

## 提示词实验室

Prompt Lab 是 Prompt action 的桌面工作台。它负责生成提示词、测试提示词效果、对比原始提示词和优化提示词，并显示本次调用的模型、个性化状态、Knowledge OS 使用状态和 token budget。

Prompt 默认不读取 Knowledge OS sources、claims 或 graph。只有用户在本次操作中手动开启 `使用 Knowledge OS`，或后续某个 Skill policy 明确允许时，才可以加入相关知识。

## 知识系统

Knowledge OS 是 Level Up 的查看、搜索、审核和修正界面。Level Up 不直接把节点和关系写入正式 graph，而是写入 review queue。用户审核通过后才写入 `graph/nodes.jsonl` 和 `graph/edges.jsonl`。

这个工作区让长期知识可见、可修正、可删除，避免右键动作变成不可审计的黑盒。

## 设置

Settings 负责模型、Prompt 策略、Level Up 策略、个性化、Skills、浏览器扩展、隐私与安全、关于。

个性化开关控制 Skill 是否可以读取 `knowledge_os/wiki/personal`。即使关闭，用户仍然可以在知识系统里编辑个人资料文件。

## 为什么右键只保留 Prompt 和 Level Up

右键菜单应该是轻量入口，不承载复杂信息架构。Prompt 解决即时提示词生成，Level Up 解决长期知识沉淀。测试、审核、修正、策略配置都放在桌面端工作区。

这样可以保持右键操作稳定，也避免把复杂功能塞进系统菜单。

