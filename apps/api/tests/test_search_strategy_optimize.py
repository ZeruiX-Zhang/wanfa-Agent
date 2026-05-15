"""Tests for SearchStrategyEngine.optimize_query_with_model()."""

from __future__ import annotations

import os
import tempfile
from unittest.mock import patch, MagicMock

import pytest


@pytest.fixture(autouse=True)
def _isolate_storage():
    """Ensure tests use an isolated SQLite database."""
    with tempfile.TemporaryDirectory(prefix="reality-os-search-test-", ignore_cleanup_errors=True) as tmp_dir:
        storage_path = os.path.join(tmp_dir, "test_knowledge.sqlite3")
        os.environ["REALITY_OS_API_STORAGE"] = storage_path
        os.environ.setdefault("REALITY_OS_ENV", "development")

        # Reset singletons
        import apps.api.app.knowledge_core as kc_mod
        import apps.api.app.model_registry as mr_mod

        old_core = kc_mod._CORE
        old_registry = mr_mod._REGISTRY
        kc_mod._CORE = None
        mr_mod._REGISTRY = None

        yield

        kc_mod._CORE = old_core
        mr_mod._REGISTRY = old_registry


def _make_engine():
    """Create a SearchStrategyEngine with no skills directory."""
    from apps.api.app.search_strategy import SearchStrategyEngine
    from pathlib import Path

    # Use a non-existent directory so no skills are loaded
    return SearchStrategyEngine(skills_dir=Path("__nonexistent_skills__"))


class TestOptimizeQueryWithModelSuccess:
    """Tests for successful model-based query optimization."""

    def test_returns_optimized_query_and_expanded_terms(self):
        """When model returns valid structured response, parse it correctly."""
        from apps.api.app.model_registry import ModelCallResult

        mock_response = (
            "优化查询: 深度学习模型训练优化技巧\n"
            "同义词: 深度学习, 神经网络, 机器学习\n"
            "相关概念: 梯度下降, 超参数调优, 正则化\n"
            "精确搜索词: 模型训练, 训练优化, 学习率调整"
        )
        mock_result = ModelCallResult(
            ok=True,
            content=mock_response,
            slot="generator",
            provider_id="openai",
            model_name="gpt-4o",
            status="completed",
            cost_estimate=0.5,
        )

        engine = _make_engine()

        with patch("apps.api.app.model_registry.call_model", return_value=mock_result):
            optimized_query, expanded_terms = engine.optimize_query_with_model(
                query="深度学习训练",
                language="zh-CN",
            )

        assert optimized_query == "深度学习模型训练优化技巧"
        assert "深度学习" in expanded_terms
        assert "神经网络" in expanded_terms
        assert "梯度下降" in expanded_terms
        assert "模型训练" in expanded_terms
        assert len(expanded_terms) == 9  # 3 synonyms + 3 related + 3 precise

    def test_english_response_parsing(self):
        """When model returns English structured response, parse it correctly."""
        from apps.api.app.model_registry import ModelCallResult

        mock_response = (
            "Optimized Query: deep learning model training optimization techniques\n"
            "Synonyms: neural network, machine learning, AI training\n"
            "Related Concepts: gradient descent, hyperparameter tuning, regularization\n"
            "Precise Terms: model training, training optimization, learning rate"
        )
        mock_result = ModelCallResult(
            ok=True,
            content=mock_response,
            slot="generator",
            provider_id="openai",
            model_name="gpt-4o",
            status="completed",
            cost_estimate=0.3,
        )

        engine = _make_engine()

        with patch("apps.api.app.model_registry.call_model", return_value=mock_result):
            optimized_query, expanded_terms = engine.optimize_query_with_model(
                query="deep learning training",
                language="en",
            )

        assert optimized_query == "deep learning model training optimization techniques"
        assert "neural network" in expanded_terms
        assert "gradient descent" in expanded_terms
        assert "model training" in expanded_terms


class TestOptimizeQueryWithModelFallback:
    """Tests for fallback behavior when model is unavailable."""

    def test_fallback_on_model_not_configured(self):
        """When model returns None (not configured), fall back to tokenize."""
        from apps.api.app.model_registry import ModelCallResult

        mock_result = ModelCallResult(
            ok=False,
            content=None,
            slot="generator",
            provider_id=None,
            model_name=None,
            status="not_configured",
            error_type="not_configured",
            error="Slot 'generator' is not configured or disabled.",
        )

        engine = _make_engine()

        with patch("apps.api.app.model_registry.call_model", return_value=mock_result):
            optimized_query, expanded_terms = engine.optimize_query_with_model(
                query="深度学习训练技巧",
                language="zh-CN",
            )

        # Fallback: optimized_query is None
        assert optimized_query is None
        # expanded_terms should contain meaningful tokens from the query
        assert isinstance(expanded_terms, list)

    def test_fallback_on_model_exception(self):
        """When model call raises an exception, fall back to tokenize."""
        engine = _make_engine()

        with patch("apps.api.app.model_registry.call_model", side_effect=Exception("Connection timeout")):
            optimized_query, expanded_terms = engine.optimize_query_with_model(
                query="AI model optimization",
                language="en",
            )

        assert optimized_query is None
        assert isinstance(expanded_terms, list)

    def test_fallback_on_empty_model_response(self):
        """When model returns empty content, fall back to tokenize."""
        from apps.api.app.model_registry import ModelCallResult

        mock_result = ModelCallResult(
            ok=True,
            content="",
            slot="generator",
            provider_id="openai",
            model_name="gpt-4o",
            status="empty_response",
        )

        engine = _make_engine()

        with patch("apps.api.app.model_registry.call_model", return_value=mock_result):
            optimized_query, expanded_terms = engine.optimize_query_with_model(
                query="machine learning",
                language="en",
            )

        assert optimized_query is None
        assert isinstance(expanded_terms, list)

    def test_fallback_on_unparseable_response(self):
        """When model returns unstructured text, fall back to tokenize."""
        from apps.api.app.model_registry import ModelCallResult

        mock_result = ModelCallResult(
            ok=True,
            content="This is just random text without any structure.",
            slot="generator",
            provider_id="openai",
            model_name="gpt-4o",
            status="completed",
        )

        engine = _make_engine()

        with patch("apps.api.app.model_registry.call_model", return_value=mock_result):
            optimized_query, expanded_terms = engine.optimize_query_with_model(
                query="test query",
                language="en",
            )

        # Unparseable response triggers fallback
        assert optimized_query is None
        assert isinstance(expanded_terms, list)


class TestOptimizeQueryTracing:
    """Tests for trace recording during query optimization."""

    def test_records_trace_step_on_success(self):
        """Successful model call records trace steps."""
        from apps.api.app.model_registry import ModelCallResult

        mock_response = (
            "优化查询: 优化后的查询\n"
            "同义词: 词1, 词2\n"
            "相关概念: 概念1\n"
            "精确搜索词: 关键词1"
        )
        mock_result = ModelCallResult(
            ok=True,
            content=mock_response,
            slot="generator",
            provider_id="openai",
            model_name="gpt-4o",
            status="completed",
            cost_estimate=0.2,
        )

        engine = _make_engine()

        with patch("apps.api.app.model_registry.call_model", return_value=mock_result):
            with patch("apps.api.app.trace.record_step") as mock_trace:
                engine.optimize_query_with_model(
                    query="测试查询",
                    language="zh-CN",
                    run_id="run_test123",
                )

        # Should have recorded at least 2 steps: running + complete
        assert mock_trace.call_count >= 2
        # First call: running step
        first_call = mock_trace.call_args_list[0]
        assert first_call.kwargs["step_type"] == "query_optimization"
        assert first_call.kwargs["status"] == "running"
        # Second call: complete step
        second_call = mock_trace.call_args_list[1]
        assert second_call.kwargs["step_type"] == "query_optimization_complete"
        assert second_call.kwargs["status"] == "completed"

    def test_records_trace_step_on_fallback(self):
        """Fallback records a fallback trace step."""
        from apps.api.app.model_registry import ModelCallResult

        mock_result = ModelCallResult(
            ok=False,
            content=None,
            slot="generator",
            provider_id=None,
            model_name=None,
            status="not_configured",
            error_type="not_configured",
            error="Not configured",
        )

        engine = _make_engine()

        with patch("apps.api.app.model_registry.call_model", return_value=mock_result):
            with patch("apps.api.app.trace.record_step") as mock_trace:
                engine.optimize_query_with_model(
                    query="test",
                    language="en",
                    run_id="run_fallback",
                )

        # Should have recorded at least 2 steps: running + fallback
        assert mock_trace.call_count >= 2
        last_call = mock_trace.call_args_list[-1]
        assert last_call.kwargs["step_type"] == "query_optimization_fallback"


class TestParseQueryOptimizationResponse:
    """Tests for the response parsing logic."""

    def test_parse_chinese_response_with_chinese_colons(self):
        """Parse response with Chinese full-width colons."""
        from apps.api.app.search_strategy import SearchStrategyEngine
        from pathlib import Path

        engine = SearchStrategyEngine(skills_dir=Path("__nonexistent__"))

        response = (
            "优化查询：更精确的搜索\n"
            "同义词：词A，词B，词C\n"
            "相关概念：概念X、概念Y\n"
            "精确搜索词：关键词1；关键词2"
        )
        result = engine._parse_query_optimization_response(response)
        assert result is not None
        optimized, terms = result
        assert optimized == "更精确的搜索"
        assert "词A" in terms
        assert "词B" in terms
        assert "概念X" in terms
        assert "关键词1" in terms

    def test_parse_partial_response_only_synonyms(self):
        """Parse response with only synonyms (no optimized query)."""
        from apps.api.app.search_strategy import SearchStrategyEngine
        from pathlib import Path

        engine = SearchStrategyEngine(skills_dir=Path("__nonexistent__"))

        response = "同义词: 词1, 词2, 词3"
        result = engine._parse_query_optimization_response(response)
        assert result is not None
        optimized, terms = result
        assert optimized == ""  # No optimized query found
        assert len(terms) == 3

    def test_parse_empty_response_returns_none(self):
        """Empty or completely unstructured response returns None."""
        from apps.api.app.search_strategy import SearchStrategyEngine
        from pathlib import Path

        engine = SearchStrategyEngine(skills_dir=Path("__nonexistent__"))

        assert engine._parse_query_optimization_response("") is None
        assert engine._parse_query_optimization_response("random text") is None
