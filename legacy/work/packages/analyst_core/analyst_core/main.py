from __future__ import annotations

from fastapi import FastAPI

from analyst_core.api.routes import data_agent_router, public_router


def create_app() -> FastAPI:
    app = FastAPI(
        title="Analyst Core Compatibility API",
        description="Deprecated package-local analyst entrypoint kept as a compatibility shim.",
        version="compat",
    )
    app.include_router(public_router)
    app.include_router(data_agent_router)
    return app


app = create_app()
