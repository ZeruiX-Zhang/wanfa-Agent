# Prompt Lab

提示词实验室用于生成、测试和对比提示词。

## 生成提示词

1. 打开桌面端。
2. 进入 `提示词实验室`。
3. 填写 `原始文本` 和 `目标 / 补充信息`。
4. 选择优化类型。
5. 点击 `生成 Prompt`。

生成结果会显示：

- 优化后的提示词
- 当前 provider 和模型
- 个性化是否使用
- Knowledge OS 是否使用
- context budget

## 测试提示词

1. 在 `当前测试输入` 中填写测试内容。
2. 点击 `测试 Prompt`。
3. 查看优化提示词结果和 token budget。

测试输入默认不写入 Knowledge OS。

## A/B 对比

1. 先生成优化后的提示词。
2. 填写测试输入。
3. 点击 `A/B 对比`。

接口会分别运行原始提示词和优化提示词，并返回一个简单 comparison：

- winner
- reason
- clarity / specificity / usefulness scores

MVP 不做复杂自动评测。

## 保存测试案例

界面保留 `保存测试案例` 和 `保存为 Skill 示例` 入口。只有用户点击保存时，测试内容才可以被写入测试案例或 Skill example。

## 确认没有默认读取 Knowledge OS

生成 Prompt 后查看：

- `knowledge_os_info.used` 应为 `false`
- `knowledge_os_info.sources` 应为空
- `knowledge_os_info.claims` 应为空
- `knowledge_os_info.graph` 应为空
- `context_budget.used_knowledge_tokens` 应为 `0`
- `context_budget.used_graph_tokens` 应为 `0`

后端测试 `test_prompt_default_does_not_read_knowledge_os` 覆盖该边界。

