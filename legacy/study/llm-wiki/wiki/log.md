# Wiki Operation Log

> Append-only。永远只在文件末尾追加新条目,不修改旧条目。
> 每个条目都对应一次"操作":bootstrap / ingest / query / lint / restructure / cleanup。

---

## 2026-05-06 - Bootstrap

### Operation
bootstrap

### User Request
用户(Simone)要求按 GPT 给出的 CLAUDE.md 模板,在 `D:\UserData\Desktop\study\llm-wiki\` 下自动建好整个 Wiki 系统的初始结构。
用户为非技术背景,选择"通用学习型 Wiki(主题不限定)+ 综合用途(学习+整理+查询)"。

### Actions Taken
- 在 `D:\UserData\Desktop\study\` 下新建 `llm-wiki/` 子项目目录
- 创建 raw/ 全部子目录(articles, books, papers, transcripts, notes, assets)
- 创建 wiki/ 全部子目录(concepts, people, organizations, projects, sources, questions, claims, contradictions, maps, glossary)
- 在每个子目录下放 README.md,说明该目录的用途、命名规范、如何放入资料
- 写入完善版 CLAUDE.md(填充了通用学习型 Wiki 的占位符,补充了与同级 study/ 系统的边界、Obsidian 设置建议、git 建议)
- 创建 wiki/index.md(初始版导航地图)
- 创建 wiki/log.md(本文件)
- 在 wiki/questions/ 创建一个示例页 `example-how-to-use-this-wiki.md`,作为标准页模板的活样板
- 在 llm-wiki/ 根目录创建 README.md,作为新手快速上手指南

### Files Read
- (未读取任何 raw/ 文件;raw/ 当前为空)
- D:\UserData\Desktop\study\schema\AI-RULES.md(为了避免与同级 study 体系冲突,而非用于 ingest)

### Files Created
- llm-wiki/CLAUDE.md
- llm-wiki/README.md
- llm-wiki/raw/articles/README.md
- llm-wiki/raw/books/README.md
- llm-wiki/raw/papers/README.md
- llm-wiki/raw/transcripts/README.md
- llm-wiki/raw/notes/README.md
- llm-wiki/raw/assets/README.md
- llm-wiki/wiki/index.md
- llm-wiki/wiki/log.md
- llm-wiki/wiki/concepts/README.md
- llm-wiki/wiki/people/README.md
- llm-wiki/wiki/organizations/README.md
- llm-wiki/wiki/projects/README.md
- llm-wiki/wiki/sources/README.md
- llm-wiki/wiki/questions/README.md
- llm-wiki/wiki/questions/example-how-to-use-this-wiki.md
- llm-wiki/wiki/claims/README.md
- llm-wiki/wiki/contradictions/README.md
- llm-wiki/wiki/maps/README.md
- llm-wiki/wiki/glossary/README.md

### Files Updated
- (无)

### Assumptions
- 用户的 study/ 目录已存在另一套"学习教练"体系(study/raw、study/wiki、study/schema、study/wiki/00-学习进度.md 等),本 Wiki 与之独立、互不干扰。
- "Wiki 主题"采用通用学习型(不预先限定 LLM/AI),由资料涌现主题,因此初始 index.md 不预设具体领域条目。
- 用户没有 git,故仅在 CLAUDE.md 第 17 节给出 git 建议而不强制。

### Issues / Uncertainty
- 沙箱 Linux 启动慢,bootstrap 全程使用 Read/Write/Edit 直接操作 Windows 文件系统(未使用 bash)。这不影响后续工作。

### Recommended Next Step
1. 把你想要整理的"第一份资料"放到 `raw/` 对应子目录:
   - 文章/博客 → `raw/articles/`
   - 论文 PDF → `raw/papers/`
   - 视频字幕 → `raw/transcripts/`
   - 自己的笔记 → `raw/notes/`
2. 在新对话里说: "请阅读 CLAUDE.md,然后按 Ingest Workflow 处理 raw/articles/xxx.md"
3. Claude 会创建对应的 sources 摘要页 + 抽出的概念页,并更新 index.md 和 log.md

---

## 2026-05-06 - Inbox System Bootstrap

### Operation
bootstrap (extension)

### User Request
用户参考 GPT 的建议,要求把"整理资料"这一步压缩成一个收件箱入口:
"看到资料 → 丢进 inbox → 对 Claude 说处理 inbox" 即可,不再需要手动分类、命名、转 Markdown。

### Actions Taken
- 在 `raw/` 下新建 `inbox/` 完整结构(urls.md / notes.md / clippings.md / ideas.md / web/ / pdfs/ / videos/ / images/ / misc/)
- 每个子目录下放说明用 README,各自给出"什么放进来 / 怎么放 / 失败时怎么办"
- urls.md / notes.md / clippings.md / ideas.md 四个文本入口都自带使用模板,降低上手摩擦
- 在 CLAUDE.md 新增 §11.7 "Inbox Import Workflow"(完整定义:去重规则、URL 抓取、PDF 提取、视频字幕、图片识别、notes/clippings/ideas 处理、规范化 front-matter)
- 在 CLAUDE.md 新增 §11.8 "Inbox Processing Status Page Template"
- 创建 `wiki/questions/inbox-processing-status.md` 状态仪表盘(带表格化处理记录、失败标签速查)
- 在 `wiki/index.md` 顶部新增"★ 最常用的入口:Inbox(收件箱)"区块,把 inbox 提到最显眼位置
- 在 `wiki/index.md` 的 Key Questions 与 Maintenance Notes 都同步加入 inbox 链接

### Files Read
- (无;inbox 当前为空,本次只搭骨架)

### Files Created
- llm-wiki/raw/inbox/README.md
- llm-wiki/raw/inbox/urls.md
- llm-wiki/raw/inbox/notes.md
- llm-wiki/raw/inbox/clippings.md
- llm-wiki/raw/inbox/ideas.md
- llm-wiki/raw/inbox/web/README.md
- llm-wiki/raw/inbox/pdfs/README.md
- llm-wiki/raw/inbox/videos/README.md
- llm-wiki/raw/inbox/images/README.md
- llm-wiki/raw/inbox/misc/README.md
- llm-wiki/wiki/questions/inbox-processing-status.md

### Files Updated
- llm-wiki/CLAUDE.md (新增 §11.7、§11.8)
- llm-wiki/wiki/index.md (新增 inbox 入口区块,更新维护备注)
- llm-wiki/README.md (新增"丢进 inbox"极简流程,放在最前面)

### Assumptions
- GPT 原方案的 `notes.md` 单一入口拆成了四个(notes / clippings / ideas / urls),减少 notes.md 越塞越乱的问题。
- 增加了 GPT 方案没强调的"去重(dedup by URL/title slug/content hash 1KB)"规则,避免同一份资料被处理两次。
- urls.md 改成了"待处理 / 已处理"两区结构,Claude 处理后会移行而不是删除——保留你的写作痕迹。
- PDF 二进制文件保留在 `raw/inbox/pdfs/`,只把派生的 Markdown 副本放进 `raw/papers/`,避免重复占空间。

### Issues / Uncertainty
- 视频字幕拉取依赖 yt-dlp 等命令行工具是否在沙箱里可用,失败概率不低。CLAUDE.md 已强制"失败时如实告知,不编造"。
- 扫描版 PDF 的 OCR 暂未自动化(避免引入 Tesseract / 云 OCR 依赖),只标 needs-ocr 由用户决定。

### Recommended Next Step
1. 把任何一份资料(链接、PDF、截图、随手笔记都行)丢进 `raw/inbox/` 对应位置
2. 在新对话开头粘下面这段(已写进 README.md):

   ```
   请阅读 D:\UserData\Desktop\study\llm-wiki\CLAUDE.md,
   然后按 §11.7 Inbox Import Workflow 处理 raw/inbox/。
   完成后更新 wiki/questions/inbox-processing-status.md、wiki/index.md、wiki/log.md,
   并用中文告诉我:成功导入了什么、失败了什么、需要我人工处理什么、下一步建议。
   ```

3. (可选)给浏览器装 Obsidian Web Clipper,保存路径设为
   `D:\UserData\Desktop\study\llm-wiki\raw\inbox\web\`,以后网页一键存

---

## 2026-05-06 - First Inbox Import

### Operation
inbox-import

### User Request
用户在 `raw/inbox/notes.md` 写下 5 行关于 RAG 的研究问题,触发 §11.7 Inbox Import Workflow。

### Actions Taken
- 清点 inbox:仅 notes.md 有内容(5 行 RAG 问题),其他入口为空
- 分类:判断为"用户原创的研究问题清单"(单一主题、连贯、共时,作为整体处理而非 5 条独立 note)
- 去重:`raw/notes/` 为空,无重复
- 归档:创建 `raw/notes/2026-05-06-rag-research-questions.md`(规范化 front-matter,保留原文逐条)
- Ingest:
  - 1 × source 摘要页 `wiki/sources/2026-05-06-rag-research-questions.md`
  - 5 × question 页(rag-essence / rag-experts-mental-model / rag-experts-debates / rag-upper-and-lower-bounds / rag-vs-no-rag-ceilings)— 全部 `status: open`、`evidence: needs-source`,严格不编造答案
  - 1 × concept 页 `wiki/concepts/rag.md`(draft 状态)
  - 1 × glossary 页 `wiki/glossary/rag.md`(占位定义,标 needs-source)
- 处理 inbox 原文:把 notes.md 的"我的笔记"区清空,在文件下方追加"已处理"区,原文 5 行以引用形式保留(不删除)
- 更新 `wiki/index.md` 五处:Core Concepts、Key Questions、Recent Sources、Glossary、Maintenance Notes
- 更新 `wiki/questions/inbox-processing-status.md`(填本次处理记录、待人工处理清单、下一步建议)

### Files Read
- raw/inbox/urls.md
- raw/inbox/notes.md
- (其他 inbox 子目录与文件均空,仅有 README,未读)

### Files Created
- raw/notes/2026-05-06-rag-research-questions.md
- wiki/sources/2026-05-06-rag-research-questions.md
- wiki/questions/rag-essence.md
- wiki/questions/rag-experts-mental-model.md
- wiki/questions/rag-experts-debates.md
- wiki/questions/rag-upper-and-lower-bounds.md
- wiki/questions/rag-vs-no-rag-ceilings.md
- wiki/concepts/rag.md
- wiki/glossary/rag.md

### Files Updated
- raw/inbox/notes.md(原文移到"已处理"区,以引用形式保留)
- wiki/index.md
- wiki/questions/inbox-processing-status.md

### Assumptions
- 这 5 行是**同一主题的整体问题清单**,不拆成 5 条独立 note,而是作为一份 source + 5 张衍生 question 页处理。
- 概念页 `rag.md` 和 glossary `rag.md` 双轨并存,等证据丰富后再决定是否合并(已写入 inbox-processing-status 待办)。
- 用户没有指定具体"顶级 RAG 工程师"是谁,问题页里只列出**候选名单作为方向提示**,明确标注"由 Wiki 列出而非证据支持"。

### Issues / Uncertainty
- 5 个问题页的 evidence 都只有用户笔记一份,实际答案能力为零。这是符合 §2.2 "No Fabrication" 的诚实状态,但也意味着 Wiki 当前不能用来回答 RAG 问题。
- 概念页 `rag.md` 写得相当克制(Details 留空),避免在没有外部来源的情况下展开技术细节而触发 §2.2。

### Recommended Next Step
1. 把 RAG 原论文链接 `https://arxiv.org/abs/2005.11401` 粘到 `raw/inbox/urls.md`
2. 再说"处理 inbox" — 这一次会真正给 5 个 needs-source 的问题页补上第一份硬证据
3. 后续可以陆续把 Lilian Weng / LlamaIndex / LangChain 博客等丢进 inbox,逐步把 confidence 从 low 提到 medium

---

## 2026-05-06 - Add Inbox Uploader (HTML)

### Operation
bootstrap (extension)

### User Request
用户表示"上传资料太麻烦",希望有简约高级感风格的网页/桌面端中文工具来上传。
经过澄清,选择:单文件 HTML(双击即用)、丝绸黑金风、支持文字/链接/文件三种入口。

### Actions Taken
- 在项目根目录创建 `inbox-uploader.html`(单文件,无外部依赖,无 CDN)
  - 设计:深色背景 + 金色 accent + 玻璃拟态卡片 + 丝绸纹理(纯 CSS 实现,无图片)
  - 三个标签页:文字 / 链接 / 文件
  - 文字面板:三种类型 segmented control(笔记/摘录/灵感)、可选标题与来源、自动 front-matter、Ctrl/⌘+Enter 保存
  - 链接面板:一键复制成 urls.md 待处理区格式 + 备份 .txt 下载
  - 文件面板:拖放 / 点击选择,按后缀自动提示对应 inbox 子目录(pdfs/web/images/videos/misc),批量下载
  - localStorage 草稿自动保存,关页面不丢
  - Toast 提示、文件名时间戳化(避免重名)、slugify 处理特殊字符
- 在 `README.md` 顶部"一句话用法"下方新增"✨ 想更省事?用上传工具"区块,讲清三标签页、工作流、小提示

### Files Created
- llm-wiki/inbox-uploader.html

### Files Updated
- llm-wiki/README.md

### Assumptions
- 浏览器打开本地 HTML 不能直接写到磁盘,所以采用"下载到系统下载目录 → 用户拖进 inbox"的折中。这是单文件零依赖方案的天花板。
- 如果用户后续希望"点保存就直接落到 raw/inbox/",需要切换到方案 B(本地 Python 后台 + 网页前端),需要装 Python——这是本次没选的路径。
- 配色采用深色 #08070a + 金色 #d4af6a 系统,丝绸纹理用 repeating-linear-gradient 极淡斜线 + 金色径向光晕实现,纯 CSS,无外部资源。

### Issues / Uncertainty
- 部分浏览器在批量下载多个文件时会拦截。已用 250ms 错峰下载缓解,但极端情况(>10 个文件一批)用户可能需要在浏览器允许"自动下载多个文件"。
- localStorage 不在隐私模式下持久化。隐私模式下打开会丢草稿——这是浏览器固有限制。

### Recommended Next Step
1. 双击 `D:\UserData\Desktop\study\llm-wiki\inbox-uploader.html` 体验一下
2. 试着用"链接"标签页,粘一行 RAG 论文链接,点"复制到剪贴板",再粘到 `raw/inbox/urls.md` 的"待处理"区
3. 然后说"处理 inbox",看完整闭环
4. (未来可选)若希望连"拖文件到 inbox"这步都省掉,可以让我做方案 B:本地 Python 服务,文件直接落盘

---

## 2026-05-06 - Inbox Uploader v2: Direct Disk Write (File System Access)

### Operation
bootstrap (extension)

### User Request
用户反馈 v1 仍然需要"下载 → 拖入 inbox"两步,和之前没区别;希望省掉"打开文件夹、拖文件"的过程。
讨论了三个方案:
- B(Python 后台):需要装 Python、每次启动服务,代价大
- C(File System Access API):零安装,授权一次后直写盘,只在 Chrome/Edge 工作
- D(PWA):C 的延伸,体验类似桌面应用
用户选 **C**,确认平时用 Chrome/Edge,不做 B 兜底。

### Actions Taken
- 重写 `inbox-uploader.html`,在保留 v1 全部 UI 的基础上加入 File System Access 直写盘:
  - 顶部新增**连接状态条**:金色 LIVE 标签(已连接)/ 黄色未连接 / 红色不支持,直观显示当前模式
  - "连接 inbox 文件夹"按钮:调用 `showDirectoryPicker()`,首次需要用户选择 `raw/inbox/` 并授予 readwrite 权限
  - **handle 持久化**:用 IndexedDB 存 FileSystemDirectoryHandle,重开浏览器后能记住"上次选的是哪个",只需用户点一次"重新连接"恢复(浏览器安全规则要求每会话再授权一次)
  - **inbox 健全性检查**:连接时扫描该目录,若没看到 urls.md / notes.md / clippings.md / ideas.md 任一,弹确认框提示用户可能选错了目录
  - **文字面板**:点保存 → 直接 `getFileHandle({create:true}).createWritable()` 写到 `raw/inbox/`(根目录)
  - **链接面板**:点"追加到 urls.md" → 读 urls.md 现有内容 → 智能定位"## 待处理 (pending)"section → 在该 section 末尾追加新 block(不存在则创建文件并写入完整骨架),不会覆盖用户内容
  - **文件面板**:按后缀自动落到对应子目录(`getDirectoryHandle({create:true})`),子目录不存在会自动创建
  - **降级路径**:浏览器不支持 API、用户未连接、或权限被撤销 → 自动回到 v1 的"下载 + 提示拖入"模式,功能仍可用
  - 保存成功后清空对应输入(文字面板清正文 / 链接面板清列表 / 文件面板移除已保存项),减少误重发
- README.md "✨ 推荐:零安装上传工具"区块全面重写:讲清"第一次连接"5 步、"之后每次"如何用、"重新打开浏览器后"的 1 步恢复、为什么不是 Firefox/Safari

### Files Updated
- llm-wiki/inbox-uploader.html(v1 → v2,从下载模式升级为直写盘 + 下载降级)
- llm-wiki/README.md

### Assumptions
- 用户用 Chrome/Edge 访问本地 file:// 路径时,File System Access API 可用。注意:某些 Chromium 衍生浏览器或企业策略可能禁用此 API,届时会自动降级。
- 把笔记/摘录/灵感都写到 inbox 根目录(而不是分别写到 notes.md / clippings.md / ideas.md 末尾),理由是:每条笔记是独立 .md 文件更利于 Claude 后续分类、归档、溯源,且不会造成 4 个入口文件膨胀。
- urls.md 的追加策略选"插在 ## 待处理 (pending) section 内的末尾",不放最顶部也不覆盖,保留用户已有的注释和示例。

### Issues / Uncertainty
- 浏览器对 File System Access 的 handle 持久化只到"应用数据被清理"为止;如果用户清浏览数据会丢失,需要再次走完整选择流程。这是浏览器固有限制,工具无法绕过。
- 同名文件保存时会**覆盖**(默认行为)。考虑到文件名带 `YYYY-MM-DD-HHmm` 时间戳,实际重名概率极低;但 1 分钟内连续两次保存同标题可能撞车。后续若需严格防覆盖可改为先 `getFileHandle({create:false})` 检测、撞名时加 `-2` 后缀。

### Recommended Next Step
1. 用 Chrome 或 Edge 双击打开 `D:\UserData\Desktop\study\llm-wiki\inbox-uploader.html`
2. 点"连接 inbox 文件夹",选 `D:\UserData\Desktop\study\llm-wiki\raw\inbox`,允许写权限
3. 看到金色 **LIVE** 标签即代表生效
4. 在"链接"标签里粘一行 RAG 论文 URL `https://arxiv.org/abs/2005.11401`,点"追加到 urls.md"
5. 打开 `raw/inbox/urls.md` 验证它确实落到了"待处理"区
6. 然后回到 Claude 说"处理 inbox"

---

## 2026-05-07 - Second Inbox Import: GPT Synthesis on AI Engineering

### Operation
inbox-import

### User Request
用户通过 inbox-uploader.html(直写盘版 v2)上传了一篇文章,触发 §11.7 Inbox Import Workflow。

### Inbox 实况
- 文件:`raw/inbox/2026-05-07-0948-notes-如何成为顶级AI工程师.md`(由 inbox-uploader 直写盘生成,文件名前缀正确)
- 用户标的 kind:notes;来源标:GPT
- 内容:约 9000 字,关于"如何成为顶级 AI 应用工程师"的长篇综述,引用 Stanford AI Index 2026 / McKinsey 2025 / Stack Overflow 2025 / OWASP / NIST / OpenAI / Anthropic / LangChain / Cursor / Lovable / Perplexity,**但全部未给 URL**

### Actions Taken
- 重新分类:用户标的 note → 实际为 LLM-generated 长篇综述,改归 `article` 更准确
- **关键判定**:文章引用的所有"权威报告"都是 GPT 转述,无 URL。Wiki 视为 **secondhand**,所有衍生页 `confidence: low` + `evidence_quality: secondhand-via-gpt`,严格遵守 §2.2 不编造
- 归档:`raw/articles/2026-05-07-gpt-how-to-become-top-ai-engineer.md`,带"来源警示"front-matter,完整保留前 4 大节内容,后半节略
- 创建 source 摘要页:`wiki/sources/2026-05-07-gpt-how-to-become-top-ai-engineer.md`,顶部明确标"来源等级声明",列 6 组 secondhand 数据点供未来核实
- 创建 4 个新概念页:[[agent]] / [[context-engineering]] / [[evals]] / [[tool-calling]],全部标 secondhand,Details 节留白避免传 GPT 转述
- 创建 1 个人物页:[[harrison-chase]](作为 [[rag-experts-mental-model]] 候选清单第一人)
- 创建 4 个项目页:[[langchain]] / [[cursor]] / [[lovable]] / [[perplexity]]
- 创建 2 个组织占位页:[[anthropic]] / [[openai]](仅为让其他页可 link,内容空)
- 创建 1 个新 question 页:[[top-ai-engineer-capabilities]],承接文章主论点,confidence low
- 创建 4 个 glossary 词条
- **更新 2 个已有 RAG 问题页**:[[rag-essence]] 和 [[rag-experts-mental-model]] 从全 needs-source 升级到 secondhand-via-gpt(仍待一手),把候选人物页链上
- 把 inbox 原文件 front-matter 改为 status: processed,加"已处理"提示,**不删除**用户原文
- 更新 wiki/index.md(5 个区块都加了新链接 + 维护备注)
- 更新 wiki/questions/inbox-processing-status.md(新处理记录 + 待人工 + 下一步建议)

### Files Read
- raw/inbox/2026-05-07-0948-notes-如何成为顶级AI工程师.md
- wiki/index.md / wiki/log.md / wiki/questions/inbox-processing-status.md
- 已有 RAG 问题页(为了反向链接更新)

### Files Created
- raw/articles/2026-05-07-gpt-how-to-become-top-ai-engineer.md
- wiki/sources/2026-05-07-gpt-how-to-become-top-ai-engineer.md
- wiki/concepts/agent.md
- wiki/concepts/context-engineering.md
- wiki/concepts/evals.md
- wiki/concepts/tool-calling.md
- wiki/people/harrison-chase.md
- wiki/projects/langchain.md
- wiki/projects/cursor.md
- wiki/projects/lovable.md
- wiki/projects/perplexity.md
- wiki/organizations/anthropic.md
- wiki/organizations/openai.md
- wiki/questions/top-ai-engineer-capabilities.md
- wiki/glossary/agent.md
- wiki/glossary/context-engineering.md
- wiki/glossary/evals.md
- wiki/glossary/tool-calling.md

### Files Updated
- raw/inbox/2026-05-07-0948-notes-如何成为顶级AI工程师.md(front-matter status → processed,加提示,不删原文)
- wiki/questions/rag-essence.md(补 secondhand evidence)
- wiki/questions/rag-experts-mental-model.md(补 secondhand evidence + 候选人物链接)
- wiki/index.md
- wiki/questions/inbox-processing-status.md

### Assumptions
- **将用户标的 `kind: notes` 改为 `article`**:理由是文章长度(9000 字)、有结构、有引用、有论点,作为可被反复引用的"来源"而非"个人随笔"价值更高。这一改动在归档版 front-matter 与 source 摘要页都做了显式说明。
- **不入 wiki/claims/**:文章里 6 组数据点(Stanford / McKinsey / MIT NANDA / SO / Cursor / Lovable)都是 GPT 转述,直接入主张库会污染 confidence。改为在 source 摘要页列"待核实清单"。
- **anthropic / openai 占位页**:为了让概念页可 link,但内容刻意保持空,等一手资料 ingest 后再展开,避免占位页被误读为已有内容。
- **概念页 Details 节留白**:严格执行"不传 secondhand 技术细节",而是把"待 ingest 的一手文档名"写出来。

### Issues / Uncertainty
- 这次 ingest 让 Wiki 从"几乎全空"跳到"15+ 页面",但因为来源是单一 LLM 综述,**confidence 没有真正提升**。这是符合预期的诚实结果,不是失败。
- inbox 文件保留了 status: processed 标记,但物理上仍在 raw/inbox/。CLAUDE.md §11.7 没规定要不要清出 inbox。当前选择是保留——它是不可改的"原始凭证",将来如果归档版有疑问可以回查。如果用户希望 inbox 始终是"待处理列表",未来可以考虑把已处理的移到 `raw/inbox/processed/` 子目录。

### Recommended Next Step
1. **下一份 inbox 必须是一手资料**,否则 Wiki 会陷入"全是 GPT 二手综述"的退化。最高 ROI 单一资料:
   - Anthropic 官方"Building Effective Agents"博文 → 一次升级 3 个概念页
2. 如果想继续围绕本文展开,把任意一份 Harrison Chase / Jerry Liu / Cursor 创始人的访谈丢进 inbox
3. 等积累到 5+ 个 RAG / Agent 相关概念页有真证据后,在 `wiki/maps/` 建第一张主题地图 "ai-engineering-map.md"

---

## 2026-05-07 - Obsidian Vault Bootstrap + First Topic Map

### Operation
bootstrap (extension)

### User Request
用户看到别人的 Wiki 都有"知识地图"(圆点 + 连线),问自己缺了什么。
确认是 Obsidian Graph View,选了"装 Obsidian",请我代为完成所有可代劳的部分。

### Actions Taken
- 在 `llm-wiki/.obsidian/` 预配置了 8 份 JSON,装好 Obsidian 打开 vault 即生效:
  - `app.json`:新文件位置 = wiki/、附件位置 = raw/inbox/images/、shortest 链接格式、忽略过滤 raw/inbox/
  - `appearance.json`:深色基础主题(theme: obsidian)
  - `graph.json`:graph 视图配色分组(7 类按 path 区分)、排除 inbox 与 _templates、力学参数调到适合阅读的值
  - `core-plugins.json`:开启 16 个核心插件(file-explorer/search/graph/backlink/templates 等)
  - `workspace.json`:左侧栏 = 文件管理器/搜索/收藏,右侧栏 = 反向链接/大纲/Graph,主区默认打开 README
  - `templates.json`:模板目录指向 wiki/_templates
  - `bookmarks.json`:预放 6 个常用入口快捷方式(README、index、AI 工程地图、inbox 状态、log、Graph View)
  - `hotkeys.json`:Ctrl+G 打开全局图谱、Ctrl+Shift+G 打开局部图谱
- 建 `wiki/_templates/` 目录,8 份模板严格对应 CLAUDE.md §5-§8 + 人物/项目/地图/问题:
  - 00-concept / 01-source / 02-claim / 03-contradiction / 04-question / 05-person / 06-project-or-org / 07-map
  - 用 Obsidian Templates 核心插件即可使用(无需 Templater)
- 建项目根目录 `OPEN-IN-OBSIDIAN.md`:三步傻瓜指南、装好后该做什么、失败兜底表
- 建第一张手写主题地图 `wiki/maps/ai-engineering-map.md`:把当前 17 个 AI 工程相关页面织成一条主线(入口 → 4 大概念 → evals → 4 个产品案例 → 人物组织 → 5 个 RAG 问题),诚实标 secondhand,列"还缺什么"清单
- 更新 `README.md`:新增"想要知识地图?"区块,把 OPEN-IN-OBSIDIAN.md 当主入口
- 更新 `wiki/index.md`:Main Maps 区填入 [[ai-engineering-map]]

### Files Created
- llm-wiki/.obsidian/app.json
- llm-wiki/.obsidian/appearance.json
- llm-wiki/.obsidian/graph.json
- llm-wiki/.obsidian/core-plugins.json
- llm-wiki/.obsidian/workspace.json
- llm-wiki/.obsidian/templates.json
- llm-wiki/.obsidian/bookmarks.json
- llm-wiki/.obsidian/hotkeys.json
- llm-wiki/wiki/_templates/README.md
- llm-wiki/wiki/_templates/00-concept.md ~ 07-map.md(8 份)
- llm-wiki/OPEN-IN-OBSIDIAN.md
- llm-wiki/wiki/maps/ai-engineering-map.md

### Files Updated
- llm-wiki/README.md(新增"知识地图"区块)
- llm-wiki/wiki/index.md(Main Maps 填充)

### Assumptions
- 用户用 Windows + Obsidian 桌面版。配置文件用 forward slash 路径(Obsidian 在 Windows 下也接受 forward slash,跨平台兼容)。
- workspace.json 选择"启动时主区显示 README、左侧文件管理器开着、右侧 graph 标签备用"——这是新手最容易上手的布局。
- 新文件位置设为 wiki/(而不是 vault 根目录),避免用户不小心把笔记建到 raw/ 污染原始层。
- 附件位置设为 raw/inbox/images/,这样 Obsidian 直接粘贴截图也会落到 inbox,与 inbox-uploader 的工作流一致。
- 模板没装 Templater 也能用——核心 templates 插件就够,降低用户上手门槛。

### Issues / Uncertainty
- `.obsidian/workspace.json` 在 Obsidian 启动后会被它改写为最新状态,不会一直保持我设的初始布局。但首次打开仍然会按我的设置显示一次,达到"第一印象很好"的效果。
- bookmarks.json 里 graph 类型的 bookmark 格式我用了 Obsidian 1.x 标准,极少数情况下旧版本可能不识别——会被自动忽略,不影响主功能。
- 没有强制启用 Restricted mode 或 Trust 状态——用户首次打开 vault 时仍需自己点一下 "Trust author and enable plugins",这是 Obsidian 安全设计,无法绕过。OPEN-IN-OBSIDIAN.md 里已写明这一步。

### Recommended Next Step
1. 用户下载并安装 Obsidian,按 OPEN-IN-OBSIDIAN.md 三步打开 vault
2. 看 graph + 主题地图,反馈印象
3. 如果 graph 出现孤立节点(orphan,即没人链向它的页),触发一次"Lint Workflow"补链接
4. 若想继续扩展,把"在 Obsidian 里手写一页笔记 → Claude 接力整理"也接入工作流

---

## 2026-05-07 - First Lint After Obsidian Bootstrap

### Operation
lint

### User Request
用户已装好 Obsidian 并打开 vault(可以从 workspace.json 自动汉化、bases/canvas 默认开启等迹象确认)。在用户开始用 Graph View 之前,跑一次健康度体检,确保图谱不出现孤立节点和坏链——避免第一印象不好。

### Actions Taken
- 扫描 wiki/ 全部 33 个页面,逐条比对 138+ 个 `[[]]` 链接是否解析得到
- 发现 5 个孤立 glossary 节点(rag/agent/evals/context-engineering/tool-calling 速查页) → 在每个对应 concept 页顶部加 `[[wiki/glossary/xxx|速查词条]]` 反向链
- 发现 3 处坏链:
  - `[[index]]`(应该是 `[[wiki/index]]`)
  - `[[wiki/glossary/]]`、`[[wiki/claims/]]`(它们想表达的是目录路径,不是 wikilink) → 改为反引号路径
- 发现 5 个 RAG 问题页之间互链不完整 → 补全成 K5 完全图,在图谱里形成紧密簇
- 发现 4 个产品页(langchain/cursor/lovable/perplexity)修前几乎不互链 → 加横向链接成"产品案例"簇
- 让 [[ai-engineering-map]] 被 [[top-ai-engineer-capabilities]] 反链(主题地图不再只被 index 链)
- 让 [[example-how-to-use-this-wiki]] 被 [[inbox-processing-status]] 反链(不再孤立)
- 写 `wiki/questions/wiki-health-check.md`:总结所发现问题、修复动作、剩余覆盖缺口、Graph View 验证清单

### Files Created
- wiki/questions/wiki-health-check.md

### Files Updated
- wiki/concepts/rag.md / agent.md / context-engineering.md / evals.md / tool-calling.md(加 glossary 反向链)
- wiki/questions/example-how-to-use-this-wiki.md(修 [[index]] 坏链)
- wiki/maps/ai-engineering-map.md(修 [[wiki/glossary/]] 坏链)
- wiki/questions/inbox-processing-status.md(修 [[wiki/claims/]] 坏链 + 加 example 反链)
- wiki/questions/rag-experts-mental-model.md / rag-upper-and-lower-bounds.md / rag-vs-no-rag-ceilings.md(补全 RAG K5 互链)
- wiki/projects/cursor.md / lovable.md / perplexity.md(补"产品案例"集群互链)
- wiki/questions/top-ai-engineer-capabilities.md(链 ai-engineering-map)
- wiki/index.md(加 wiki-health-check 入口)

### Assumptions
- Obsidian 默认用 "shortest" link 格式时同名文件会歧义,所以 glossary 反向链用了 `[[wiki/glossary/rag|...]]` 完整路径形式,Obsidian 会显示别名而不是完整路径。
- "K5 完全图"只对 5 个 RAG 问题做(它们是用户原始问题清单的一组,逻辑上确实互相依赖)。其他主题不做完全图,避免 Graph View 变成毛线团。
- 不强行让所有 glossary 页相互链接——它们功能是"速查",不是讨论,横向连接没有信息价值。

### Issues / Uncertainty
- Obsidian 1.x 在 `userIgnoreFilters` 配置 `raw/inbox/` 后,**仍可能在 Graph View 第一帧显示 inbox 节点**(已知小 bug,刷新即消失)。已在 wiki-health-check 提示用户。
- 所有修补只动了链接,**没有改任何内容主张**。所有页面的 secondhand 标记和 confidence 都不变。

### Recommended Next Step
1. 用户在 Obsidian 里按 Ctrl+G 打开图谱,验证修复(应该看到 ~30 节点 + 4 个清晰簇,无孤点)
2. 看 [[wiki-health-check]] 的"Next 5 Actions"—— ingest Anthropic Building Effective Agents 是 ROI 最高的下一步
3. 若图谱配色没生效:Ctrl+P → "Reload app without saving"
