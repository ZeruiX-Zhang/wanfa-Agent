from __future__ import annotations

from abc import ABC, abstractmethod
from typing import ClassVar

from pydantic import BaseModel


class ToolResult(BaseModel):
    success: bool
    tool_name: str
    output: dict[str, object]
    error: str | None = None


class BaseTool(ABC):
    name: ClassVar[str]
    description: ClassVar[str]
    args_schema: ClassVar[type[BaseModel]]

    @abstractmethod
    def run(self, args: BaseModel, trace_id: str) -> ToolResult:
        raise NotImplementedError
