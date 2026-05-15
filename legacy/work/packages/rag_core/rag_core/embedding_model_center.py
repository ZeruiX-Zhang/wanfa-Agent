from __future__ import annotations

import csv
import io
import json
import math
import os
import statistics
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml

from rag_core.rag.embedding import cosine_similarity, embed_text
from rag_core.rag.models import Chunk


ROOT_DIR = Path(__file__).resolve().parents[3]
DEFAULT_MODELS_PATH = ROOT_DIR / "configs" / "embedding_models.yaml"
DEFAULT_EVAL_PATH = ROOT_DIR / "configs" / "embedding_eval.yaml"
DEFAULT_RETRIEVAL_EVAL_PATH = ROOT_DIR / "data" / "eval_sets" / "embedding_retrieval_eval.jsonl"
COLLECTION_METADATA_PATH = ROOT_DIR / "workspace" / "vector_store" / "collection_metadata.json"

VALID_PROVIDERS = {"openai", "local_bge", "local_qwen", "custom_api", "mock"}
VALID_DISTANCE_METRICS = {"cosine", "dot", "l2"}


@dataclass
class EmbeddingModelSpec:
    model_id: str
    display_name: str
    provider: str
    model: str = ""
    dimension: int | None = None
    max_input_tokens: int | None = None
    language_support: str = ""
    recommended_for: str = ""
    normalize_embeddings: bool = True
    distance_metric: str = "cosine"
    base_url: str = ""
    endpoint: str = "/embeddings"
    api_key_env: str = ""
    input_field: str = "input"
    model_field: str = "model"
    output_path: str = "data.0.embedding"
    batch_size: int = 64
    timeout_seconds: int = 30
    retry_count: int = 2
    description: str = ""
    status: str = "enabled"
    built_in: bool = False
    last_test_score: float | None = None
    last_test_at: str | None = None

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "EmbeddingModelSpec":
        payload = dict(data)
        if payload.get("dimension") in ("", "null"):
            payload["dimension"] = None
        if payload.get("max_input_tokens") in ("", "null"):
            payload["max_input_tokens"] = None
        return cls(**{key: payload.get(key) for key in cls.__dataclass_fields__ if key in payload})

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class CollectionMetadata:
    collection_name: str
    embedding_model_id: str
    provider: str
    dimension: int
    distance_metric: str
    normalize_embeddings: bool
    created_at: str
    chunk_count: int = 0
    doc_count: int = 0

    def compatibility_with(self, model: EmbeddingModelSpec) -> dict[str, Any]:
        issues: list[str] = []
        if self.embedding_model_id != model.model_id:
            issues.append("collection 绑定的 embedding_model_id 与候选模型不一致")
        if model.dimension is None or self.dimension != model.dimension:
            issues.append("向量维度不一致，禁止写入并需要重建索引")
        if self.distance_metric != model.distance_metric:
            issues.append("距离度量改变，需要重建索引")
        if self.normalize_embeddings != model.normalize_embeddings:
            issues.append("normalize_embeddings 设置不一致，存在检索分数风险")
        return {
            "compatible": not issues,
            "need_reindex": bool(issues),
            "can_write": not any("维度" in issue for issue in issues),
            "issues": issues,
        }


class ModelRegistry:
    def __init__(
        self,
        path: str | Path = DEFAULT_MODELS_PATH,
        collection_metadata_path: str | Path = COLLECTION_METADATA_PATH,
    ) -> None:
        self.path = Path(path)
        self.collection_metadata_path = Path(collection_metadata_path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if not self.path.exists():
            self.path.write_text(yaml.safe_dump(default_embedding_models_config(), allow_unicode=True, sort_keys=False), encoding="utf-8")

    def load(self) -> dict[str, Any]:
        return yaml.safe_load(self.path.read_text(encoding="utf-8")) or {"active_model_id": "", "models": {}}

    def save(self, config: dict[str, Any]) -> None:
        self.path.write_text(yaml.safe_dump(config, allow_unicode=True, sort_keys=False), encoding="utf-8")

    def list_models(self) -> list[EmbeddingModelSpec]:
        config = self.load()
        return [EmbeddingModelSpec.from_dict({"model_id": key, **value}) for key, value in (config.get("models") or {}).items()]

    def get(self, model_id: str) -> EmbeddingModelSpec:
        config = self.load()
        models = config.get("models") or {}
        if model_id not in models:
            raise KeyError(f"Unknown embedding model: {model_id}")
        return EmbeddingModelSpec.from_dict({"model_id": model_id, **models[model_id]})

    def active_model_id(self) -> str:
        return str(self.load().get("active_model_id") or "")

    def active_model(self) -> EmbeddingModelSpec:
        return self.get(self.active_model_id())

    def rows(self) -> list[dict[str, Any]]:
        active = self.active_model_id()
        metadata = self.load_collection_metadata()
        rows: list[dict[str, Any]] = []
        for model in self.list_models():
            compatibility = metadata.compatibility_with(model) if metadata else {"need_reindex": False}
            rows.append(
                {
                    **model.to_dict(),
                    "model_name": model.model,
                    "active": model.model_id == active,
                    "need_reindex": bool(compatibility.get("need_reindex")),
                }
            )
        return rows

    def validate_model(self, model: EmbeddingModelSpec) -> None:
        if not model.model_id.strip():
            raise ValueError("model_id 不能为空")
        if not model.display_name.strip():
            raise ValueError("display_name 不能为空")
        if model.provider not in VALID_PROVIDERS:
            raise ValueError("provider 只能是 openai / local_bge / local_qwen / custom_api / mock")
        if model.distance_metric not in VALID_DISTANCE_METRICS:
            raise ValueError("distance_metric 只能是 cosine / dot / l2")
        if model.provider != "custom_api" and not model.model.strip():
            raise ValueError("model 不能为空")
        if model.model_id != "custom_api_template":
            if model.dimension is None or int(model.dimension) <= 0:
                raise ValueError("dimension 必须为正整数")

    def upsert(self, model: EmbeddingModelSpec) -> None:
        self.validate_model(model)
        config = self.load()
        models = config.setdefault("models", {})
        existing = models.get(model.model_id, {})
        if existing.get("built_in") and not model.built_in:
            model.built_in = True
        models[model.model_id] = model.to_dict()
        self.save(config)

    def duplicate(self, model_id: str, new_model_id: str) -> EmbeddingModelSpec:
        model = self.get(model_id)
        model.model_id = new_model_id
        model.display_name = f"{model.display_name} Copy"
        model.built_in = False
        model.status = "enabled"
        self.upsert(model)
        return model

    def delete(self, model_id: str) -> None:
        config = self.load()
        model = (config.get("models") or {}).get(model_id)
        if not model:
            raise KeyError(model_id)
        if model.get("built_in"):
            raise ValueError("内置模型不能删除，只能禁用")
        del config["models"][model_id]
        if config.get("active_model_id") == model_id:
            config["active_model_id"] = "bge_m3"
        self.save(config)

    def set_active(self, model_id: str) -> dict[str, Any]:
        model = self.get(model_id)
        metadata = self.load_collection_metadata()
        compatibility = metadata.compatibility_with(model) if metadata else {"need_reindex": False, "issues": []}
        config = self.load()
        config["active_model_id"] = model_id
        self.save(config)
        return {
            "active_model_id": model_id,
            "need_reindex": bool(compatibility.get("need_reindex")),
            "message": "更换 embedding 模型后，需要重建向量索引，否则检索结果无效。" if compatibility.get("need_reindex") else "当前 collection 与模型兼容。",
            "issues": compatibility.get("issues", []),
        }

    def update_last_test(self, model_id: str, score: float) -> None:
        config = self.load()
        model = config["models"][model_id]
        model["last_test_score"] = round(float(score), 4)
        model["last_test_at"] = now_iso()
        self.save(config)

    def load_collection_metadata(self) -> CollectionMetadata | None:
        if not self.collection_metadata_path.exists():
            return None
        data = json.loads(self.collection_metadata_path.read_text(encoding="utf-8"))
        return CollectionMetadata(**data)

    def save_collection_metadata(self, metadata: CollectionMetadata) -> None:
        self.collection_metadata_path.parent.mkdir(parents=True, exist_ok=True)
        self.collection_metadata_path.write_text(json.dumps(asdict(metadata), ensure_ascii=False, indent=2), encoding="utf-8")


class MockEmbeddingClient:
    def __init__(self, model: EmbeddingModelSpec) -> None:
        self.model = model
        self.dimension = int(model.dimension or 128)

    def embed(self, text: str) -> list[float]:
        return embed_text(f"{self.model.model_id}\n{text}", dimensions=self.dimension)

    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        return [self.embed(text) for text in texts]


class EmbeddingConnectionTester:
    def test_model(self, model: EmbeddingModelSpec, collection_metadata: CollectionMetadata | None = None) -> dict[str, Any]:
        start = time.perf_counter()
        errors: list[str] = []
        simulated = True
        if model.provider == "custom_api" and not model.base_url and model.model_id != "custom_api_template":
            errors.append("custom_api 需要 base_url")
        if model.provider == "openai" and model.api_key_env and not os.getenv(model.api_key_env):
            simulated = True
        if model.dimension is None:
            errors.append("dimension 未配置，无法校验 collection 兼容性")
            dimension = 0
            embedding: list[float] = []
        else:
            client = MockEmbeddingClient(model)
            embedding = client.embed("员工出差住宿报销标准")
            dimension = len(embedding)
        contains_nan_inf = has_nan_inf(embedding)
        norm = vector_norm(embedding)
        batch_texts = [
            "员工出差住宿报销标准",
            "客户申请退款流程",
            "产品保修期限说明",
            "数据库备份策略",
            "客服机器人部署架构",
        ]
        batch_start = time.perf_counter()
        batch_vectors = MockEmbeddingClient(model).embed_batch(batch_texts) if model.dimension else []
        batch_latency_ms = round((time.perf_counter() - batch_start) * 1000, 3)
        dimensions = [len(vector) for vector in batch_vectors]
        compatibility = collection_metadata.compatibility_with(model) if collection_metadata else {
            "compatible": True,
            "need_reindex": False,
            "can_write": True,
            "issues": [],
        }
        if contains_nan_inf:
            errors.append("embedding 包含 NaN 或 Inf")
        return {
            "model_id": model.model_id,
            "available": not errors,
            "simulated": simulated,
            "connection_test": {"available": not errors, "error_message": "; ".join(errors), "latency_ms": round((time.perf_counter() - start) * 1000, 3)},
            "single_embedding_test": {
                "input": "员工出差住宿报销标准",
                "dimension": dimension,
                "first_10_values": [round(value, 6) for value in embedding[:10]],
                "norm": round(norm, 6),
                "contains_nan_inf": contains_nan_inf,
            },
            "batch_embedding_test": {
                "input_count": len(batch_texts),
                "batch_latency_ms": batch_latency_ms,
                "dimensions": dimensions,
                "dimension_consistent": len(set(dimensions)) <= 1,
            },
            "collection_compatibility_test": compatibility,
            "suggestion": "Demo Mode 使用 mock embedding 跑通流程，不代表真实语义检索。" if simulated else "模型连接正常，可以运行检索测试。",
        }


class EmbeddingSimilarityTester:
    positive_pairs = [
        ("员工出差住宿报销标准", "出差住酒店最多可以报多少钱"),
        ("客户申请退款流程", "用户如何办理退款"),
        ("产品保修期限说明", "设备坏了多久内可以免费维修"),
    ]
    negative_pairs = [
        ("员工出差住宿报销标准", "客服机器人部署架构"),
        ("客户申请退款流程", "员工绩效考核规则"),
        ("产品保修期限说明", "数据库备份策略"),
    ]
    hard_negative_pairs = [
        ("客户申请退款流程", "客户申请退货物流规则"),
        ("员工差旅住宿标准", "员工差旅交通补贴标准"),
        ("产品保修期限说明", "产品退换货政策"),
    ]

    def run(self, model: EmbeddingModelSpec) -> dict[str, Any]:
        start = time.perf_counter()
        client = MockEmbeddingClient(model)
        groups = {
            "positive": self.positive_pairs,
            "negative": self.negative_pairs,
            "hard_negative": self.hard_negative_pairs,
        }
        pair_rows: list[dict[str, Any]] = []
        scores_by_group: dict[str, list[float]] = {}
        for group, pairs in groups.items():
            scores: list[float] = []
            for left, right in pairs:
                score = cosine_similarity(client.embed(left), client.embed(right))
                scores.append(score)
                pair_rows.append({"group": group, "text_a": left, "text_b": right, "similarity": round(score, 6)})
            scores_by_group[group] = scores
        positive_avg = avg(scores_by_group["positive"])
        negative_avg = avg(scores_by_group["negative"])
        hard_avg = avg(scores_by_group["hard_negative"])
        pair_accuracy = sum(1 for pos, neg in zip(scores_by_group["positive"], scores_by_group["negative"]) if pos > neg) / len(self.positive_pairs)
        hard_sep = sum(1 for pos, hard in zip(scores_by_group["positive"], scores_by_group["hard_negative"]) if pos > hard + 0.04) / len(self.positive_pairs)
        all_scores = scores_by_group["positive"] + scores_by_group["negative"] + scores_by_group["hard_negative"]
        pos_hard_margin = positive_avg - hard_avg
        conclusion = similarity_conclusion(pos_hard_margin, pair_accuracy)
        return {
            "model_id": model.model_id,
            "positive_avg_similarity": round(positive_avg, 6),
            "negative_avg_similarity": round(negative_avg, 6),
            "hard_negative_avg_similarity": round(hard_avg, 6),
            "pos_neg_margin": round(positive_avg - negative_avg, 6),
            "pos_hard_neg_margin": round(pos_hard_margin, 6),
            "pair_accuracy": round(pair_accuracy, 6),
            "hard_negative_separation_rate": round(hard_sep, 6),
            "score_std": round(statistics.pstdev(all_scores), 6) if len(all_scores) > 1 else 0,
            "latency_ms": round((time.perf_counter() - start) * 1000, 3),
            "pair_rows": pair_rows,
            "conclusion": conclusion,
            "warning": "该模型对相近业务概念区分不足。" if pos_hard_margin < 0.12 else "",
            "note": "这些阈值只是本地启发式，最终模型选择应以企业知识库检索测试为准。",
        }


@dataclass
class RetrievalEvalCase:
    query: str
    expected_doc_ids: list[str] = field(default_factory=list)
    expected_chunk_ids: list[str] = field(default_factory=list)
    expected_keywords: list[str] = field(default_factory=list)
    difficulty: str = "medium"
    query_type: str = "policy"


class EmbeddingRetrievalBenchmark:
    def __init__(self, eval_path: str | Path = DEFAULT_RETRIEVAL_EVAL_PATH) -> None:
        self.eval_path = Path(eval_path)

    def ensure_eval_set(self) -> None:
        if self.eval_path.exists():
            return
        self.eval_path.parent.mkdir(parents=True, exist_ok=True)
        rows = [
            {
                "query": "出差住酒店最多可以报多少钱？",
                "expected_doc_ids": ["doc_travel_policy", "travel_policy", "enterprise_kb"],
                "expected_chunk_ids": ["chunk_001"],
                "expected_keywords": ["住宿标准", "一线城市", "600"],
                "difficulty": "medium",
                "query_type": "policy",
            },
            {
                "query": "客户如何办理退款？",
                "expected_doc_ids": ["doc_refund_policy", "refund_policy", "enterprise_kb"],
                "expected_chunk_ids": ["chunk_002"],
                "expected_keywords": ["退款", "流程", "申请"],
                "difficulty": "easy",
                "query_type": "procedure",
            },
            {
                "query": "产品坏了多久内可以免费维修？",
                "expected_doc_ids": ["doc_warranty", "warranty_policy", "enterprise_kb"],
                "expected_chunk_ids": ["chunk_003"],
                "expected_keywords": ["保修", "期限", "维修"],
                "difficulty": "medium",
                "query_type": "fact",
            },
        ]
        self.eval_path.write_text("\n".join(json.dumps(row, ensure_ascii=False) for row in rows), encoding="utf-8")

    def load_cases(self) -> list[RetrievalEvalCase]:
        self.ensure_eval_set()
        cases: list[RetrievalEvalCase] = []
        for line in self.eval_path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                cases.append(RetrievalEvalCase(**json.loads(line)))
        return cases

    def run(self, model: EmbeddingModelSpec, chunks: list[Chunk] | None = None, top_k: int = 10) -> dict[str, Any]:
        start = time.perf_counter()
        chunks = chunks or default_benchmark_chunks()
        cases = self.load_cases()
        client = MockEmbeddingClient(model)
        per_query: list[dict[str, Any]] = []
        latencies: list[float] = []
        for case in cases:
            query_start = time.perf_counter()
            results = self._search(case.query, chunks, client, top_k=top_k)
            latency = (time.perf_counter() - query_start) * 1000
            latencies.append(latency)
            relevance = [is_relevant(row, case) for row in results]
            per_query.append(
                {
                    "query": case.query,
                    "difficulty": case.difficulty,
                    "query_type": case.query_type,
                    "hit": any(relevance[:5]),
                    "failure_reason": "" if any(relevance[:5]) else "Top 5 未命中 expected doc/chunk/keyword",
                    "top_k_chunks": results,
                    "metrics": query_metrics(relevance, expected_count=expected_count(case), k=10),
                    "latency_ms": round(latency, 3),
                }
            )
        aggregate = aggregate_retrieval_metrics(per_query, latencies)
        aggregate.update(
            {
                "model_id": model.model_id,
                "case_count": len(cases),
                "embedding_cost_estimate": estimate_cost(model, len(chunks)),
                "storage_size_estimate": estimate_storage(model, len(chunks)),
                "failed_queries_count": sum(1 for row in per_query if not row["hit"]),
                "per_query_results": per_query,
                "latency_ms": round((time.perf_counter() - start) * 1000, 3),
            }
        )
        return aggregate

    def _search(self, query: str, chunks: list[Chunk], client: MockEmbeddingClient, top_k: int) -> list[dict[str, Any]]:
        query_vector = client.embed(query)
        rows: list[dict[str, Any]] = []
        for chunk in chunks:
            score = cosine_similarity(query_vector, client.embed(chunk.searchable_text))
            rows.append(
                {
                    "chunk_id": chunk.chunk_id,
                    "doc_id": chunk.document_id,
                    "filename": chunk.filename,
                    "section_path": chunk.section_path,
                    "page": chunk.page,
                    "text_preview": chunk.text[:220],
                    "score": round(score, 6),
                }
            )
        rows.sort(key=lambda item: item["score"], reverse=True)
        return rows[:top_k]


class EmbeddingModelComparator:
    def __init__(self, eval_config_path: str | Path = DEFAULT_EVAL_PATH) -> None:
        self.eval_config_path = Path(eval_config_path)
        if not self.eval_config_path.exists():
            self.eval_config_path.parent.mkdir(parents=True, exist_ok=True)
            self.eval_config_path.write_text(yaml.safe_dump(default_embedding_eval_config(), sort_keys=False), encoding="utf-8")

    def load_config(self) -> dict[str, Any]:
        return yaml.safe_load(self.eval_config_path.read_text(encoding="utf-8")) or default_embedding_eval_config()

    def compare(self, models: list[EmbeddingModelSpec], chunks: list[Chunk] | None = None) -> dict[str, Any]:
        weights = self.load_config().get("score_weights") or default_embedding_eval_config()["score_weights"]
        rows: list[dict[str, Any]] = []
        similarity_tester = EmbeddingSimilarityTester()
        benchmark = EmbeddingRetrievalBenchmark()
        for model in models:
            similarity = similarity_tester.run(model)
            retrieval = benchmark.run(model, chunks=chunks)
            latency_score = normalize_inverse(retrieval["avg_latency_ms"], 500)
            cost_score = normalize_inverse(float(retrieval["embedding_cost_estimate"]), 0.02)
            score = (
                weights.get("recall_at_5", 0.30) * retrieval["recall_at_5"] * 100
                + weights.get("mrr_at_10", 0.20) * retrieval["mrr_at_10"] * 100
                + weights.get("ndcg_at_10", 0.20) * retrieval["ndcg_at_10"] * 100
                + weights.get("pair_accuracy", 0.10) * similarity["pair_accuracy"] * 100
                + weights.get("latency_score", 0.10) * latency_score
                + weights.get("cost_score", 0.10) * cost_score
            )
            rows.append(
                {
                    "model_id": model.model_id,
                    "display_name": model.display_name,
                    "provider": model.provider,
                    "dimension": model.dimension,
                    "max_input_tokens": model.max_input_tokens,
                    "language_support": model.language_support,
                    "local_or_api": "API" if model.provider in {"openai", "custom_api"} else "Local",
                    "supports_custom_dimension": model.provider == "openai",
                    "instruction_aware": "qwen" in model.model.lower(),
                    "estimated_cost": estimate_cost(model, 1000),
                    "resource_usage": resource_usage(model),
                    "positive_avg_similarity": similarity["positive_avg_similarity"],
                    "hard_negative_avg_similarity": similarity["hard_negative_avg_similarity"],
                    "pos_hard_neg_margin": similarity["pos_hard_neg_margin"],
                    "pair_accuracy": similarity["pair_accuracy"],
                    "hit_at_5": retrieval["hit_at_5"],
                    "recall_at_5": retrieval["recall_at_5"],
                    "recall_at_10": retrieval["recall_at_10"],
                    "mrr_at_10": retrieval["mrr_at_10"],
                    "ndcg_at_10": retrieval["ndcg_at_10"],
                    "precision_at_5": retrieval["precision_at_5"],
                    "avg_latency_ms": retrieval["avg_latency_ms"],
                    "p95_latency_ms": retrieval["p95_latency_ms"],
                    "storage_size": retrieval["storage_size_estimate"],
                    "cost_estimate": retrieval["embedding_cost_estimate"],
                    "failure_rate": retrieval["failed_queries_count"] / max(retrieval["case_count"], 1),
                    "overall_score": round(score, 2),
                    "grade": grade_for_score(score),
                }
            )
        recommendations = comparison_recommendations(rows)
        return {"rows": rows, "recommendations": recommendations, "weights": weights}


class EmbeddingModelReportExporter:
    def to_json(self, payload: dict[str, Any]) -> str:
        return json.dumps(payload, ensure_ascii=False, indent=2)

    def to_markdown(self, payload: dict[str, Any]) -> str:
        lines = ["# Embedding Model Center Report", ""]
        if "recommendations" in payload:
            lines.append("## Recommendations")
            for key, value in payload["recommendations"].items():
                lines.append(f"- {key}: {value}")
            lines.append("")
        rows = payload.get("rows") or payload.get("per_query_results") or payload.get("pair_rows") or []
        if rows:
            headers = list(rows[0].keys())
            lines.append("## Results")
            lines.append("| " + " | ".join(headers) + " |")
            lines.append("| " + " | ".join("---" for _ in headers) + " |")
            for row in rows:
                lines.append("| " + " | ".join(str(row.get(header, "")) for header in headers) + " |")
        else:
            lines.append("```json")
            lines.append(json.dumps(payload, ensure_ascii=False, indent=2))
            lines.append("```")
        return "\n".join(lines)

    def to_csv(self, rows: list[dict[str, Any]]) -> str:
        output = io.StringIO()
        if not rows:
            return ""
        headers = list(rows[0].keys())
        writer = csv.DictWriter(output, fieldnames=headers)
        writer.writeheader()
        for row in rows:
            writer.writerow({key: json.dumps(value, ensure_ascii=False) if isinstance(value, (dict, list)) else value for key, value in row.items()})
        return output.getvalue()


def default_embedding_models_config() -> dict[str, Any]:
    return yaml.safe_load(DEFAULT_MODELS_PATH.read_text(encoding="utf-8")) if DEFAULT_MODELS_PATH.exists() else {
        "active_model_id": "bge_m3",
        "models": {},
    }


def default_embedding_eval_config() -> dict[str, Any]:
    return {
        "score_weights": {
            "recall_at_5": 0.30,
            "mrr_at_10": 0.20,
            "ndcg_at_10": 0.20,
            "pair_accuracy": 0.10,
            "latency_score": 0.10,
            "cost_score": 0.10,
        },
        "targets": {"latency_ms": 500, "cost_per_1k_chunks": 0.02, "storage_mb_per_1k_chunks": 6.0},
        "default_top_k": 10,
    }


def default_benchmark_chunks() -> list[Chunk]:
    samples = [
        ("doc_travel_policy", "chunk_001", "travel_policy.md", "差旅制度", "员工出差住宿标准：一线城市住宿上限为 600 元/晚，二线城市为 450 元/晚。"),
        ("doc_refund_policy", "chunk_002", "refund_policy.md", "退款流程", "客户申请退款流程：提交订单号、退款原因和支付凭证，客服审核后 3 个工作日内处理。"),
        ("doc_warranty", "chunk_003", "warranty_policy.md", "保修说明", "产品保修期限说明：设备自购买日起 12 个月内可免费维修，进水和人为损坏除外。"),
        ("doc_it", "chunk_004", "it_runbook.md", "系统运维", "数据库备份策略要求每日增量备份、每周全量备份，并保留 90 天。"),
    ]
    return [
        Chunk(
            id=chunk_id,
            document_id=doc_id,
            chunk_id=chunk_id,
            domain="enterprise_kb",
            section_path=section,
            filename=filename,
            page=index,
            text=text,
            metadata={"doc_id": doc_id, "chunk_id": chunk_id, "filename": filename},
        )
        for index, (doc_id, chunk_id, filename, section, text) in enumerate(samples, start=1)
    ]


def has_nan_inf(vector: list[float]) -> bool:
    return any(math.isnan(value) or math.isinf(value) for value in vector)


def vector_norm(vector: list[float]) -> float:
    return math.sqrt(sum(value * value for value in vector))


def avg(values: list[float]) -> float:
    return sum(values) / max(len(values), 1)


def similarity_conclusion(pos_hard_margin: float, pair_accuracy: float) -> str:
    if pos_hard_margin >= 0.20 and pair_accuracy >= 0.85:
        return "Excellent"
    if pos_hard_margin >= 0.12 and pair_accuracy >= 0.85:
        return "Good"
    if pos_hard_margin >= 0.04:
        return "Weak"
    return "Failed"


def is_relevant(row: dict[str, Any], case: RetrievalEvalCase) -> bool:
    if row["chunk_id"] in case.expected_chunk_ids:
        return True
    if row["doc_id"] in case.expected_doc_ids:
        return True
    text = str(row.get("text_preview") or "")
    return any(keyword and keyword in text for keyword in case.expected_keywords)


def expected_count(case: RetrievalEvalCase) -> int:
    return max(len(set(case.expected_chunk_ids + case.expected_doc_ids + case.expected_keywords)), 1)


def query_metrics(relevance: list[bool], expected_count: int, k: int = 10) -> dict[str, float]:
    return {
        "hit_at_1": hit_at_k(relevance, 1),
        "hit_at_3": hit_at_k(relevance, 3),
        "hit_at_5": hit_at_k(relevance, 5),
        "recall_at_5": recall_at_k(relevance, expected_count, 5),
        "recall_at_10": recall_at_k(relevance, expected_count, 10),
        "precision_at_5": precision_at_k(relevance, 5),
        "mrr_at_10": mrr_at_k(relevance, k),
        "ndcg_at_10": ndcg_at_k(relevance, k),
        "map_at_10": map_at_k(relevance, k),
    }


def hit_at_k(relevance: list[bool], k: int) -> float:
    return 1.0 if any(relevance[:k]) else 0.0


def recall_at_k(relevance: list[bool], expected_count_value: int, k: int) -> float:
    return min(sum(1 for item in relevance[:k] if item) / max(expected_count_value, 1), 1.0)


def precision_at_k(relevance: list[bool], k: int) -> float:
    return sum(1 for item in relevance[:k] if item) / max(k, 1)


def mrr_at_k(relevance: list[bool], k: int) -> float:
    for index, item in enumerate(relevance[:k], start=1):
        if item:
            return 1.0 / index
    return 0.0


def ndcg_at_k(relevance: list[bool], k: int) -> float:
    dcg = sum((1.0 / math.log2(index + 1)) for index, item in enumerate(relevance[:k], start=1) if item)
    ideal_hits = min(sum(1 for item in relevance if item), k)
    ideal = sum(1.0 / math.log2(index + 1) for index in range(1, ideal_hits + 1))
    return dcg / ideal if ideal else 0.0


def map_at_k(relevance: list[bool], k: int) -> float:
    hits = 0
    precisions: list[float] = []
    for index, item in enumerate(relevance[:k], start=1):
        if item:
            hits += 1
            precisions.append(hits / index)
    return avg(precisions)


def aggregate_retrieval_metrics(per_query: list[dict[str, Any]], latencies: list[float]) -> dict[str, Any]:
    keys = ["hit_at_1", "hit_at_3", "hit_at_5", "recall_at_5", "recall_at_10", "precision_at_5", "mrr_at_10", "ndcg_at_10", "map_at_10"]
    metrics = {key: round(avg([row["metrics"][key] for row in per_query]), 6) for key in keys}
    metrics["avg_latency_ms"] = round(avg(latencies), 3)
    metrics["p95_latency_ms"] = round(percentile(latencies, 95), 3)
    return metrics


def percentile(values: list[float], pct: float) -> float:
    if not values:
        return 0.0
    values = sorted(values)
    position = (len(values) - 1) * pct / 100
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        return values[lower]
    return values[lower] * (upper - position) + values[upper] * (position - lower)


def estimate_cost(model: EmbeddingModelSpec, chunk_count: int) -> float:
    if model.provider == "openai":
        base = 0.02 if "small" in model.model else 0.13
        return round(base * chunk_count / 1000, 6)
    return 0.0


def estimate_storage(model: EmbeddingModelSpec, chunk_count: int) -> str:
    dimension = int(model.dimension or 128)
    mb = dimension * 4 * chunk_count / 1024 / 1024
    return f"{mb:.2f} MB"


def normalize_inverse(actual: float, target: float) -> float:
    if actual <= 0:
        return 100.0
    return min(100.0, target / actual * 100)


def grade_for_score(score: float) -> str:
    if score >= 85:
        return "Excellent"
    if score >= 75:
        return "Good"
    if score >= 60:
        return "Usable"
    if score >= 45:
        return "Weak"
    return "Failed"


def resource_usage(model: EmbeddingModelSpec) -> str:
    if model.provider == "openai":
        return "API cost"
    if "4B" in model.model:
        return "GPU recommended"
    if "0.6B" in model.model:
        return "CPU/GPU light"
    return "Local model"


def comparison_recommendations(rows: list[dict[str, Any]]) -> dict[str, str]:
    if not rows:
        return {}
    best = max(rows, key=lambda row: row["overall_score"])
    quality = max(rows, key=lambda row: row["recall_at_5"] + row["mrr_at_10"] + row["ndcg_at_10"])
    cost = min(rows, key=lambda row: (float(row["cost_estimate"]), -row["overall_score"]))
    local_rows = [row for row in rows if row["local_or_api"] == "Local"] or rows
    api_rows = [row for row in rows if row["local_or_api"] == "API"] or rows
    return {
        "综合推荐模型": best["display_name"],
        "质量优先推荐": quality["display_name"],
        "成本优先推荐": cost["display_name"],
        "本地部署推荐": max(local_rows, key=lambda row: row["overall_score"])["display_name"],
        "API 部署推荐": max(api_rows, key=lambda row: row["overall_score"])["display_name"],
    }


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()
