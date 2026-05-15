from __future__ import annotations

from pathlib import Path

import yaml

from rag_core.embedding_eval import (
    EmbeddingReportExporter,
    EmbeddingScoreCalculator,
    apply_weight_profile,
    build_metric_table_rows,
    build_model_comparison_rows,
    export_report,
    load_weights_config,
    need_reindex_for_model,
    normalize_weights_config,
    save_weight_profile,
    save_weights_config,
    validate_weights_config,
)


def sample_inputs() -> dict:
    return {
        "similarity_test_result": {
            "pair_accuracy": 0.88,
            "hard_negative_margin": 0.09,
            "positive_scores": [0.80, 0.82, 0.84, 0.86],
            "negative_scores": [0.20, 0.25, 0.27, 0.30],
            "hard_negative_scores": [0.55, 0.58, 0.60, 0.62],
        },
        "retrieval_benchmark_result": {
            "recall_at_5": 0.86,
            "ndcg_at_10": 0.79,
            "mrr_at_10": 0.78,
            "hit_at_1": 0.72,
            "precision_at_5": 0.74,
        },
        "rag_context_result": {
            "context_recall": 0.80,
            "context_precision": 0.78,
            "citation_support_rate": 0.83,
        },
        "engineering_result": {
            "avg_latency_ms": 620,
            "p95_latency_ms": 1700,
            "cost_per_1k_chunks": 0.03,
            "dimension": 1024,
            "failure_rate": 0.02,
        },
        "model_info": {"model_name": "BAAI/bge-m3", "provider": "local_bge", "dimension": 1024, "max_input_length": 8192},
    }


def calculate_sample():
    config = load_weights_config()
    return EmbeddingScoreCalculator().calculate(weights_config=config, **sample_inputs())


def test_weighted_score_calculation():
    result = calculate_sample()
    weighted_sum = round(sum(row.weighted_score for row in result.metric_rows), 2)
    assert result.overall_score == weighted_sum
    assert result.retrieval_quality_score > result.semantic_separation_score


def test_weight_sum_validation():
    config = load_weights_config()
    validation = validate_weights_config(config)
    assert validation.is_valid
    assert validation.category_total == 100
    assert validation.metric_total == 100


def test_weight_normalization():
    config = load_weights_config()
    config["retrieval_quality"]["weight"] = 100
    normalized = normalize_weights_config(config)
    validation = validate_weights_config(normalized)
    assert validation.is_valid
    assert validation.category_total == 100
    assert validation.metric_total == 100


def test_hard_negative_margin_normalization():
    calculator = EmbeddingScoreCalculator()
    assert calculator.normalize_hard_negative_margin(0.21) == 100
    assert calculator.normalize_hard_negative_margin(0.13) == 80
    assert calculator.normalize_hard_negative_margin(0.09) == 60
    assert calculator.normalize_hard_negative_margin(0.05) == 40
    assert calculator.normalize_hard_negative_margin(0.01) == 20


def test_latency_score_calculation():
    calculator = EmbeddingScoreCalculator()
    assert calculator.latency_score(400, 500) == 100
    assert round(calculator.latency_score(1000, 500), 2) == 50


def test_cost_score_calculation():
    calculator = EmbeddingScoreCalculator()
    assert calculator.cost_score(0, 0.02) == 100
    assert round(calculator.cost_score(0.04, 0.02), 2) == 50


def test_grade_judgement_and_failed_dimension():
    inputs = sample_inputs()
    inputs["engineering_result"]["dimension_mismatch"] = True
    result = EmbeddingScoreCalculator().calculate(weights_config=load_weights_config(), **inputs)
    assert result.grade == "Failed"
    assert result.overall_score < 45


def test_metric_table_data_generation():
    result = calculate_sample()
    rows = build_metric_table_rows(result)
    assert rows
    assert {"metric_name", "current_value", "normalized_score", "weight", "weighted_score", "judgement", "explanation", "suggestion"}.issubset(rows[0])


def test_model_comparison_table_data_generation():
    result = calculate_sample()
    second_inputs = sample_inputs()
    second_inputs["model_info"] = {"model_name": "text-embedding-3-small", "provider": "openai", "dimension": 1536, "max_input_length": 8192}
    second_inputs["retrieval_benchmark_result"]["recall_at_5"] = 0.78
    second = EmbeddingScoreCalculator().calculate(weights_config=load_weights_config(), **second_inputs)
    rows = build_model_comparison_rows([result, second])
    assert len(rows) == 2
    assert rows[0]["operation"]
    assert "recall_at_5" in rows[0]


def test_report_export_json_markdown_csv_html(tmp_path: Path):
    result = calculate_sample()
    exporter = EmbeddingReportExporter()
    assert "综合评分" in exporter.to_markdown(result, [result])
    assert "metric_name" in exporter.to_csv(result)
    assert "Embedding 模型评分报告" in exporter.to_html(result, [result])
    assert '"overall_score"' in exporter.to_json(result, [result])
    for suffix in ["json", "md", "csv", "html"]:
        path = tmp_path / f"report.{suffix}"
        export_report(path, result, [result])
        assert path.exists()
        assert path.read_text(encoding="utf-8")


def test_weight_profile_save_and_load(tmp_path: Path):
    config = load_weights_config()
    config = save_weight_profile(
        config,
        "custom_quality",
        {
            "retrieval_quality": 60,
            "semantic_separation": 15,
            "rag_context_quality": 15,
            "engineering_quality": 10,
        },
        "test profile",
    )
    save_weights_config(config, tmp_path / "weights.yaml")
    loaded = load_weights_config(tmp_path / "weights.yaml")
    applied = apply_weight_profile(loaded, "custom_quality")
    validation = validate_weights_config(applied)
    assert validation.is_valid
    assert applied["active_profile"] == "custom_quality"
    assert yaml.safe_load((tmp_path / "weights.yaml").read_text(encoding="utf-8"))["profiles"]["custom_quality"]


def test_model_switch_need_reindex_hint():
    assert need_reindex_for_model("BAAI/bge-m3", 1024, "text-embedding-3-small", 1536)
    assert not need_reindex_for_model("BAAI/bge-m3", 1024, "BAAI/bge-m3", 1024)
