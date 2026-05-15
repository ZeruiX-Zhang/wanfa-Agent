# raw/inbox/web/

放在这里的内容:用浏览器扩展(Obsidian Web Clipper / MarkDownload 等)保存下来的网页 Markdown 文件。

## 推荐工具

**Obsidian Web Clipper(首选)**
- Chrome / Firefox / Edge / Safari 都有
- 安装后,在扩展设置里把"保存路径"设为本目录的绝对路径:
  `D:\UserData\Desktop\study\llm-wiki\raw\inbox\web`
- 看到任何想保存的网页 → 点扩展图标 → 自动落到这里

**MarkDownload(备选)**
- 当 Web Clipper 抓不全时(某些网站的反爬、登录墙)用它
- 设置同样指向本目录

## 命名建议

工具会自动用网页标题命名,通常已经够用。如果出现奇怪字符或冲突,**不要手改**——Claude 在处理 inbox 时会重命名为 `YYYY-MM-DD-slug.md` 并归档到 `raw/articles/`。

## 抓不全怎么办?

直接保留下来。Claude 处理时会:
1. 读一遍内容,判断是否够用
2. 不够用就标记 `needs-fetch` 或 `needs-fulltext`,告诉你哪些链接需要你自己再访问一次
3. 永远不会假装内容完整然后乱总结
