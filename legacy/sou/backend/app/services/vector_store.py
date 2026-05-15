from __future__ import annotations

import math
from collections import Counter
from dataclasses import dataclass


class VectorStore:
    def upsert(self, vector_id: str, text: str, metadata: dict) -> None:
        raise NotImplementedError

    def search(self, text: str, limit: int = 5) -> list[tuple[str, float, dict]]:
        raise NotImplementedError


def _embed(text: str) -> Counter:
    tokens = [token.lower() for token in text.split() if len(token) > 2]
    return Counter(tokens)


def _cosine(a: Counter, b: Counter) -> float:
    common = set(a) & set(b)
    numerator = sum(a[k] * b[k] for k in common)
    denom = math.sqrt(sum(v * v for v in a.values())) * math.sqrt(sum(v * v for v in b.values()))
    return 0.0 if denom == 0 else numerator / denom


@dataclass
class MemoryVectorStore(VectorStore):
    rows: dict[str, tuple[Counter, dict]]

    def __init__(self) -> None:
        self.rows = {}

    def upsert(self, vector_id: str, text: str, metadata: dict) -> None:
        self.rows[vector_id] = (_embed(text), metadata)

    def search(self, text: str, limit: int = 5) -> list[tuple[str, float, dict]]:
        query = _embed(text)
        scored = [
            (vector_id, _cosine(query, vector), metadata)
            for vector_id, (vector, metadata) in self.rows.items()
        ]
        return sorted(scored, key=lambda row: row[1], reverse=True)[:limit]
