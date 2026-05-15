from __future__ import annotations

from app.models.schemas import (
    ContextBudget,
    PromptLabCompareResponse,
    PromptLabComparison,
    PromptLabComparisonScores,
    PromptLabTestResponse,
)
from app.providers.factory import build_provider
from app.providers.mock import MockProvider
from app.services.settings_service import SettingsService


class PromptLabService:
    def __init__(self, settings_service: SettingsService | None = None) -> None:
        self.settings_service = settings_service or SettingsService()

    def test_prompt(self, prompt: str, test_input: str, model_override: str | None = None) -> PromptLabTestResponse:
        model, privacy = self.settings_service.get_model_settings()
        if model_override:
            model.model = model_override
        provider = build_provider(model, privacy)
        provider_info = self.settings_service.provider_info()
        if isinstance(provider, MockProvider):
            output = provider.generate(
                [
                    {"role": "system", "content": "Prompt Lab Test"},
                    {"role": "user", "content": f"提示词：\n{prompt}\n\n测试输入：\n{test_input}"},
                ]
            )
        else:
            try:
                output = provider.generate(
                    [
                        {"role": "system", "content": prompt},
                        {"role": "user", "content": test_input or "请根据系统提示执行一次最小测试。"},
                    ],
                    {"temperature": 0.2, "max_tokens": 1200, "timeout": 45},
                )
            except Exception as exc:  # noqa: BLE001
                raise RuntimeError(self.settings_service.sanitize_error(str(exc))) from exc
        return PromptLabTestResponse(
            ok=True,
            output=output,
            provider_info=provider_info,
            token_budget=self._budget(prompt, test_input, output),
        )

    def compare_prompts(self, original_prompt: str, optimized_prompt: str, test_input: str) -> PromptLabCompareResponse:
        original = self.test_prompt(original_prompt, test_input)
        optimized = self.test_prompt(optimized_prompt, test_input)
        comparison = self._compare(original_prompt, optimized_prompt, original.output, optimized.output)
        return PromptLabCompareResponse(
            ok=True,
            original_output=original.output,
            optimized_output=optimized.output,
            comparison=comparison,
        )

    def _compare(self, original_prompt: str, optimized_prompt: str, original_output: str, optimized_output: str) -> PromptLabComparison:
        original_score = _prompt_score(original_prompt) + _output_score(original_output)
        optimized_score = _prompt_score(optimized_prompt) + _output_score(optimized_output)
        if optimized_score > original_score:
            winner = "optimized"
            reason = "优化后的提示词包含更明确的目标、上下文、约束和输出格式。"
        elif original_score > optimized_score:
            winner = "original"
            reason = "原始提示词在当前测试中更直接或更贴近输入。"
        else:
            winner = "tie"
            reason = "两版提示词在当前简单评分下接近，建议增加更多测试案例。"
        return PromptLabComparison(
            winner=winner,  # type: ignore[arg-type]
            reason=reason,
            scores=PromptLabComparisonScores(
                clarity=min(10, _prompt_score(optimized_prompt) * 2),
                specificity=min(10, optimized_score),
                usefulness=min(10, _output_score(optimized_output) * 2),
            ),
        )

    def _budget(self, prompt: str, test_input: str, output: str) -> ContextBudget:
        budget = ContextBudget(
            used_skill_tokens=_estimate_tokens(prompt),
            used_memory_tokens=_estimate_tokens(test_input),
            used_knowledge_tokens=0,
            used_graph_tokens=0,
        )
        budget.used_total_estimate = (
            budget.used_skill_tokens
            + budget.used_memory_tokens
            + budget.used_knowledge_tokens
            + budget.used_graph_tokens
            + _estimate_tokens(output)
        )
        return budget


def _prompt_score(prompt: str) -> int:
    checks = ["角色", "任务", "目标", "上下文", "约束", "输出格式", "质量", "验收", "步骤"]
    lowered = prompt.lower()
    return sum(1 for item in checks if item in prompt or item.lower() in lowered)


def _output_score(output: str) -> int:
    checks = ["结论", "步骤", "假设", "验收", "建议", "结果"]
    return sum(1 for item in checks if item in output)


def _estimate_tokens(text: str) -> int:
    cleaned = (text or "").strip()
    if not cleaned:
        return 0
    return max(1, len(cleaned) // 4)

