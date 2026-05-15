from __future__ import annotations

from fastapi import FastAPI

from workflow_core.api.routes import agent_router, public_router


def create_app() -> FastAPI:
    app = FastAPI(
        title="Workflow Core Compatibility API",
        description="Deprecated package-local workflow entrypoint kept as a compatibility shim.",
        version="compat",
    )
    app.include_router(public_router)
    app.include_router(agent_router)
    return app


app = create_app()
