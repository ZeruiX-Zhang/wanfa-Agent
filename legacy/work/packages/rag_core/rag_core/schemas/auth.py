from __future__ import annotations

from pydantic import BaseModel, Field

from rag_core.rag.service import RequestContext


class AuthContext(BaseModel):
    user_id: str = Field(default="anonymous", description="Caller user id.")
    tenant_id: str = Field(default="default", description="Tenant id.")
    roles: list[str] = Field(default_factory=lambda: ["reader"], description="Caller roles.")

    def to_rag_context(self) -> RequestContext:
        return RequestContext(user_id=self.user_id, tenant_id=self.tenant_id, roles=self.roles)
