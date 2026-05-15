from __future__ import annotations

from tests.conftest import client


def test_prompt_lab_test_api_returns_provider_and_budget() -> None:
    response = client.post(
        "/api/prompt-lab/test",
        json={"prompt": "请按步骤输出结论和验收标准。", "test_input": "把一个想法改成任务说明。"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["ok"] is True
    assert "本地模拟模型" in body["output"]
    assert body["provider_info"]["active_provider"] == "mock"
    assert body["token_budget"]["used_total_estimate"] >= 1


def test_prompt_lab_compare_api_returns_scores() -> None:
    response = client.post(
        "/api/prompt-lab/compare",
        json={
            "original_prompt": "帮我写一下。",
            "optimized_prompt": "请按角色、任务、上下文、约束、输出格式和验收标准生成结果。",
            "test_input": "生成产品需求说明。",
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["ok"] is True
    assert body["original_output"]
    assert body["optimized_output"]
    assert body["comparison"]["winner"] in {"original", "optimized", "tie"}
    assert set(body["comparison"]["scores"]) == {"clarity", "specificity", "usefulness"}

