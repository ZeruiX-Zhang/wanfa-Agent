from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]


@dataclass(frozen=True)
class AppSettings:
    app_name: str = "PromptAgent"
    host: str = os.getenv("PROMPT_AGENT_HOST", "127.0.0.1")
    port: int = int(os.getenv("PROMPT_AGENT_PORT", "8787"))
    settings_path: Path = PROJECT_ROOT / "storage" / "settings.json"
    knowledge_os_path: Path = PROJECT_ROOT / "knowledge_os"


settings = AppSettings()

