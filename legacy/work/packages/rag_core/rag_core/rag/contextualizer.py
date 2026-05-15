from __future__ import annotations

from rag_core.rag.models import Chunk
from rag_core.rag.settings import env_int, env_str


class Contextualizer:
    def contextualize(self, chunk: Chunk) -> str:
        raise NotImplementedError


class TemplateContextualizer(Contextualizer):
    def contextualize(self, chunk: Chunk) -> str:
        max_tokens = env_int("CONTEXTUALIZER_MAX_TOKENS", 200)
        template = (
            f"Domain: {chunk.domain}. "
            f"Document: {chunk.filename}. "
            f"Section: {chunk.section_path or 'root'}. "
            f"Page: {chunk.page}. "
            f"Text: {chunk.text}"
        )
        return " ".join(template.split()[:max_tokens])


class LLMContextualizer(Contextualizer):
    def __init__(self) -> None:
        self._fallback = TemplateContextualizer()

    def contextualize(self, chunk: Chunk) -> str:
        return self._fallback.contextualize(chunk)


def build_contextualizer() -> Contextualizer:
    provider = env_str("CONTEXTUALIZER_PROVIDER", "template")
    if provider == "llm":
        return LLMContextualizer()
    return TemplateContextualizer()
