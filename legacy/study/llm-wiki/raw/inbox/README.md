# raw/inbox/ — 收件箱(你只管扔,别想分类)

这是整个 Wiki 的**唯一入口**。
不知道资料该放哪?**统统扔到 inbox/。**
然后对 Claude 说:**"处理 inbox"**。

---

## 子目录一句话指南

```
raw/inbox/
├── urls.md        ← 粘任何链接(网页/视频/论文 PDF 链接)
├── notes.md       ← 临时随手粘的纯文字
├── clippings.md   ← 你看书/看视频时摘抄的句子和金句
├── ideas.md       ← 你自己的灵感、半成品想法、对话片段
├── web/           ← Obsidian Web Clipper 等保存的网页 .md
├── pdfs/          ← 直接拖进来的 PDF
├── videos/        ← 视频字幕、转录文件(.srt/.vtt/.txt/.md)
├── images/        ← 截图、照片、图表
└── misc/          ← 真的不知道放哪就扔这里
```

---

## 三条铁律

1. **inbox 是落地区,不是归宿。** 处理后,Claude 会把内容规范化到 `raw/articles/`、`raw/papers/`、`raw/transcripts/` 等正式目录,inbox 文件原样保留作为"凭证"。
2. **不要在 inbox 里"先整理一遍再丢"。** 那会让你拖延。原则就是:看到资料 → 0 思考扔进来 → 让 Claude 整理。
3. **同一份资料丢两次不会爆炸。** Claude 在处理时会和已存档的资料对比(标题、URL、内容前 1KB),自动跳过重复。

---

## 触发处理的暗号

在新对话里对 Claude 说任何一句都会触发 Inbox Import Workflow:

- "处理 inbox"
- "导入 inbox"
- "整理新资料"
- "import inbox"

详细规则见项目根目录 `CLAUDE.md` 第 11.7 节。
