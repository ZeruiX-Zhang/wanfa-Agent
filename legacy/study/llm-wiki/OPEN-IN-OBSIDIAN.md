# 用 Obsidian 打开你的 Wiki(三步)

只做一次,以后双击 Obsidian 图标就能进入。

---

## 第一步:下载并安装 Obsidian

打开 → https://obsidian.md
点 → "Get Obsidian for Windows"
双击 → 下载下来的 `.exe` 文件,一路 Next

完全免费,不用注册账号。

---

## 第二步:把 llm-wiki 当作 Vault 打开

第一次启动会出现一个欢迎窗口,点:

> **"Open folder as vault"**

然后浏览到这个路径,点选中后"选择文件夹":

```
D:\UserData\Desktop\study\llm-wiki
```

> ⚠️ **只选 `llm-wiki` 这一层,不要选 `study`**——选 `study` 会把同级的"学习教练"系统也加载进来。

会弹一个"Trust author and enable plugins?"——选 **"Trust author and enable plugins"**(我已经在 vault 里预配好了所有设置和模板,需要信任后才生效)。

---

## 第三步:看看效果

打开后你会立刻看到:

- **左侧侧边栏**:文件管理器、搜索、收藏夹(已预先放好 6 个常用页面快捷入口)
- **右侧侧边栏**:反向链接 / 大纲 / Graph View 三个标签
- **中间**:默认打开 README.md

按 <kbd>Ctrl</kbd> + <kbd>G</kbd> → **打开全局知识图谱**(就是你说的"圆点 + 连线")。

第一眼会看到大约 30+ 个圆点,按颜色分组:

- 🟡 金色 = 概念页(`wiki/concepts/`)
- 🟠 香槟色 = 问题页(`wiki/questions/`)
- 🟫 米色 = 来源/原始资料(`wiki/sources/` + `raw/articles|papers|notes/`)
- 🟤 暗金 = 人物/组织/项目
- ✨ 浅金 = 主题地图(`wiki/maps/`)
- 🩶 深米 = 词条(`wiki/glossary/`)
- 🔴 暖红 = 矛盾/主张

`raw/inbox/` 已被自动**排除**在图谱外(避免原始凭证污染)。

按 <kbd>Ctrl</kbd> + <kbd>Shift</kbd> + <kbd>G</kbd> → **打开"局部图谱"**——只显示当前页和它的相邻节点。比如打开 `[[rag]]` 后按这个组合键,你会看到只有 RAG 周围那几页。

---

## 好的,然后呢?

### 推荐第一件事:看主题地图

侧边栏收藏夹里有 **🌟 AI 工程主题地图** ——这是手工梳理的学习路径,把 Graph 里的乱麻整理成一条清晰主线。

### 推荐第二件事:打开 Templater 插件(可选)

如果想让"新建笔记"自动套上 CLAUDE.md 模板,做这一步:

1. Settings(齿轮) → Community plugins → **Turn on community plugins**
2. Browse → 搜 **Templater** → Install → Enable
3. Settings → Templater → "Template folder location" 设为 `wiki/_templates`
4. 写新笔记时:<kbd>Ctrl</kbd>+<kbd>P</kbd> → "Templater: Insert template" → 选 `04-question.md` 等

**核心模板插件已经默认开启**,所以即使不装 Templater,你也能用 <kbd>Ctrl</kbd>+<kbd>P</kbd> → "Insert template" 用 8 份预置模板。

---

## 失败兜底

| 症状 | 原因 | 解决 |
|------|------|------|
| 找不到"Open folder as vault" | 你跳过了欢迎屏 | 左下角齿轮 → Manage vaults → "Open folder as vault" |
| 打开后图谱空白 | 选错文件夹了 | 确认你选的是 `llm-wiki`,不是 `llm-wiki\wiki` 或 `study` |
| 图谱里圆点没有颜色 | 配色没生效 | 重启一下 Obsidian。仍然不行就 Ctrl+P → "Reload app without saving" |
| Trust 弹窗没出现,模板不可用 | Restricted mode | Settings → Community plugins → 关掉 Restricted mode |
| 我点 Ctrl+G 没反应 | 焦点不在 Obsidian 主窗口 | 先用鼠标点中间编辑区域,再按 |

---

## 你不需要做的事

- 不需要登录账号
- 不需要联网
- 不需要导入文件——它直接读你硬盘上的 `.md` 文件
- 不需要担心格式——所有页面已经是标准 Markdown + Obsidian 双链

---

## 装好之后告诉我

发我一句"装好了",我就帮你做下一件事:

- 检查 graph 里有没有孤立节点(orphan pages)
- 帮你建更多主题地图(把"如何成为顶级 AI 工程师"那篇综述变成一张可视化路径图)
- 调整哪些页面应该合并、哪些拆分
