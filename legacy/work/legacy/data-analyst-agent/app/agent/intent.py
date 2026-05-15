from __future__ import annotations

import re


DANGEROUS_SQL_RE = re.compile(
    r"\b(drop|delete|update|insert|alter|create|replace|attach|detach|pragma|vacuum|truncate)\b",
    re.IGNORECASE,
)

SENSITIVE_FILE_RE = re.compile(
    r"(\.env|api\s*key|apikey|token|password|secret|密钥|读取.*文件|本地文件)",
    re.IGNORECASE,
)


def detect_blocked_request(question: str) -> tuple[bool, str, list[str]]:
    if DANGEROUS_SQL_RE.search(question):
        return True, "SQL validation failed: 用户请求执行破坏性或非只读 SQL。", [DANGEROUS_SQL_RE.search(question).group(1).upper()]
    if SENSITIVE_FILE_RE.search(question):
        return True, "SQL validation failed: 用户请求读取本地文件或敏感密钥，已拒绝。", ["sensitive_file"]
    return False, "", []
