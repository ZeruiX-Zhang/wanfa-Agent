from __future__ import annotations

import re

import sqlparse
from sqlparse.sql import TokenList
from sqlparse.tokens import DDL, DML, Keyword

from analyst_core.schemas.data_agent import SQLValidationResult


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
    return LINE_COMMENT_RE.sub(" ", BLOCK_COMMENT_RE.sub(" ", sql))


def _normalize_sql(sql: str) -> str:
    return re.sub(r"\s+", " ", sql).strip()


class SQLSafetyChecker:
    def __init__(self, max_result_rows: int = 100):
        self.max_result_rows = max_result_rows

    def validate(self, sql: str) -> SQLValidationResult:
        original_sql = sql
        cleaned = _normalize_sql(_strip_comments(sql))
        reasons: list[str] = []
        blocked_keywords: list[str] = []

        if not cleaned:
            return SQLValidationResult(
                is_valid=False,
                original_sql=original_sql,
                sanitized_sql=None,
                reasons=["SQL validation failed: empty SQL."],
                blocked_keywords=[],
                enforced_limit=None,
                max_result_rows=self.max_result_rows,
            )

        semicolon_count = cleaned.count(";")
        parsed_statements = [statement for statement in sqlparse.parse(cleaned) if str(statement).strip()]
        if len(parsed_statements) != 1:
            reasons.append("SQL validation failed: multiple statements are not allowed.")
        cleaned = cleaned[:-1].strip() if cleaned.endswith(";") else cleaned

        statement = parsed_statements[0] if parsed_statements else None
        statement_type = statement.get_type().upper() if statement is not None else "UNKNOWN"
        if statement_type != "SELECT" or not cleaned.lower().startswith("select "):
            reasons.append("SQL validation failed: only SELECT statements are allowed.")

        upper_sql = cleaned.upper()
        for keyword in BANNED_KEYWORDS:
            if re.search(rf"\b{keyword}\b", upper_sql):
                blocked_keywords.append(keyword)
        if statement is not None:
            for token in _flatten_tokens(statement):
                if token.ttype in {DDL, DML, Keyword} and str(token).upper() in BANNED_KEYWORDS:
                    blocked_keywords.append(str(token).upper())
        if blocked_keywords:
            reasons.append("SQL validation failed: dangerous SQL keywords detected.")

        if re.search(r"\bsqlite_(master|schema|temp_master|sequence)\b", cleaned, re.IGNORECASE):
            reasons.append("SQL validation failed: SQLite system tables are blocked.")
            blocked_keywords.append("sqlite_system_table")

        for pattern in LOCAL_FILE_PATTERNS:
            if re.search(pattern, cleaned, re.IGNORECASE):
                reasons.append("SQL validation failed: local files, extensions, or secrets are blocked.")
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

        sanitized_sql = f"SELECT * FROM ({cleaned}) AS safe_query LIMIT {self.max_result_rows}"
        return SQLValidationResult(
            is_valid=True,
            original_sql=original_sql,
            sanitized_sql=sanitized_sql,
            reasons=["SQL validation passed."],
            blocked_keywords=[],
            enforced_limit=self.max_result_rows,
            max_result_rows=self.max_result_rows,
        )


def _flatten_tokens(token_list: TokenList):
    for token in token_list.tokens:
        if isinstance(token, TokenList):
            yield from _flatten_tokens(token)
        else:
            yield token
