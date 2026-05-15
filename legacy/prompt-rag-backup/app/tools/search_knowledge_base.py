from __future__ import annotations

from pydantic import BaseModel, Field

from app.agent.tool_schema import BaseTool, ToolResult
from app.rag.retriever import Retriever
from app.router.domain_router import DomainRouter
from app.schemas.domain import DomainRequestValue


class SearchKnowledgeBaseArgs(BaseModel):
    query: str = Field(min_length=1)
    domain: DomainRequestValue = "auto"
    top_k: int = Field(default=5, ge=1, le=20)


class SearchKnowledgeBaseTool(BaseTool):
    name = "search_knowledge_base"
    description = "Search the FAISS-backed enterprise knowledge base."
    args_schema = SearchKnowledgeBaseArgs

    def __init__(self, retriever: Retriever | None = None, domain_router: DomainRouter | None = None) -> None:
        self.retriever = retriever or Retriever()
        self.domain_router = domain_router or DomainRouter()

    def run(self, args: SearchKnowledgeBaseArgs, trace_id: str) -> ToolResult:
        route = self.domain_router.route(args.query, requested_domain=args.domain)
        chunks = self.retriever.retrieve(args.query, top_k=args.top_k, domain=route.domain)
        return ToolResult(
            success=True,
            tool_name=self.name,
            output={
                "selected_domain": route.domain,
                "router_confidence": route.confidence,
                "router_reason": route.reason,
                "results": [
                    {
                        "chunk_id": chunk.chunk_id,
                        "text": chunk.text,
                        "metadata": chunk.metadata.model_dump(),
                        "score": chunk.score,
                    }
                    for chunk in chunks
                ]
            },
        )
