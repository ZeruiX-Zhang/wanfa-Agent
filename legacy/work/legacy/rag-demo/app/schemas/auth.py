from __future__ import annotations

from pydantic import BaseModel, Field

from app.rag.service import RequestContext


class AuthContext(BaseModel):
    user_id: str = Field(default="anonymous", description="调用方用户 ID，用于审计和 trace。")
    tenant_id: str = Field(default="default", description="租户 ID，用于多租户知识库隔离。")
    roles: list[str] = Field(default_factory=lambda: ["reader"], description="调用方角色列表，用于 access_roles 权限过滤。")

    def to_rag_context(self) -> RequestContext:
        return RequestContext(user_id=self.user_id, tenant_id=self.tenant_id, roles=self.roles)
