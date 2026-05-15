# raw/inbox/videos/

放在这里的内容:视频/音频的字幕或转录文件(`.srt`、`.vtt`、`.txt`、`.md`)。

## 视频本身放哪?

**不要把视频文件本身放进来**——文件大、不可搜索。
你需要的是它的"文字稿":
- YouTube → 视频底下点"显示文字记录"复制
- B 站 → 用第三方字幕导出工具
- 自己录的 → 用 Whisper / 飞书妙记 / 通义听悟 转录后导出 .txt

## 视频链接呢?

链接放到 `../urls.md`,Claude 处理 inbox 时会尝试拉字幕。
拉不到就告诉你,需要你自己抄。

## 命名建议

`YYYY-MM-讲者-标题简写.txt`
例:`2024-04-Karpathy-MakeMore-Lecture5.txt`

## 字幕质量提示

- 平台官方字幕 > 平台自动字幕 > Whisper > 第三方
- 如果是自动字幕,Claude 在 source 摘要里会标 `transcript_quality: auto`,提醒你某些细节可能不准
