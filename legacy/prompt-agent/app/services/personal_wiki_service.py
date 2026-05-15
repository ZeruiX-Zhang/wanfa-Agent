from __future__ import annotations

import os
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from app.core.config import settings
from app.models.schemas import PersonalWikiFileContent, PersonalWikiFileItem


PERSONAL_FILES: dict[str, str] = {
    "profile": "profile.md",
    "preferences": "preferences.md",
    "goals": "goals.md",
    "current_projects": "current_projects.md",
    "writing_style": "writing_style.md",
    "learning_style": "learning_style.md",
    "decision_history": "decision_history.md",
}


@dataclass
class PersonalContextItem:
    id: str
    filename: str
    title: str
    summary: str


class PersonalWikiService:
    def __init__(self, root_path: Path | None = None) -> None:
        self.root_path = root_path or settings.knowledge_os_path

    @property
    def personal_path(self) -> Path:
        return self.root_path / "wiki" / "personal"

    def ensure_structure(self) -> None:
        self.personal_path.mkdir(parents=True, exist_ok=True)
        defaults = {
            "profile": "# 个人资料\n\n这里记录长期稳定的身份、角色和背景摘要。\n",
            "preferences": "# 偏好\n\n- 输出偏好：结构清晰、具体、可执行。\n",
            "goals": "# 目标\n\n记录长期目标和阶段性目标。\n",
            "current_projects": "# 当前项目\n\n- PromptAgent：桌面端右键 AI 操作层。\n",
            "writing_style": "# 写作风格\n\n偏好直接、实用、少空话。\n",
            "learning_style": "# 学习风格\n\n偏好用例驱动、逐步拆解、可验证反馈。\n",
            "decision_history": "# 决策记录\n\n记录重要产品和技术决策。\n",
        }
        for file_id, filename in PERSONAL_FILES.items():
            path = self.personal_path / filename
            if not path.exists():
                path.write_text(defaults[file_id], encoding="utf-8")

    def list_files(self) -> list[PersonalWikiFileItem]:
        self.ensure_structure()
        return [self._item(file_id, self.personal_path / filename) for file_id, filename in PERSONAL_FILES.items()]

    def read_file(self, file_id: str) -> PersonalWikiFileContent:
        path = self._safe_file(file_id)
        item = self._item(file_id, path)
        return PersonalWikiFileContent(**item.model_dump(), content=path.read_text(encoding="utf-8"))

    def update_file(self, file_id: str, content: str) -> PersonalWikiFileContent:
        path = self._safe_file(file_id)
        path.write_text(content.rstrip() + "\n", encoding="utf-8")
        return self.read_file(file_id)

    def retrieve_context(self, query: str, limit: int = 5) -> list[PersonalContextItem]:
        self.ensure_structure()
        terms = {part.lower() for part in query.split() if len(part) >= 2}
        scored: list[tuple[int, PersonalContextItem]] = []
        for item in self.list_files():
            content = self.read_file(item.id).content
            haystack = f"{item.title} {content}".lower()
            score = sum(1 for term in terms if term in haystack)
            if score or item.id in {"preferences", "current_projects", "writing_style"}:
                scored.append((score, PersonalContextItem(item.id, item.filename, item.title, _summarize(content, 240))))
        scored.sort(key=lambda pair: pair[0], reverse=True)
        return [item for _, item in scored[:limit]]

    def summary_test(self, enabled: bool) -> dict[str, object]:
        items = self.retrieve_context("preferences goals current projects writing style") if enabled else []
        summary = "\n".join(f"- {item.title}: {item.summary}" for item in items) or "个性化关闭或没有可用摘要。"
        return {
            "enabled": enabled,
            "summary": summary,
            "used_files": [
                PersonalWikiFileItem(id=item.id, filename=item.filename, title=item.title).model_dump()
                for item in items
            ],
        }

    def open_folder(self) -> tuple[bool, str, Path]:
        self.ensure_structure()
        path = self.personal_path.resolve()
        opened, message = open_allowed_path(path, self.root_path)
        return opened, message, path

    def _safe_file(self, file_id: str) -> Path:
        self.ensure_structure()
        if file_id not in PERSONAL_FILES:
            raise ValueError("Invalid personal file id.")
        path = (self.personal_path / PERSONAL_FILES[file_id]).resolve()
        _assert_inside(path, self.root_path)
        return path

    def _item(self, file_id: str, path: Path) -> PersonalWikiFileItem:
        content = path.read_text(encoding="utf-8") if path.exists() else ""
        title = _first_heading(content) or path.stem.replace("_", " ").title()
        updated_at = datetime.fromtimestamp(path.stat().st_mtime).astimezone().isoformat(timespec="seconds")
        return PersonalWikiFileItem(id=file_id, filename=path.name, title=title, updated_at=updated_at)


def open_allowed_path(path: Path, root: Path) -> tuple[bool, str]:
    _assert_inside(path.resolve(), root.resolve())
    try:
        if os.name == "nt":
            os.startfile(str(path))  # type: ignore[attr-defined]
        elif sys.platform == "darwin":
            subprocess.Popen(["open", str(path)])
        else:
            subprocess.Popen(["xdg-open", str(path)])
    except Exception as exc:  # noqa: BLE001
        return False, f"无法自动打开，请手动打开：{path}。错误：{exc}"
    return True, "已尝试打开。"


def _assert_inside(path: Path, root: Path) -> None:
    resolved = path.resolve()
    root_resolved = root.resolve()
    if resolved != root_resolved and root_resolved not in resolved.parents:
        raise ValueError("Path escapes Knowledge OS root.")


def _first_heading(markdown: str) -> str:
    for line in markdown.splitlines():
        if line.strip().startswith("# "):
            return line.strip()[2:].strip()
    return ""


def _summarize(text: str, limit: int) -> str:
    cleaned = " ".join(line.strip() for line in text.splitlines() if line.strip() and not line.startswith("#"))
    return cleaned[:limit].rstrip() + ("..." if len(cleaned) > limit else "")

