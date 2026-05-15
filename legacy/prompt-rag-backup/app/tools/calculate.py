from __future__ import annotations

import ast
import operator
from typing import Callable

from pydantic import BaseModel, Field

from app.agent.tool_schema import BaseTool, ToolResult
from app.core.errors import AppError


class CalculateArgs(BaseModel):
    expression: str = Field(min_length=1, max_length=200)


class CalculateTool(BaseTool):
    name = "calculate"
    description = "Safely calculate numeric expressions using a restricted AST evaluator."
    args_schema = CalculateArgs

    _binary_ops: dict[type[ast.operator], Callable[[float, float], float]] = {
        ast.Add: operator.add,
        ast.Sub: operator.sub,
        ast.Mult: operator.mul,
        ast.Div: operator.truediv,
        ast.FloorDiv: operator.floordiv,
        ast.Mod: operator.mod,
        ast.Pow: operator.pow,
    }
    _unary_ops: dict[type[ast.unaryop], Callable[[float], float]] = {
        ast.UAdd: operator.pos,
        ast.USub: operator.neg,
    }

    def run(self, args: CalculateArgs, trace_id: str) -> ToolResult:
        result = self._evaluate(args.expression)
        return ToolResult(success=True, tool_name=self.name, output={"expression": args.expression, "result": result})

    def _evaluate(self, expression: str) -> float:
        try:
            tree = ast.parse(expression, mode="eval")
        except SyntaxError as exc:
            raise AppError("Invalid math expression", status_code=400, code="invalid_expression") from exc
        return float(self._eval_node(tree.body))

    def _eval_node(self, node: ast.AST) -> float:
        if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
            return float(node.value)
        if isinstance(node, ast.BinOp) and type(node.op) in self._binary_ops:
            left = self._eval_node(node.left)
            right = self._eval_node(node.right)
            if isinstance(node.op, ast.Pow) and abs(right) > 10:
                raise AppError("Exponent is too large", status_code=400, code="unsafe_expression")
            return self._binary_ops[type(node.op)](left, right)
        if isinstance(node, ast.UnaryOp) and type(node.op) in self._unary_ops:
            return self._unary_ops[type(node.op)](self._eval_node(node.operand))
        raise AppError("Expression contains unsupported syntax", status_code=400, code="unsafe_expression")
