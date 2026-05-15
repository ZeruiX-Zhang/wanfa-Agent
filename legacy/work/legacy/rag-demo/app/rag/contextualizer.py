from __future__ import annotations

from app.rag.models import Chunk
from app.rag.settings import env_int, env_str


class Contextualizer:
    def contextualize(self, chunk: Chunk) -> str:
        raise NotImplementedError


class TemplateContextualizer(Contextualizer):
    def contextualize(self, chunk: Chunk) -> str:
        max_tokens = env_int("CONTEXTUALIZER_MAX_TOKENS", 200)
        template = (
            f"本片段来自 {chunk.domain} 业务域的 {chunk.filename} 文档，"
            f"章节路径为 {chunk.section_path or 'root'}，页码为 {chunk.page}。"
            f"原文片段：{chunk.text}"
        )
        return " ".join(template.split()[:max_tokens])


class LLMContextualizer(Contextualizer):
    def __init__(self) -> None:
        self._fallback = TemplateContextualizer()

    def contextualize(self, chunk: Chunk) -> str:
        # External LLM contextualization is intentionally behind the LLM client
        # contract added later. Until configured, use deterministic fallback.
        return self._fallback.contextualize(chunk)


def build_contextualizer() -> Contextualizer:
    provider = env_str("CONTEXTUALIZER_PROVIDER", "template")
    if provider == "llm":
        return LLMContextualizer()
    return TemplateContextualizer()

