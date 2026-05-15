from __future__ import annotations

import copy
import csv
import html
import io
import json
import math
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

import yaml


ROOT_DIR = Path(__file__).resolve().parents[3]
DEFAULT_WEIGHTS_PATH = ROOT_DIR / "configs" / "embedding_eval_weights.yaml"

CATEGORY_KEYS = (
    "retrieval_quality",
    "semantic_separation",
    "rag_context_quality",
    "engineering_quality",
)

CATEGORY_LABELS = {
    "retrieval_quality": "检索质量",
    "semantic_separation": "语义区分度",
    "rag_context_quality": "RAG 上下文质量",
    "engineering_quality": "工程可用性",
}

METRIC_DISPLAY_NAMES = {
    "recall_at_5": "Recall@5",
    "ndcg_at_10": "nDCG@10",
    "mrr_at_10": "MRR@10",
    "hit_at_1": "Hit@1",
    "precision_at_5": "Precision@5",
    "pair_accuracy": "Pair Accuracy",
    "hard_negative_margin": "Hard Negative Margin",
    "score_distribution_quality": "Score Distribution Quality",
    "context_recall": "Context Recall",
    "context_precision": "Context Precision",
    "citation_support_rate": "Citation Support Rate",
    "avg_latency_score": "Avg Latency",
    "p95_latency_score": "P95 Latency",
    "cost_score": "Cost / 1k chunks",
    "storage_score": "Storage / 1k chunks",
    "stability_score": "Stability",
}

METRIC_SUGGESTIONS = {
    "recall_at_5": "补充业务问法、检查切片粒度，必要时开启 hybrid retrieval。",
    "ndcg_at_10": "增加 reranker，或优化 query rewrite 和标题 metadata。",
    "mrr_at_10": "提升首个正确证据排名，可加入 rerank 和 hard negative cases。",
    "hit_at_1": "强化高价值 FAQ、术语同义词和标题路径。",
    "precision_at_5": "降低噪声 chunk，收紧过滤条件或提高 rerank 权重。",
    "pair_accuracy": "补充正负样本对，覆盖核心业务概念。",
    "hard_negative_margin": "增加容易混淆的 hard negative 测试，如退款流程与退货规则。",
    "score_distribution_quality": "检查相似度分布，补充更真实的负样本和近义业务问题。",
    "context_recall": "提高 top_k、优化切片和召回融合策略。",
    "context_precision": "减少过长 chunk，过滤重复内容，启用 rerank。",
    "citation_support_rate": "检查 citation formatter 和 chunk metadata，避免引用不支持答案。",
    "avg_latency_score": "调大 batch，使用本地缓存或更快的 embedding provider。",
    "p95_latency_score": "检查长尾请求、超时重试和并发批处理。",
    "cost_score": "降低 API 调用量，缓存 embedding，或改用本地模型。",
    "storage_score": "控制维度和 chunk 数，按 collection 做生命周期管理。",
    "stability_score": "排查失败率、超时、NaN/Inf 和维度不一致问题。",
}

GRADE_TEXT = {
    "Excellent": "推荐用于生产级 RAG。",
    "Good": "适合大多数企业知识库场景，可进入试运行。",
    "Usable": "可用于 Demo 或低风险场景，建议继续优化。",
    "Weak": "检索质量偏弱，不建议直接用于正式知识库。",
    "Failed": "不建议使用，需更换模型或检查配置。",
}


@dataclass
class WeightValidation:
    is_valid: bool
    category_total: float
    metric_total: float
    category_metric_totals: dict[str, float]
    errors: list[str] = field(default_factory=list)


@dataclass
class MetricScoreRow:
    metric_key: str
    metric_name: str
    category_key: str
    category_name: str
    current_value: str
    normalized_score: float
    weight: float
    weighted_score: float
    judgement: str
    explanation: str
    suggestion: str
    why_it_matters: str

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class EmbeddingScoreResult:
    model_name: str
    provider: str
    dimension: int
    max_input_length: int
    overall_score: float
    retrieval_quality_score: float
    semantic_separation_score: float
    rag_context_quality_score: float
    engineering_quality_score: float
    grade: str
    recommendation: str
    risk_notes: list[str]
    metric_rows: list[MetricScoreRow]
    natural_language_explanation: str
    need_reindex: bool = False
    recommended_use: str = ""

    def as_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["metric_rows"] = [row.as_dict() for row in self.metric_rows]
        return data


def load_weights_config(path: str | Path | None = None) -> dict[str, Any]:
    config_path = Path(path) if path else DEFAULT_WEIGHTS_PATH
    with config_path.open("r", encoding="utf-8") as file:
        return yaml.safe_load(file) or {}


def save_weights_config(config: dict[str, Any], path: str | Path | None = None) -> None:
    config_path = Path(path) if path else DEFAULT_WEIGHTS_PATH
    config_path.parent.mkdir(parents=True, exist_ok=True)
    with config_path.open("w", encoding="utf-8") as file:
        yaml.safe_dump(config, file, allow_unicode=True, sort_keys=False)


def validate_weights_config(config: dict[str, Any], tolerance: float = 0.01) -> WeightValidation:
    category_total = 0.0
    metric_total = 0.0
    category_metric_totals: dict[str, float] = {}
    errors: list[str] = []
    for category_key in CATEGORY_KEYS:
        category = config.get(category_key, {}) or {}
        category_weight = float(category.get("weight", 0) or 0)
        category_total += category_weight
        metrics = category.get("metrics", {}) or {}
        metric_sum = sum(float(metric.get("weight", 0) or 0) for metric in metrics.values())
        category_metric_totals[category_key] = metric_sum
        metric_total += metric_sum
        if abs(metric_sum - category_weight) > tolerance:
            errors.append(
                f"{CATEGORY_LABELS.get(category_key, category_key)} 的指标权重合计 {metric_sum:.2f}，"
                f"应等于分组权重 {category_weight:.2f}。"
            )
    if abs(category_total - 100.0) > tolerance:
        errors.append(f"四个分组权重合计 {category_total:.2f}，必须等于 100。")
    if abs(metric_total - 100.0) > tolerance:
        errors.append(f"所有指标权重合计 {metric_total:.2f}，必须等于 100。")
    return WeightValidation(
        is_valid=not errors,
        category_total=round(category_total, 6),
        metric_total=round(metric_total, 6),
        category_metric_totals={key: round(value, 6) for key, value in category_metric_totals.items()},
        errors=errors,
    )


def normalize_weights_config(config: dict[str, Any]) -> dict[str, Any]:
    normalized = copy.deepcopy(config)
    category_weights = [float((normalized.get(key, {}) or {}).get("weight", 0) or 0) for key in CATEGORY_KEYS]
    category_sum = sum(category_weights)
    if category_sum <= 0:
        equal = 100.0 / len(CATEGORY_KEYS)
        category_weights = [equal for _ in CATEGORY_KEYS]
        category_sum = 100.0
    new_category_weights = [round(old_weight / category_sum * 100.0, 4) for old_weight in category_weights]
    if new_category_weights:
        new_category_weights[-1] = round(100.0 - sum(new_category_weights[:-1]), 4)
    for category_key, new_category_weight in zip(CATEGORY_KEYS, new_category_weights):
        category = normalized.setdefault(category_key, {})
        category["weight"] = new_category_weight
        metrics = category.get("metrics", {}) or {}
        metric_sum = sum(float(metric.get("weight", 0) or 0) for metric in metrics.values())
        if metrics:
            metric_items = list(metrics.values())
            if metric_sum <= 0:
                equal_metric = new_category_weight / len(metrics)
                for metric in metric_items:
                    metric["weight"] = round(equal_metric, 4)
            else:
                for metric in metric_items:
                    metric_weight = float(metric.get("weight", 0) or 0)
                    metric["weight"] = round(metric_weight / metric_sum * new_category_weight, 4)
            metric_items[-1]["weight"] = round(new_category_weight - sum(float(metric.get("weight", 0) or 0) for metric in metric_items[:-1]), 4)
    return normalized


def apply_weight_profile(config: dict[str, Any], profile_name: str) -> dict[str, Any]:
    profiles = config.get("profiles", {}) or {}
    if profile_name not in profiles:
        raise KeyError(f"Unknown embedding eval weight profile: {profile_name}")
    profile_weights = (profiles[profile_name] or {}).get("weights", {}) or {}
    updated = copy.deepcopy(config)
    for category_key, new_weight in profile_weights.items():
        if category_key not in CATEGORY_KEYS:
            continue
        category = updated.setdefault(category_key, {})
        old_weight = float(category.get("weight", 0) or 0)
        category["weight"] = float(new_weight)
        metrics = category.get("metrics", {}) or {}
        metric_sum = sum(float(metric.get("weight", 0) or 0) for metric in metrics.values())
        base = metric_sum if metric_sum > 0 else old_weight
        if metrics:
            for metric in metrics.values():
                metric_weight = float(metric.get("weight", 0) or 0)
                if base > 0:
                    metric["weight"] = round(metric_weight / base * float(new_weight), 4)
                else:
                    metric["weight"] = round(float(new_weight) / len(metrics), 4)
    updated["active_profile"] = profile_name
    return normalize_weights_config(updated)


def save_weight_profile(config: dict[str, Any], profile_name: str, category_weights: dict[str, float], description: str = "") -> dict[str, Any]:
    updated = copy.deepcopy(config)
    profiles = updated.setdefault("profiles", {})
    profiles[profile_name] = {
        "description": description or "用户自定义评分权重 profile。",
        "weights": {key: float(value) for key, value in category_weights.items() if key in CATEGORY_KEYS},
    }
    return updated


def need_reindex_for_model(
    collection_model: str | None,
    collection_dimension: int | None,
    candidate_model: str | None,
    candidate_dimension: int | None,
) -> bool:
    if not collection_model or collection_dimension is None:
        return False
    return collection_model != candidate_model or int(collection_dimension) != int(candidate_dimension or 0)


class EmbeddingScoreCalculator:
    def calculate(
        self,
        similarity_test_result: dict[str, Any],
        retrieval_benchmark_result: dict[str, Any],
        rag_context_result: dict[str, Any],
        engineering_result: dict[str, Any],
        weights_config: dict[str, Any],
        model_info: dict[str, Any] | None = None,
    ) -> EmbeddingScoreResult:
        validation = validate_weights_config(weights_config)
        if not validation.is_valid:
            raise ValueError("Invalid embedding eval weights: " + "; ".join(validation.errors))

        model_info = model_info or {}
        metric_rows: list[MetricScoreRow] = []
        category_weighted_scores: dict[str, float] = {}
        category_weights: dict[str, float] = {}
        sources = {
            "retrieval_quality": retrieval_benchmark_result or {},
            "semantic_separation": similarity_test_result or {},
            "rag_context_quality": rag_context_result or {},
            "engineering_quality": engineering_result or {},
        }

        for category_key in CATEGORY_KEYS:
            category = weights_config.get(category_key, {}) or {}
            category_name = category.get("label") or CATEGORY_LABELS[category_key]
            category_weight = float(category.get("weight", 0) or 0)
            category_weights[category_key] = category_weight
            category_weighted_scores[category_key] = 0.0
            for metric_key, metric_config in (category.get("metrics", {}) or {}).items():
                raw, normalized_score = self._metric_value_and_score(
                    metric_key=metric_key,
                    category_key=category_key,
                    source=sources[category_key],
                    engineering=engineering_result or {},
                    weights_config=weights_config,
                )
                metric_weight = float(metric_config.get("weight", 0) or 0)
                weighted_score = normalized_score * metric_weight / 100.0
                category_weighted_scores[category_key] += weighted_score
                metric_rows.append(
                    MetricScoreRow(
                        metric_key=metric_key,
                        metric_name=METRIC_DISPLAY_NAMES.get(metric_key, metric_key),
                        category_key=category_key,
                        category_name=category_name,
                        current_value=raw,
                        normalized_score=round(normalized_score, 2),
                        weight=round(metric_weight, 4),
                        weighted_score=round(weighted_score, 4),
                        judgement=grade_for_score(normalized_score),
                        explanation=str(metric_config.get("description") or ""),
                        suggestion=METRIC_SUGGESTIONS.get(metric_key, "结合业务目标调整测试集和检索策略。"),
                        why_it_matters=self._why_metric_matters(metric_key),
                    )
                )

        category_scores = {
            category_key: (
                category_weighted_scores[category_key] / category_weights[category_key] * 100.0
                if category_weights[category_key] > 0
                else 0.0
            )
            for category_key in CATEGORY_KEYS
        }
        overall_score = sum(row.weighted_score for row in metric_rows)
        dimension_mismatch = bool((engineering_result or {}).get("dimension_mismatch"))
        if dimension_mismatch:
            overall_score = min(overall_score, 44.0)
        grade = "Failed" if dimension_mismatch else grade_for_score(overall_score)
        risk_notes = self._risk_notes(metric_rows, engineering_result or {}, dimension_mismatch)
        recommendation = self._recommendation(grade, metric_rows, risk_notes)

        result = EmbeddingScoreResult(
            model_name=str(model_info.get("model_name") or model_info.get("model") or "mock-embedding"),
            provider=str(model_info.get("provider") or "mock"),
            dimension=int(model_info.get("dimension") or (engineering_result or {}).get("dimension") or 0),
            max_input_length=int(model_info.get("max_input_length") or 0),
            overall_score=round(overall_score, 2),
            retrieval_quality_score=round(category_scores["retrieval_quality"], 2),
            semantic_separation_score=round(category_scores["semantic_separation"], 2),
            rag_context_quality_score=round(category_scores["rag_context_quality"], 2),
            engineering_quality_score=round(category_scores["engineering_quality"], 2),
            grade=grade,
            recommendation=recommendation,
            risk_notes=risk_notes,
            metric_rows=metric_rows,
            natural_language_explanation="",
            need_reindex=need_reindex_for_model(
                model_info.get("collection_model"),
                model_info.get("collection_dimension"),
                model_info.get("model_name") or model_info.get("model"),
                model_info.get("dimension") or (engineering_result or {}).get("dimension"),
            ),
            recommended_use=recommended_use_for_grade(grade),
        )
        result.natural_language_explanation = generate_natural_language_explanation(result)
        return result

    def normalize_hard_negative_margin(self, margin: float) -> float:
        if margin >= 0.20:
            return 100.0
        if margin >= 0.12:
            return 80.0
        if margin >= 0.08:
            return 60.0
        if margin >= 0.04:
            return 40.0
        return 20.0

    def latency_score(self, actual_ms: float, target_ms: float) -> float:
        if actual_ms <= 0:
            return 0.0
        if actual_ms <= target_ms:
            return 100.0
        return clamp(target_ms / actual_ms * 100.0)

    def cost_score(self, actual_cost: float, target_cost: float) -> float:
        if actual_cost <= 0:
            return 100.0
        if target_cost <= 0:
            return 0.0
        return clamp(target_cost / actual_cost * 100.0)

    def storage_score(self, dimension: int, target_storage_mb_per_1k_chunks: float) -> tuple[str, float]:
        if dimension <= 0:
            return "unknown", 0.0
        actual_mb = dimension * 4 * 1000 / 1024 / 1024
        if actual_mb <= 0:
            return "unknown", 0.0
        return f"{actual_mb:.2f} MB", clamp(target_storage_mb_per_1k_chunks / actual_mb * 100.0)

    def score_distribution_quality(self, source: dict[str, Any]) -> float:
        if "score_distribution_quality" in source:
            return scale_to_score(float(source.get("score_distribution_quality") or 0))
        positive = [float(value) for value in source.get("positive_scores", []) or []]
        negative = [float(value) for value in source.get("negative_scores", []) or []]
        hard_negative = [float(value) for value in source.get("hard_negative_scores", []) or []]
        if not positive or not (negative or hard_negative):
            return self.normalize_hard_negative_margin(float(source.get("hard_negative_margin", 0) or 0))
        pos_floor = percentile(positive, 25)
        neg_ceiling = percentile(negative, 75) if negative else 0.0
        hard_ceiling = percentile(hard_negative, 75) if hard_negative else neg_ceiling
        gap = min(pos_floor - neg_ceiling, pos_floor - hard_ceiling)
        return self.normalize_hard_negative_margin(gap)

    def _metric_value_and_score(
        self,
        metric_key: str,
        category_key: str,
        source: dict[str, Any],
        engineering: dict[str, Any],
        weights_config: dict[str, Any],
    ) -> tuple[str, float]:
        if metric_key == "hard_negative_margin":
            margin = float(source.get(metric_key, 0) or 0)
            return f"{margin:.2f}", self.normalize_hard_negative_margin(margin)
        if metric_key == "score_distribution_quality":
            score = self.score_distribution_quality(source)
            return self._distribution_label(source, score), score
        if metric_key == "avg_latency_score":
            actual = float(engineering.get("avg_latency_ms", 0) or 0)
            target = float(engineering.get("target_avg_latency_ms") or weights_config.get("target_avg_latency_ms") or 500)
            return f"{actual:.0f}ms", self.latency_score(actual, target)
        if metric_key == "p95_latency_score":
            actual = float(engineering.get("p95_latency_ms", 0) or 0)
            target = float(engineering.get("target_p95_latency_ms") or weights_config.get("target_p95_latency_ms") or 1500)
            return f"{actual:.0f}ms", self.latency_score(actual, target)
        if metric_key == "cost_score":
            actual = float(engineering.get("cost_per_1k_chunks", 0) or 0)
            target = float(engineering.get("target_cost_per_1k_chunks") or weights_config.get("target_cost_per_1k_chunks") or 0.02)
            return f"{actual:.4f}", self.cost_score(actual, target)
        if metric_key == "storage_score":
            dimension = int(engineering.get("dimension", 0) or 0)
            target = float(weights_config.get("target_storage_mb_per_1k_chunks") or 6.0)
            return self.storage_score(dimension, target)
        if metric_key == "stability_score":
            if engineering.get("dimension_mismatch"):
                return "dimension mismatch", 0.0
            if "stability_score" in engineering:
                score = scale_to_score(float(engineering.get("stability_score") or 0))
            else:
                failure_rate = float(engineering.get("failure_rate", 0) or 0)
                score = clamp(100.0 - failure_rate * 100.0)
            if engineering.get("has_nan_inf"):
                score = min(score, 60.0)
            failure_rate = float(engineering.get("failure_rate", 0) or 0)
            return f"{failure_rate * 100:.1f}% failure", score
        value = float(source.get(metric_key, 0) or 0)
        return f"{value:.2f}", scale_to_score(value)

    def _distribution_label(self, source: dict[str, Any], score: float) -> str:
        if source.get("positive_scores") or source.get("negative_scores") or source.get("hard_negative_scores"):
            return f"distribution score {score:.0f}"
        return f"{score:.0f}"

    def _why_metric_matters(self, metric_key: str) -> str:
        if metric_key in {"recall_at_5", "ndcg_at_10", "mrr_at_10", "hit_at_1", "precision_at_5"}:
            return "这些指标直接衡量用户问题能否检索到正确 chunk，以及正确证据是否排在前面。"
        if metric_key in {"context_recall", "context_precision", "citation_support_rate"}:
            return "RAG 不只需要召回 chunk，还要把干净且能支撑答案的上下文交给 LLM。"
        if metric_key in {"avg_latency_score", "p95_latency_score", "cost_score", "storage_score", "stability_score"}:
            return "企业知识库需要长期运行，延迟、成本、存储和稳定性会影响真实可用性。"
        return "语义区分度决定模型能否区分相近但业务含义不同的问题。"

    def _risk_notes(self, rows: list[MetricScoreRow], engineering: dict[str, Any], dimension_mismatch: bool) -> list[str]:
        risks: list[str] = []
        if dimension_mismatch:
            risks.append("当前 collection 的模型或维度不一致，必须重建索引。")
        if engineering.get("has_nan_inf"):
            risks.append("检测到 NaN/Inf，稳定性分最高只能为 60。")
        weak_rows = sorted([row for row in rows if row.normalized_score < 60], key=lambda row: row.normalized_score)
        for row in weak_rows[:3]:
            risks.append(f"{row.metric_name} 偏弱，当前分数 {row.normalized_score:.0f}。")
        return risks or ["当前未发现阻断性风险，仍建议用真实业务 eval set 复测。"]

    def _recommendation(self, grade: str, rows: list[MetricScoreRow], risk_notes: list[str]) -> str:
        lowest = sorted(rows, key=lambda row: row.normalized_score)[:2]
        if grade in {"Excellent", "Good"} and lowest:
            return f"{GRADE_TEXT[grade]}建议继续优化 {lowest[0].metric_name} 和 {lowest[-1].metric_name}。"
        return GRADE_TEXT[grade]


def build_metric_table_rows(result: EmbeddingScoreResult) -> list[dict[str, Any]]:
    return [row.as_dict() for row in result.metric_rows]


def build_model_comparison_rows(results: list[EmbeddingScoreResult]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for result in results:
        metric_map = {row.metric_key: row for row in result.metric_rows}
        rows.append(
            {
                "model_name": result.model_name,
                "provider": result.provider,
                "dimension": result.dimension,
                "max_input_length": result.max_input_length,
                "overall_score": result.overall_score,
                "grade": result.grade,
                "retrieval_quality_score": result.retrieval_quality_score,
                "semantic_separation_score": result.semantic_separation_score,
                "rag_context_quality_score": result.rag_context_quality_score,
                "engineering_quality_score": result.engineering_quality_score,
                "recall_at_5": _metric_score(metric_map, "recall_at_5"),
                "ndcg_at_10": _metric_score(metric_map, "ndcg_at_10"),
                "mrr_at_10": _metric_score(metric_map, "mrr_at_10"),
                "precision_at_5": _metric_score(metric_map, "precision_at_5"),
                "hard_negative_margin": _metric_current(metric_map, "hard_negative_margin"),
                "avg_latency": _metric_current(metric_map, "avg_latency_score"),
                "p95_latency": _metric_current(metric_map, "p95_latency_score"),
                "cost_per_1k_chunks": _metric_current(metric_map, "cost_score"),
                "storage_per_1k_chunks": _metric_current(metric_map, "storage_score"),
                "need_reindex": result.need_reindex,
                "recommended_use": result.recommended_use,
                "operation": "查看详情 / 设为当前模型 / 创建新 collection / 重建索引 / 导出报告",
            }
        )
    return rows


def summarize_model_recommendations(results: list[EmbeddingScoreResult]) -> dict[str, str]:
    if not results:
        return {
            "best_overall": "-",
            "quality_first": "-",
            "cost_first": "-",
            "local_deployment": "-",
            "api_deployment": "-",
        }
    best_overall = max(results, key=lambda item: item.overall_score)
    quality_first = max(results, key=lambda item: item.retrieval_quality_score * 0.65 + item.rag_context_quality_score * 0.25 + item.semantic_separation_score * 0.10)
    cost_first = max(results, key=lambda item: item.engineering_quality_score * 0.65 + item.overall_score * 0.35)
    local_candidates = [item for item in results if "local" in item.provider.lower() or "bge" in item.model_name.lower() or "qwen" in item.model_name.lower()]
    api_candidates = [item for item in results if item.provider.lower() in {"openai", "custom_api", "api"} or "embedding-3" in item.model_name]
    local_best = max(local_candidates or results, key=lambda item: item.overall_score)
    api_best = max(api_candidates or results, key=lambda item: item.overall_score)
    return {
        "best_overall": best_overall.model_name,
        "quality_first": quality_first.model_name,
        "cost_first": cost_first.model_name,
        "local_deployment": local_best.model_name,
        "api_deployment": api_best.model_name,
    }


class EmbeddingReportExporter:
    def to_json(self, result: EmbeddingScoreResult, comparisons: list[EmbeddingScoreResult] | None = None) -> str:
        payload = {
            "result": result.as_dict(),
            "comparison": build_model_comparison_rows(comparisons or []),
            "recommendations": summarize_model_recommendations(comparisons or [result]),
        }
        return json.dumps(payload, ensure_ascii=False, indent=2)

    def to_csv(self, result: EmbeddingScoreResult) -> str:
        output = io.StringIO()
        fieldnames = [
            "metric_name",
            "current_value",
            "normalized_score",
            "weight",
            "weighted_score",
            "judgement",
            "explanation",
            "suggestion",
        ]
        writer = csv.DictWriter(output, fieldnames=fieldnames)
        writer.writeheader()
        for row in result.metric_rows:
            writer.writerow({key: row.as_dict()[key] for key in fieldnames})
        return output.getvalue()

    def to_markdown(self, result: EmbeddingScoreResult, comparisons: list[EmbeddingScoreResult] | None = None) -> str:
        progress = "#" * int(round(result.overall_score / 5))
        progress = progress.ljust(20, ".")
        lines = [
            f"# Embedding 模型评分报告: {result.model_name}",
            "",
            "## 模型信息",
            f"- Provider: {result.provider}",
            f"- 维度: {result.dimension}",
            f"- 最大输入长度: {result.max_input_length}",
            "",
            "## 综合评分",
            f"- 综合评分: {result.overall_score:.0f} / 100",
            f"- 等级: {result.grade}",
            f"- 进度条: [{progress}] {result.overall_score:.0f}%",
            f"- 检索质量: {result.retrieval_quality_score:.0f}",
            f"- 语义区分度: {result.semantic_separation_score:.0f}",
            f"- 上下文质量: {result.rag_context_quality_score:.0f}",
            f"- 工程可用性: {result.engineering_quality_score:.0f}",
            "",
            "## 指标表格",
            "| 指标 | 当前值 | 归一化分数 | 权重 | 加权得分 | 判断 | 解释 | 建议 |",
            "|---|---:|---:|---:|---:|---|---|---|",
        ]
        for row in result.metric_rows:
            lines.append(
                f"| {row.metric_name} | {row.current_value} | {row.normalized_score:.0f} | "
                f"{row.weight:.2f} | {row.weighted_score:.2f} | {row.judgement} | "
                f"{row.explanation} | {row.suggestion} |"
            )
        comparison_rows = build_model_comparison_rows(comparisons or [])
        if comparison_rows:
            lines.extend(
                [
                    "",
                    "## 模型对比表",
                    "| 模型 | Provider | 维度 | 综合评分 | 等级 | Recall@5 | nDCG@10 | MRR@10 | 推荐用途 |",
                    "|---|---|---:|---:|---|---:|---:|---:|---|",
                ]
            )
            for row in comparison_rows:
                lines.append(
                    f"| {row['model_name']} | {row['provider']} | {row['dimension']} | "
                    f"{row['overall_score']:.0f} | {row['grade']} | {row['recall_at_5']:.0f} | "
                    f"{row['ndcg_at_10']:.0f} | {row['mrr_at_10']:.0f} | {row['recommended_use']} |"
                )
        lines.extend(
            [
                "",
                "## 自然语言解释",
                result.natural_language_explanation,
                "",
                "## 风险提示",
                *[f"- {note}" for note in result.risk_notes],
                "",
                "## 推荐动作",
                result.recommendation,
            ]
        )
        return "\n".join(lines)

    def to_html(self, result: EmbeddingScoreResult, comparisons: list[EmbeddingScoreResult] | None = None) -> str:
        color = grade_color(result.grade)
        metric_rows = "\n".join(
            "<tr>"
            f"<td>{html.escape(row.metric_name)}</td>"
            f"<td>{html.escape(row.current_value)}</td>"
            f"<td>{row.normalized_score:.0f}</td>"
            f"<td>{row.weight:.2f}</td>"
            f"<td>{row.weighted_score:.2f}</td>"
            f"<td>{html.escape(row.judgement)}</td>"
            f"<td>{html.escape(row.explanation)}</td>"
            f"<td>{html.escape(row.suggestion)}</td>"
            "</tr>"
            for row in result.metric_rows
        )
        comparison_rows = "\n".join(
            "<tr>"
            f"<td>{html.escape(str(row['model_name']))}</td>"
            f"<td>{html.escape(str(row['provider']))}</td>"
            f"<td>{row['dimension']}</td>"
            f"<td>{row['overall_score']:.0f}</td>"
            f"<td>{html.escape(str(row['grade']))}</td>"
            f"<td>{html.escape(str(row['recommended_use']))}</td>"
            "</tr>"
            for row in build_model_comparison_rows(comparisons or [])
        )
        return f"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <title>Embedding 模型评分报告</title>
  <style>
    body {{ font-family: Arial, "Microsoft YaHei", sans-serif; margin: 32px; color: #1f2933; }}
    .bar {{ width: 100%; height: 18px; background: #e5e7eb; border-radius: 8px; overflow: hidden; }}
    .fill {{ width: {result.overall_score:.0f}%; height: 100%; background: {color}; }}
    table {{ border-collapse: collapse; width: 100%; margin-top: 16px; font-size: 13px; }}
    th, td {{ border: 1px solid #d8dee9; padding: 8px; text-align: left; vertical-align: top; }}
    th {{ background: #f3f6fb; }}
    .score {{ font-size: 28px; font-weight: 700; }}
  </style>
</head>
<body>
  <h1>Embedding 模型评分报告: {html.escape(result.model_name)}</h1>
  <div class="score">{result.overall_score:.0f} / 100 {html.escape(result.grade)}</div>
  <div class="bar"><div class="fill"></div></div>
  <p>{html.escape(result.natural_language_explanation)}</p>
  <h2>子评分</h2>
  <ul>
    <li>检索质量: {result.retrieval_quality_score:.0f}</li>
    <li>语义区分度: {result.semantic_separation_score:.0f}</li>
    <li>RAG 上下文质量: {result.rag_context_quality_score:.0f}</li>
    <li>工程可用性: {result.engineering_quality_score:.0f}</li>
  </ul>
  <h2>指标表格</h2>
  <table>
    <thead><tr><th>指标</th><th>当前值</th><th>归一化分数</th><th>权重</th><th>加权得分</th><th>判断</th><th>解释</th><th>建议</th></tr></thead>
    <tbody>{metric_rows}</tbody>
  </table>
  <h2>模型对比</h2>
  <table>
    <thead><tr><th>模型</th><th>Provider</th><th>维度</th><th>综合评分</th><th>等级</th><th>推荐用途</th></tr></thead>
    <tbody>{comparison_rows}</tbody>
  </table>
  <h2>风险提示</h2>
  <ul>{"".join(f"<li>{html.escape(note)}</li>" for note in result.risk_notes)}</ul>
  <h2>推荐动作</h2>
  <p>{html.escape(result.recommendation)}</p>
</body>
</html>"""


def export_report(path: str | Path, result: EmbeddingScoreResult, comparisons: list[EmbeddingScoreResult] | None = None) -> None:
    exporter = EmbeddingReportExporter()
    report_path = Path(path)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    suffix = report_path.suffix.lower()
    if suffix == ".json":
        content = exporter.to_json(result, comparisons)
    elif suffix == ".md":
        content = exporter.to_markdown(result, comparisons)
    elif suffix == ".csv":
        content = exporter.to_csv(result)
    elif suffix in {".html", ".htm"}:
        content = exporter.to_html(result, comparisons)
    else:
        raise ValueError(f"Unsupported report format: {suffix}")
    report_path.write_text(content, encoding="utf-8")


def mock_embedding_eval_inputs(model_name: str = "BAAI/bge-m3", provider: str = "local_bge") -> dict[str, Any]:
    if model_name == "mock-embedding":
        factor = 0.68
        dimension = 128
        latency = 120
        p95 = 260
        cost = 0.0
    elif "large" in model_name:
        factor = 0.86
        dimension = 3072
        latency = 720
        p95 = 1900
        cost = 0.13
    elif "small" in model_name:
        factor = 0.79
        dimension = 1536
        latency = 420
        p95 = 1000
        cost = 0.02
    else:
        factor = 0.83
        dimension = 1024
        latency = 520
        p95 = 1280
        cost = 0.01
    return {
        "model_info": {"model_name": model_name, "provider": provider, "dimension": dimension, "max_input_length": 8192},
        "similarity_test_result": {
            "pair_accuracy": min(0.96, factor + 0.03),
            "hard_negative_margin": max(0.04, factor - 0.74),
            "positive_scores": [0.78, 0.81, 0.85, min(0.92, factor + 0.10)],
            "negative_scores": [0.18, 0.22, 0.25, 0.28],
            "hard_negative_scores": [0.56, 0.59, 0.63, max(0.55, factor - 0.10)],
        },
        "retrieval_benchmark_result": {
            "recall_at_5": factor,
            "ndcg_at_10": max(0.45, factor - 0.05),
            "mrr_at_10": max(0.42, factor - 0.12),
            "hit_at_1": max(0.35, factor - 0.18),
            "precision_at_5": max(0.40, factor - 0.09),
        },
        "rag_context_result": {
            "context_recall": max(0.50, factor - 0.02),
            "context_precision": max(0.45, factor - 0.08),
            "citation_support_rate": max(0.55, factor - 0.03),
        },
        "engineering_result": {
            "avg_latency_ms": latency,
            "p95_latency_ms": p95,
            "cost_per_1k_chunks": cost,
            "dimension": dimension,
            "failure_rate": 0.01,
        },
    }


def calculate_mock_result(model_name: str = "BAAI/bge-m3", provider: str = "local_bge", weights_config: dict[str, Any] | None = None) -> EmbeddingScoreResult:
    config = weights_config or load_weights_config()
    inputs = mock_embedding_eval_inputs(model_name=model_name, provider=provider)
    return EmbeddingScoreCalculator().calculate(weights_config=config, **inputs)


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


def recommended_use_for_grade(grade: str) -> str:
    return {
        "Excellent": "生产级企业知识库",
        "Good": "企业知识库试运行",
        "Usable": "Demo 或低风险场景",
        "Weak": "仅用于诊断，不建议上线",
        "Failed": "不建议使用",
    }[grade]


def generate_natural_language_explanation(result: EmbeddingScoreResult) -> str:
    rows = result.metric_rows
    strong = sorted(rows, key=lambda row: row.normalized_score, reverse=True)[:2]
    weak = sorted(rows, key=lambda row: row.normalized_score)[:2]
    strong_text = "、".join(row.metric_name for row in strong)
    weak_text = "、".join(row.metric_name for row in weak)
    suggestion = weak[0].suggestion if weak else result.recommendation
    text = (
        f"{result.model_name} 在当前知识库测试集中综合评分为 {result.overall_score:.0f}/100，等级 {result.grade}。"
        f"优势在 {strong_text}，说明相关证据召回或工程表现较稳。"
        f"短板是 {weak_text}，建议{suggestion}"
    )
    return text[:200]


def grade_color(grade: str) -> str:
    return {
        "Excellent": "#16803c",
        "Good": "#2f80ed",
        "Usable": "#d9822b",
        "Weak": "#c2410c",
        "Failed": "#b42318",
    }.get(grade, "#64748b")


def clamp(value: float, minimum: float = 0.0, maximum: float = 100.0) -> float:
    return max(minimum, min(maximum, value))


def scale_to_score(value: float) -> float:
    if value <= 1.0:
        return clamp(value * 100.0)
    return clamp(value)


def percentile(values: list[float], percent: float) -> float:
    if not values:
        return 0.0
    sorted_values = sorted(values)
    if len(sorted_values) == 1:
        return sorted_values[0]
    position = (len(sorted_values) - 1) * percent / 100.0
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        return sorted_values[int(position)]
    fraction = position - lower
    return sorted_values[lower] * (1 - fraction) + sorted_values[upper] * fraction


def _metric_score(metric_map: dict[str, MetricScoreRow], key: str) -> float:
    row = metric_map.get(key)
    return row.normalized_score if row else 0.0


def _metric_current(metric_map: dict[str, MetricScoreRow], key: str) -> str:
    row = metric_map.get(key)
    return row.current_value if row else ""
