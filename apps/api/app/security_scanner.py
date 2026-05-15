"""Deterministic scanners for prompt, RAG, tool, and rule injection.

This layer is intentionally conservative and dependency-free. It does not
decide final policy by itself; it produces structured flags that callers use
to keep retrieved content as evidence rather than instructions.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Literal


Severity = Literal["low", "medium", "high", "critical"]


@dataclass(frozen=True)
class SecurityFinding:
    category: str
    severity: Severity
    pattern_id: str
    description: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "category": self.category,
            "severity": self.severity,
            "pattern_id": self.pattern_id,
            "description": self.description,
        }


_PATTERNS: list[tuple[str, str, Severity, re.Pattern[str], str]] = [
    (
        "prompt_injection",
        "ignore_previous_instructions",
        "high",
        re.compile(
            r"ignore\s+(all\s+)?(previous|prior|above)\s+instructions|"
            r"忽略.{0,8}(之前|以上|前面|所有).{0,8}(指令|规则|要求)",
            re.I,
        ),
        "Content attempts to override prior instructions.",
    ),
    (
        "prompt_injection",
        "reveal_system_prompt",
        "critical",
        re.compile(
            r"(reveal|print|show|dump|expose).{0,30}(system\s+prompt|developer\s+message)|"
            r"(泄露|显示|打印|导出|暴露).{0,12}(系统提示词|系统提示|开发者消息)",
            re.I,
        ),
        "Content requests hidden prompt or system message disclosure.",
    ),
    (
        "tool_injection",
        "call_tool",
        "high",
        re.compile(
            r"(call|invoke|run|execute|use)\s+(this\s+)?(tool|function|command)|"
            r"(调用|执行|运行|使用).{0,8}(工具|函数|命令)",
            re.I,
        ),
        "Content tries to direct tool execution.",
    ),
    (
        "tool_injection",
        "delete_database",
        "critical",
        re.compile(
            r"(delete|drop|wipe|truncate).{0,20}(database|db|table|sqlite)|"
            r"(删除|清空|销毁|丢弃).{0,12}(数据库|数据表|表)",
            re.I,
        ),
        "Content requests destructive data operations.",
    ),
    (
        "secret_exfiltration",
        "export_api_key",
        "critical",
        re.compile(
            r"(export|send|print|reveal|exfiltrate).{0,30}(api[_\s-]?key|token|secret|password)|"
            r"(导出|发送|打印|泄露|窃取).{0,12}(密钥|API\s*Key|令牌|密码|secret)",
            re.I,
        ),
        "Content requests secret exfiltration.",
    ),
    (
        "safety_bypass",
        "disable_safety",
        "critical",
        re.compile(
            r"(disable|turn\s+off|bypass).{0,30}(safety|guardrail|policy|supervisor)|"
            r"(关闭|禁用|绕过).{0,12}(安全|规则|策略|监督|Supervisor)",
            re.I,
        ),
        "Content attempts to disable safety controls or supervisor checks.",
    ),
]


def scan_text(text: str | None, *, source: str = "unknown") -> list[SecurityFinding]:
    if not text:
        return []
    findings: list[SecurityFinding] = []
    for category, pattern_id, severity, regex, description in _PATTERNS:
        if regex.search(text):
            findings.append(
                SecurityFinding(
                    category=category,
                    severity=severity,
                    pattern_id=pattern_id,
                    description=f"{description} Source={source}.",
                )
            )
    return findings


def flags_for_text(text: str | None, *, source: str = "unknown") -> list[str]:
    return [finding.pattern_id for finding in scan_text(text, source=source)]


def findings_to_dicts(findings: list[SecurityFinding]) -> list[dict[str, Any]]:
    return [finding.to_dict() for finding in findings]


def has_blocking_finding(findings: list[SecurityFinding]) -> bool:
    return any(finding.severity in {"high", "critical"} for finding in findings)


def evidence_warning(language: str = "en") -> str:
    if language == "zh-CN":
        return "检索内容包含类似指令或工具调用的文本，系统已将其隔离为证据而不是指令；请人工检查原始来源。"
    return (
        "Retrieved content contained instruction-like or tool-like text. "
        "It is isolated as evidence, not treated as an instruction; inspect the original source."
    )
