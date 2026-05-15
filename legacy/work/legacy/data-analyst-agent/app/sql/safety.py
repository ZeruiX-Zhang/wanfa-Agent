from __future__ import annotations

import re

from app.schemas.data_agent import SQLValidationResult


BANNED_KEYWORDS = [
    "DROP",
    "DELETE",
    "UPDATE",
    "INSERT",
    "ALTER",
    "CREATE",
    "REPLACE",
    "ATTACH",
    "DETACH",
    "PRAGMA",
    "VACUUM",
    "TRUNCATE",
]

LOCAL_FILE_PATTERNS = [
    r"\breadfile\s*\(",
    r"\bload_extension\s*\(",
    r"\bfile\s*:",
    r"\.env\b",
    r"\bapi[_ -]?key\b",
    r"\btoken\b",
    r"\bpassword\b",
    r"\bsecret\b",
]

LINE_COMMENT_RE = re.compile(r"--.*?$", re.MULTILINE)
BLOCK_COMMENT_RE = re.compile(r"/\*.*?\*/", re.DOTALL)


def _strip_comments(sql: str) -> str:
    without_block = BLOCK_COMMENT_RE.sub(" ", sql)
    return LINE_COMMENT_RE.sub(" ", without_block)


def _normalize_sql(sql: str) -> str:
    return re.sub(r"\s+", " ", sql).strip()


class SQLSafetyChecker:
    def __init__(self, max_result_rows: int = 100):
        self.max_result_rows = max_result_rows

    def validate(self, sql: str) -> SQLValidationResult:
        original_sql = sql
        reasons: list[str] = []
        blocked_keywords: list[str] = []
        cleaned = _normalize_sql(_strip_comments(sql))

        if not cleaned:
            return SQLValidationResult(
                is_valid=False,
                original_sql=original_sql,
                sanitized_sql=None,
                reasons=["SQL validation failed: SQL 为空。"],
                blocked_keywords=[],
                enforced_limit=None,
                max_result_rows=self.max_result_rows,
            )

        semicolon_count = cleaned.count(";")
        if semicolon_count > 1 or (semicolon_count == 1 and not cleaned.endswith(";")):
            reasons.append("SQL validation failed: 禁止多语句执行。")
        cleaned = cleaned[:-1].strip() if cleaned.endswith(";") else cleaned

        if not cleaned.lower().startswith("select "):
            reasons.append("SQL validation failed: 只允许 SELECT 查询。")

        upper_sql = cleaned.upper()
        for keyword in BANNED_KEYWORDS:
            if re.search(rf"\b{keyword}\b", upper_sql):
                blocked_keywords.append(keyword)
        if blocked_keywords:
            reasons.append("SQL validation failed: 命中危险 SQL 关键字。")

        if re.search(r"\bsqlite_(master|schema|temp_master|sequence)\b", cleaned, re.IGNORECASE):
            reasons.append("SQL validation failed: 禁止访问 SQLite 系统表。")
            blocked_keywords.append("sqlite_system_table")

        for pattern in LOCAL_FILE_PATTERNS:
            if re.search(pattern, cleaned, re.IGNORECASE):
                reasons.append("SQL validation failed: 禁止读取本地文件、扩展或敏感密钥。")
                blocked_keywords.append(pattern)

        if reasons:
            return SQLValidationResult(
                is_valid=False,
                original_sql=original_sql,
                sanitized_sql=None,
                reasons=list(dict.fromkeys(reasons)),
                blocked_keywords=list(dict.fromkeys(blocked_keywords)),
                enforced_limit=None,
                max_result_rows=self.max_result_rows,
            )

        sanitized_sql = self._force_limit(cleaned)
        return SQLValidationResult(
            is_valid=True,
            original_sql=original_sql,
            sanitized_sql=sanitized_sql,
            reasons=["SQL validation passed: 仅执行只读 SELECT，并强制 LIMIT。"],
            blocked_keywords=[],
            enforced_limit=self.max_result_rows,
            max_result_rows=self.max_result_rows,
        )

    def _force_limit(self, sql: str) -> str:
        return f"SELECT * FROM ({sql}) AS safe_query LIMIT {self.max_result_rows}"

