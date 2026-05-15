from __future__ import annotations

import re
from typing import Any


EMAIL_RE = re.compile(r"(?i)\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b")
PHONE_RE = re.compile(r"(?<!\d)(?:\+?\d[\d\-\s]{8,}\d)(?!\d)")
ID_CARD_RE = re.compile(r"(?<!\d)(?:\d{15}|\d{17}[\dXx])(?!\d)")


def mask_text(text: str) -> str:
    masked = EMAIL_RE.sub(lambda m: _mask_email(m.group(0)), text)
    masked = PHONE_RE.sub(lambda m: _mask_phone_match(m.group(0)), masked)
    masked = ID_CARD_RE.sub(lambda m: _mask_middle(m.group(0), keep=4), masked)
    return masked


def mask_pii(value: Any) -> Any:
    if isinstance(value, str):
        return mask_text(value)
    if isinstance(value, list):
        return [mask_pii(item) for item in value]
    if isinstance(value, tuple):
        return tuple(mask_pii(item) for item in value)
    if isinstance(value, dict):
        return {key: mask_pii(item) for key, item in value.items()}
    return value


def _mask_email(value: str) -> str:
    name, _, domain = value.partition("@")
    if len(name) <= 2:
        return "***@" + domain
    return name[:2] + "***@" + domain


def _mask_middle(value: str, keep: int) -> str:
    compact = value.strip()
    if len(compact) <= keep * 2:
        return "***"
    return compact[:keep] + "***" + compact[-keep:]


def _mask_phone_match(value: str) -> str:
    digits = re.sub(r"\D", "", value)
    if len(digits) < 10:
        return value
    return _mask_middle(value, keep=3)
