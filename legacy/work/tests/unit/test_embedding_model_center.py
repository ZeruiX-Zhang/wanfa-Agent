from __future__ import annotations

import json
from pathlib import Path

from rag_core.embedding_model_center import (
    CollectionMetadata,
    EmbeddingConnectionTester,
    EmbeddingModelComparator,
    EmbeddingModelReportExporter,
    EmbeddingModelSpec,
    EmbeddingRetrievalBenchmark,
    EmbeddingSimilarityTester,
    ModelRegistry,
    has_nan_inf,
    hit_at_k,
    mrr_at_k,
    ndcg_at_k,
    precision_at_k,
    recall_at_k,
)


def test_model_registry_reads_default_models(tmp_path: Path):
    registry = ModelRegistry(tmp_path / "embedding_models.yaml", tmp_path / "collection.json")
    ids = {model.model_id for model in registry.list_models()}
    assert {
        "bge_m3",
        "qwen3_embedding_0_6b",
        "qwen3_embedding_4b",
        "openai_text_embedding_3_small",
        "openai_text_embedding_3_large",
        "custom_api_template",
    }.issubset(ids)


def test_custom_model_save_and_load(tmp_path: Path):
    registry = ModelRegistry(tmp_path / "embedding_models.yaml", tmp_path / "collection.json")
    model = EmbeddingModelSpec(
        model_id="custom_finance_embedding",
        display_name="Custom Finance Embedding",
        provider="custom_api",
        base_url="http://127.0.0.1:9000/v1",
        endpoint="/embeddings",
        api_key_env="CUSTOM_EMBEDDING_API_KEY",
        model="finance-embedding",
        dimension=768,
        max_input_tokens=4096,
        distance_metric="cosine",
    )
    registry.upsert(model)
    loaded = registry.get("custom_finance_embedding")
    assert loaded.display_name == "Custom Finance Embedding"
    assert loaded.dimension == 768


def test_single_embedding_dimension_check(tmp_path: Path):
    registry = ModelRegistry(tmp_path / "embedding_models.yaml", tmp_path / "collection.json")
    model = registry.get("bge_m3")
    result = EmbeddingConnectionTester().test_model(model)
    assert result["single_embedding_test"]["dimension"] == 1024
    assert not result["single_embedding_test"]["contains_nan_inf"]


def test_nan_inf_detection():
    assert has_nan_inf([0.1, float("nan")])
    assert has_nan_inf([0.1, float("inf")])
    assert not has_nan_inf([0.1, 0.2])


def test_pair_similarity_metrics(tmp_path: Path):
    registry = ModelRegistry(tmp_path / "embedding_models.yaml", tmp_path / "collection.json")
    result = EmbeddingSimilarityTester().run(registry.get("bge_m3"))
    assert "positive_avg_similarity" in result
    assert "pair_accuracy" in result
    assert result["conclusion"] in {"Excellent", "Good", "Weak", "Failed"}
    assert len(result["pair_rows"]) == 9


def test_retrieval_metric_functions():
    relevance = [False, True, False, True, False, True]
    assert hit_at_k(relevance, 1) == 0
    assert hit_at_k(relevance, 3) == 1
    assert recall_at_k(relevance, 3, 5) == 2 / 3
    assert precision_at_k(relevance, 5) == 2 / 5
    assert mrr_at_k(relevance, 10) == 0.5
    assert ndcg_at_k(relevance, 10) > 0


def test_collection_dimension_mismatch_blocks_write(tmp_path: Path):
    registry = ModelRegistry(tmp_path / "embedding_models.yaml", tmp_path / "collection.json")
    model = registry.get("openai_text_embedding_3_small")
    metadata = CollectionMetadata(
        collection_name="enterprise_kb_demo",
        embedding_model_id="bge_m3",
        provider="local_bge",
        dimension=1024,
        distance_metric="cosine",
        normalize_embeddings=True,
        created_at="2026-05-07T00:00:00Z",
        chunk_count=10,
        doc_count=2,
    )
    compatibility = metadata.compatibility_with(model)
    assert compatibility["need_reindex"]
    assert not compatibility["can_write"]


def test_switch_model_need_reindex_true(tmp_path: Path):
    registry = ModelRegistry(tmp_path / "embedding_models.yaml", tmp_path / "collection.json")
    registry.save_collection_metadata(
        CollectionMetadata(
            collection_name="enterprise_kb_demo",
            embedding_model_id="bge_m3",
            provider="local_bge",
            dimension=1024,
            distance_metric="cosine",
            normalize_embeddings=True,
            created_at="2026-05-07T00:00:00Z",
            chunk_count=10,
            doc_count=2,
        )
    )
    result = registry.set_active("openai_text_embedding_3_small")
    assert result["need_reindex"]
    assert "重建向量索引" in result["message"]


def test_mock_embedding_full_test_flow(tmp_path: Path):
    registry = ModelRegistry(tmp_path / "embedding_models.yaml", tmp_path / "collection.json")
    mock = EmbeddingModelSpec(
        model_id="mock_embedding_test",
        display_name="Mock Embedding Test",
        provider="mock",
        model="mock-embedding",
        dimension=128,
        max_input_tokens=2048,
    )
    registry.upsert(mock)
    connection = EmbeddingConnectionTester().test_model(mock)
    similarity = EmbeddingSimilarityTester().run(mock)
    retrieval = EmbeddingRetrievalBenchmark(tmp_path / "embedding_retrieval_eval.jsonl").run(mock)
    comparison = EmbeddingModelComparator(tmp_path / "embedding_eval.yaml").compare([mock])
    assert connection["available"]
    assert similarity["pair_rows"]
    assert retrieval["case_count"] >= 1
    assert comparison["rows"][0]["model_id"] == "mock_embedding_test"


def test_report_export_json_markdown_csv(tmp_path: Path):
    payload = {
        "recommendations": {"综合推荐模型": "BGE-M3"},
        "rows": [{"model_id": "bge_m3", "overall_score": 82.5, "grade": "Good"}],
    }
    exporter = EmbeddingModelReportExporter()
    json_text = exporter.to_json(payload)
    md_text = exporter.to_markdown(payload)
    csv_text = exporter.to_csv(payload["rows"])
    assert json.loads(json_text)["rows"][0]["model_id"] == "bge_m3"
    assert "Embedding Model Center Report" in md_text
    assert "model_id" in csv_text
