from __future__ import annotations

from fastapi import FastAPI

from rag_core.api.routes import public_router, rag_router


def create_app() -> FastAPI:
    app = FastAPI(
        title="RAG Core Compatibility API",
        description="Deprecated package-local RAG entrypoint kept as a compatibility shim.",
        version="compat",
    )
    app.include_router(public_router)
    app.include_router(rag_router)
    return app


app = create_app()
