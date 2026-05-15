# PromptAgent

PromptAgent 是桌面端右键 AI 操作层。桌面端是唯一主入口，浏览器扩展只是把选中文本送入本地后端的输入入口。

右键菜单保持两个动作：

- Prompt：生成或优化提示词
- Level Up：把选中文本升级为 Knowledge OS 中的长期知识

## 工作区

- 提示词实验室：生成、测试、A/B 对比提示词，并查看 provider、个性化、Knowledge OS 使用状态和 token budget。
- 知识系统：查看和修正 Level Up 沉淀的 sources、claims、review queue、graph、personal files 和 logs。
- 设置：模型、Prompt 策略、Level Up 策略、个性化、Skills、浏览器扩展、隐私与安全、关于。

## 启动

后端：

```powershell
python -m uvicorn app.main:app --host 127.0.0.1 --port 8787
```

桌面端开发：

```powershell
npm.cmd run tauri:dev
```

前端构建：

```powershell
npm.cmd run build
```

Vite 或本地 dev asset server 只服务于 Tauri 开发流程，不作为用户入口。使用时打开桌面端窗口。

## 模型

支持：

- Mock：默认本地模拟模型，不需要 API Key。
- DeepSeek：OpenAI-compatible chat completions。
- OpenAI-compatible：自定义兼容端点。
- Ollama：本地模型服务。

API 不返回 API Key。`/api/settings/model` 只返回 `has_api_key`。

## Knowledge OS

主路径是 `knowledge_os`：

- `knowledge_os/wiki/sources`
- `knowledge_os/claims/claims.jsonl`
- `knowledge_os/graph/review_queue.jsonl`
- `knowledge_os/graph/nodes.jsonl`
- `knowledge_os/graph/edges.jsonl`
- `knowledge_os/wiki/personal`
- `knowledge_os/log.md`

Personal 的唯一主存储位置是 `knowledge_os/wiki/personal`，不再以 `user_profile` 或 `personal_wiki` 作为主路径。

## 测试

```powershell
python -m pytest
npm.cmd run build
```

当前环境如果没有全局 Python，请先激活本地虚拟环境，或设置 `PROMPT_AGENT_PYTHON` 后使用 `npm.cmd run tauri:dev`。

