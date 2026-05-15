from __future__ import annotations

import json
import re
from typing import Any


EXTRACT_PROMPT = """\
You are a knowledge extraction engine. Given the text below, extract structured knowledge.
Respond with valid JSON only — no markdown fences, no explanation.

JSON schema:
{
  "title": "<short descriptive title, max 80 chars>",
  "summary": "<2-3 sentence summary>",
  "claims": [
    {"text": "<factual assertion>", "confidence": 0.0-1.0}
  ],
  "nodes": [
    {"type": "<concept type e.g. Concept/Person/Tool/Method>", "name": "<name>", "aliases": []}
  ],
  "edges": [
    {"from": "<node name>", "type": "<relation e.g. uses/extends/contradicts>", "to": "<node name>", "confidence": 0.0-1.0}
  ]
}

Extract 1-5 claims, 1-6 nodes, and 0-4 edges that are clearly supported by the text.
Omit arrays if empty.

TEXT:
"""


def extract_knowledge(text: str, provider: Any) -> dict[str, Any]:
    messages = [
        {"role": "user", "content": EXTRACT_PROMPT + text[:3000]},
    ]
    try:
        raw = provider.generate(messages, {"temperature": 0.1, "max_tokens": 800, "timeout": 30})
        return _parse_response(raw)
    except Exception:  # noqa: BLE001
        return _rule_based_fallback(text)


def _parse_response(raw: str) -> dict[str, Any]:
    # Strip markdown code fences if present
    cleaned = re.sub(r"^```(?:json)?\s*", "", raw.strip(), flags=re.MULTILINE)
    cleaned = re.sub(r"\s*```$", "", cleaned.strip(), flags=re.MULTILINE)
    try:
        data = json.loads(cleaned)
    except json.JSONDecodeError:
        # Try to find JSON object in the response
        match = re.search(r"\{.*\}", cleaned, re.DOTALL)
        if not match:
            return _rule_based_fallback(raw)
        try:
            data = json.loads(match.group(0))
        except json.JSONDecodeError:
            return _rule_based_fallback(raw)

    if not isinstance(data, dict):
        return _rule_based_fallback(raw)

    result: dict[str, Any] = {}
    if isinstance(data.get("title"), str):
        result["title"] = data["title"].strip()[:80]
    if isinstance(data.get("summary"), str):
        result["summary"] = data["summary"].strip()
    if isinstance(data.get("claims"), list):
        result["claims"] = [
            {
                "text": str(c.get("text", "")).strip(),
                "confidence": float(c.get("confidence", 0.7)),
            }
            for c in data["claims"]
            if isinstance(c, dict) and c.get("text")
        ][:5]
    if isinstance(data.get("nodes"), list):
        result["nodes"] = [
            {
                "type": str(n.get("type", "Concept")).strip(),
                "name": str(n.get("name", "")).strip(),
                "aliases": [str(a) for a in (n.get("aliases") or []) if a],
            }
            for n in data["nodes"]
            if isinstance(n, dict) and n.get("name")
        ][:6]
    if isinstance(data.get("edges"), list):
        result["edges"] = [
            {
                "from": str(e.get("from", "")).strip(),
                "type": str(e.get("type", "related_to")).strip(),
                "to": str(e.get("to", "")).strip(),
                "confidence": float(e.get("confidence", 0.6)),
            }
            for e in data["edges"]
            if isinstance(e, dict) and e.get("from") and e.get("to")
        ][:4]
    return result


def _rule_based_fallback(text: str) -> dict[str, Any]:
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    title = lines[0][:80] if lines else "Level Up Source"
    sentences = re.split(r"(?<=[。.!?！？])\s*", text.strip())
    first_sent = sentences[0].strip()[:260] if sentences else ""
    return {
        "title": title,
        "summary": " ".join(sentences[:2]).strip()[:420],
        "claims": [{"text": first_sent, "confidence": 0.5}] if first_sent else [],
        "nodes": [],
        "edges": [],
    }
