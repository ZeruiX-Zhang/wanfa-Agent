from __future__ import annotations

import re

SECRET_PATTERNS = [
    re.compile(r"(?i)(OPENAI_API_KEY|DEMO_API_KEY|JWT_SECRET|API_KEY)\s*=\s*[^\s]+"),
    re.compile(r"sk-[A-Za-z0-9_\-]{8,}"),
    re.compile(r"(?i)(password|secret|token)\s*[:=]\s*[^\s]+"),
]

FORBIDDEN_PATH_PATTERNS = [
    re.compile(r"(?i)(^|[\\/])\.env(\b|$)"),
    re.compile(r"(?i)[A-Z]:\\[^\s]*\.env\b"),
]


def sanitize_output(text: str) -> str:
    sanitized = text
    for pattern in SECRET_PATTERNS:
        sanitized = pattern.sub("[REDACTED_SECRET]", sanitized)
    for pattern in FORBIDDEN_PATH_PATTERNS:
        sanitized = pattern.sub("[REDACTED_FORBIDDEN_PATH]", sanitized)
    return sanitized


def contains_secret(text: str) -> bool:
    return any(pattern.search(text) for pattern in SECRET_PATTERNS)


def contains_forbidden_path(text: str) -> bool:
    return any(pattern.search(text) for pattern in FORBIDDEN_PATH_PATTERNS)

