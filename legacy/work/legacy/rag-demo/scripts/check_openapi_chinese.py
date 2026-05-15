from __future__ import annotations

import json
import os
import sys
from urllib.error import URLError
from urllib.request import ProxyHandler, build_opener


OPENAPI_URL = os.getenv("OPENAPI_URL", "http://127.0.0.1:8765/openapi.json")
OPENER = build_opener(ProxyHandler({}))

KEYWORDS = [
    "企业知识库 RAG 与多工具 Agent 演示系统",
    "RAG 问答",
    "文档管理",
    "Agent 执行",
    "评测",
    "执行 RAG 问答",
    "用户提出的问题",
    "业务域",
    "引用来源",
    "工具调用",
    "检索评测",
]


def main() -> int:
    try:
        with OPENER.open(OPENAPI_URL, timeout=10) as response:
            payload = response.read().decode("utf-8")
    except URLError as exc:
        print(f"无法请求 OpenAPI：{OPENAPI_URL}\n{exc}", file=sys.stderr)
        return 1

    missing = [keyword for keyword in KEYWORDS if keyword not in payload]
    if missing:
        print("OpenAPI 中文化检查失败，缺失关键词：", file=sys.stderr)
        for keyword in missing:
            print(f"- {keyword}", file=sys.stderr)
        return 1

    spec = json.loads(payload)
    print(f"OpenAPI 中文化检查通过：{spec['info']['title']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
