from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app import main


client = TestClient(main.app)


@pytest.fixture(autouse=True)
def isolated_runtime() -> None:
    base = Path.cwd() / ".pytest_tmp" / "runtime"
    if base.exists():
        shutil.rmtree(base)
    root = base / "knowledge_os"
    (root / "wiki" / "sources").mkdir(parents=True)
    (root / "claims").mkdir(parents=True)
    (root / "graph").mkdir(parents=True)
    (root / "wiki" / "personal").mkdir(parents=True)
    (root / "wiki" / "sources" / "desktop-workspaces.md").write_text(
        """---
title: PromptAgent desktop workspaces
summary: Desktop has three main workspaces: Prompt Lab, Knowledge OS, and Settings.
collection: product
tags: desktop, prompt-lab, knowledge-os
created_at: 2026-05-07T00:00:00+08:00
source_url:
---

# PromptAgent desktop workspaces

## 摘要

桌面端由提示词实验室、知识系统和设置三个主要工作区组成。
""",
        encoding="utf-8",
    )
    claim = {
        "id": "claim_desktop_workspaces",
        "text": "PromptAgent 桌面端主导航包含提示词实验室、知识系统和设置。",
        "status": "supported",
        "confidence": 0.9,
        "evidence": [{"source_page": "wiki/sources/desktop-workspaces.md", "quote": "三个主要工作区"}],
        "source_page": "wiki/sources/desktop-workspaces.md",
        "created_at": "2026-05-07T00:00:00+08:00",
    }
    review = {
        "id": "review_desktop_workspaces",
        "source_title": "PromptAgent desktop workspaces",
        "source_page": "wiki/sources/desktop-workspaces.md",
        "summary": "桌面端由提示词实验室、知识系统和设置三个主要工作区组成。",
        "claims": [claim],
        "nodes": [{"id": "promptagent_desktop", "type": "ProductArea", "name": "PromptAgent Desktop", "aliases": ["Desktop"], "source": "wiki/sources/desktop-workspaces.md"}],
        "edges": [],
        "evidence": [{"source_page": "wiki/sources/desktop-workspaces.md", "quote": "三个主要工作区"}],
        "status": "pending",
        "created_at": "2026-05-07T00:00:00+08:00",
    }
    (root / "claims" / "claims.jsonl").write_text(json.dumps(claim, ensure_ascii=False) + "\n", encoding="utf-8")
    (root / "graph" / "review_queue.jsonl").write_text(json.dumps(review, ensure_ascii=False) + "\n", encoding="utf-8")
    (root / "graph" / "nodes.jsonl").write_text(
        json.dumps({"id": "prompt_lab", "type": "Workspace", "name": "提示词实验室", "aliases": ["Prompt Lab"], "source": "wiki/sources/desktop-workspaces.md"}, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    (root / "graph" / "edges.jsonl").write_text("", encoding="utf-8")
    (root / "log.md").write_text("# Knowledge OS Log\n\n- init\n", encoding="utf-8")

    main.settings_service.path = base / "settings.json"
    main.knowledge_os.root_path = root
    main.knowledge_os.personal_wiki.root_path = root
    main.prompt_agent.knowledge_os_service = main.knowledge_os
    main.prompt_agent.settings_service = main.settings_service
    main.prompt_agent.personal_wiki_service.root_path = root
    main.prompt_lab.settings_service = main.settings_service
    yield
    shutil.rmtree(base, ignore_errors=True)
