# 我的 Wiki — 新手快速上手

欢迎。这是一个**长期个人知识库**,基于 Karpathy 的 LLM Wiki 思路:本地 Markdown、可溯源、由 AI 长期维护。

---

## ★ 一句话用法

> **看到资料 → 丢进 `raw/inbox/` → 对 Claude 说"处理 inbox"。**

就这样。不用先想"它属于哪类"、不用改名、不用转格式。Claude 会自己分类、命名、转 Markdown、归档、抽概念、互链、更新索引。

---

## 🗺️ 想要"知识地图"(Graph View)?

装 Obsidian。Wiki 的所有 `.md` 文件、双链、front-matter 已经为它准备好了——配置我都预先放进 `.obsidian/` 文件夹了,**装好直接打开 vault 就生效**:配色分组、深色主题、收藏栏、模板系统、graph 排除 inbox 等等。

完整三步指南: **[`OPEN-IN-OBSIDIAN.md`](OPEN-IN-OBSIDIAN.md)**

简版:
1. https://obsidian.md 下载安装
2. "Open folder as vault" → 选 `D:\UserData\Desktop\study\llm-wiki`(只这一层,不要选 `study`)
3. 点 "Trust author and enable plugins" → 按 <kbd>Ctrl</kbd>+<kbd>G</kbd> 看图谱

主题地图先看 [[wiki/maps/ai-engineering-map]],它把 Wiki 现有的 30+ 页面织成一条学习主线。

---

## ✨ 推荐:零安装上传工具(直写盘)

项目根目录有一份 **`inbox-uploader.html`**——丝绸黑金风的本地上传页。
**Chrome 或 Edge 双击打开**,授权一次文件夹后,**点保存就直接落到 `raw/inbox/`**——不再下载、不再拖文件。

```
D:\UserData\Desktop\study\llm-wiki\inbox-uploader.html
```

### 第一次怎么用(只需做一次)

1. 用 **Chrome 或 Edge** 双击打开 `inbox-uploader.html`(其他浏览器会自动降级到下载模式)
2. 页面顶部有一条状态栏,点"**连接 inbox 文件夹**"
3. 在弹出的文件夹选择器里,选这个目录:
   ```
   D:\UserData\Desktop\study\llm-wiki\raw\inbox
   ```
4. 浏览器弹"是否允许编辑文件夹中的文件",选**允许**
5. 状态条变成**金色 LIVE 标签 + 绿色圆点 = 已连接**

### 之后每次怎么用

| 标签页 | 用途 | 点保存后 |
|--------|------|------|
| **文字** | 笔记 / 摘录 / 灵感 | 直接生成 `YYYY-MM-DD-HHmm-kind-slug.md` 落到 `raw/inbox/` 根目录 |
| **链接** | 一行一个 URL | 自动**追加**到 `raw/inbox/urls.md` 的"待处理"区(不会覆盖你已有内容) |
| **文件** | 拖 PDF / MD / 图片 / 字幕等 | 按后缀自动写入对应子目录(pdfs / images / videos / web / misc) |

写完→点保存→回到 Claude 说"处理 inbox"。**没有"打开文件夹拖文件"这一步。**

### 重新打开浏览器后

浏览器为了安全,每个会话需要重新授权一次。再次打开 `inbox-uploader.html` 时:

- 顶部会提示"检测到上次连接过的文件夹"
- 点一下"**重新连接 inbox**" → 浏览器弹一次确认 → 1 秒搞定

(它不会忘记你选的是哪个文件夹,只是必须由你点一下确认。)

### 为什么不是 Firefox/Safari

直写盘用的是 [File System Access API],目前只 Chrome 和 Edge 支持稳定。如果你用其他浏览器打开,工具会自动**降级到下载模式**(原来的"下载到 Downloads → 拖进 inbox")并提示你切换。

[File System Access API]: https://developer.mozilla.org/en-US/docs/Web/API/File_System_Access_API

### 小贴士

- 草稿自动保存到本地浏览器(localStorage),意外关页面不丢
- 文字面板按 <kbd>Ctrl/⌘</kbd> + <kbd>Enter</kbd> 直接保存
- 文件名都自带 `YYYY-MM-DD-HHmm` 时间戳,不会重名

---

## 4 类资料具体怎么丢

| 资料形式 | 丢哪里 | 怎么操作 |
|----------|--------|----------|
| **网页/文章链接** | `raw/inbox/urls.md` | 一行一个链接粘进去 |
| **网页内容(完整保存)** | `raw/inbox/web/` | 装 [Obsidian Web Clipper] 浏览器插件,设保存路径到这个文件夹,以后看到文章点一下就完 |
| **PDF(论文/书/报告)** | `raw/inbox/pdfs/` | 直接拖文件进去 |
| **视频** | `raw/inbox/urls.md` 粘链接,或在 `raw/inbox/videos/` 放字幕文件 | Claude 会尝试拉字幕,失败会告诉你 |
| **截图/图片** | `raw/inbox/images/` | 拖图片进去 |
| **临时纯文字** | `raw/inbox/notes.md` | 粘进去就行 |
| **金句摘录** | `raw/inbox/clippings.md` | 一条一段,**记得标来源** |
| **自己的灵感** | `raw/inbox/ideas.md` | 想到什么写什么,半成品也无所谓 |
| **不知道是啥** | `raw/inbox/misc/` | 兜底,真不知道就扔这 |

[Obsidian Web Clipper]: https://obsidian.md/clipper

每个 inbox 子目录里都有 README,讲了更多细节(比如 PDF 太大怎么办、视频拉不到字幕怎么办)。

---

## 三个最常用的对话句式

直接复制粘贴给 Claude 就行。

### 1) 处理 inbox(★ 最常用)

```
请阅读 D:\UserData\Desktop\study\llm-wiki\CLAUDE.md,
然后按 §11.7 Inbox Import Workflow 处理 raw/inbox/。

完成后:
- 更新 wiki/questions/inbox-processing-status.md
- 更新 wiki/index.md
- 追加 wiki/log.md

最后用中文告诉我:
- 成功导入了什么
- 失败了什么、为什么
- 需要我人工处理什么
- 下一步最值得补充什么资料
```

### 2) 第一次启动 / 新对话第一句

```
请阅读 D:\UserData\Desktop\study\llm-wiki\CLAUDE.md,
然后查看 wiki/index.md 和 wiki/log.md,告诉我现在 Wiki 的状态、
inbox 里有没有待处理的东西,以及你建议我做的下一件事。
```

### 3) 提问(基于 Wiki 答)

```
请按 CLAUDE.md 的 Query Workflow 回答我的问题:

(在这里写问题)

请基于 Wiki 现有内容回答,区分:
- 已有证据支持的部分
- 不确定的部分
- 来源之间冲突的部分
- 完全没记录的部分
```

### 4) 周期性体检(Lint,建议每月或每 20 份资料后做一次)

```
请按 CLAUDE.md 的 Lint Workflow 对整个 Wiki 做一次健康检查。
重点找:缺证据的结论、互相矛盾的页面、孤立页面、缺失的概念、太长/太短的页面。
请创建或更新 wiki/questions/wiki-health-check.md,并给我下一步最该做的 5 件事。
```

---

## 文件夹一句话说明

```
llm-wiki/
├── CLAUDE.md            ← AI 行为规则(改它=改 AI 工作方式)
├── README.md            ← 你正在看的这份
├── raw/                 ← 原始资料(只读,永不修改)
│   ├── inbox/             ★ 收件箱:不知道放哪就扔这
│   │   ├── urls.md          链接(网页/视频/论文)
│   │   ├── notes.md         临时纯文字
│   │   ├── clippings.md     金句摘录
│   │   ├── ideas.md         自己的灵感
│   │   ├── web/             网页 Clipper 保存的 .md
│   │   ├── pdfs/            PDF 文件
│   │   ├── videos/          字幕/转录
│   │   ├── images/          截图/图片
│   │   └── misc/            兜底
│   ├── articles/          ← 经 inbox 处理后,Claude 把文章归档到这
│   ├── books/             书籍/章节
│   ├── papers/            论文 Markdown 副本
│   ├── transcripts/       视频/播客转录
│   ├── notes/             整理后的笔记
│   └── assets/            图片/附件正式归档
└── wiki/                ← AI 整理出来的结构化知识(可改)
    ├── index.md           总导航
    ├── log.md             操作历史(只追加)
    ├── concepts/          核心概念
    ├── people/            人物
    ├── organizations/     公司/机构
    ├── projects/          项目/产品
    ├── sources/           来源摘要(对应每份原始资料)
    ├── questions/         问题与答案(含 inbox-processing-status)
    ├── claims/            原子主张
    ├── contradictions/    来源冲突
    ├── maps/              主题地图/学习路径
    └── glossary/          术语词条
```

每个子目录里都有自己的 `README.md`,告诉你具体放什么、命名怎么取。

---

## 几条铁律(违反会让 Wiki 退化)

1. **永远不改 raw/ 里已经归档的东西**。inbox 是例外:Claude 处理 urls.md 时会移行到"已处理"区。
2. **每个结论都要有证据**(链接到 `raw/...` 或 `wiki/sources/...`)。
3. **遇到矛盾不要急着判定谁对**,先放进 `wiki/contradictions/`。
4. **保持小而互链**,而不是大而臃肿。一页只讲一个概念。
5. **每次操作都让 Claude 更新 `index.md` 和 `log.md`**——这是 Wiki 不腐烂的关键。

---

## 与同级 `study/` 系统的关系

这个 `llm-wiki/` 与你 `study/` 下原有的"学习教练"系统(`study/raw/`、`study/wiki/`、`study/schema/` 等)是**两套独立系统**。

CLAUDE.md 已经写明:工作在 `llm-wiki/` 下时,不会去碰外面的 `study/raw/` 或 `study/wiki/`。

如果你以后想把两边的内容合并、或者迁移某些笔记过来,要单独提出来,Claude 会先和你确认再动。

---

## 下一步

1. 随便挑一份资料(一篇文章链接、一份 PDF、一段笔记都行)丢进 `raw/inbox/` 对应位置
2. 在新对话粘上面"对话句式 1"
3. 看 Claude 把它整理成什么样
4. 如果觉得顺,再装 Obsidian Web Clipper 把网页保存自动化
