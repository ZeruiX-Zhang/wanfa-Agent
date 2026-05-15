from __future__ import annotations

import json

from fastapi.testclient import TestClient


def test_trace_metadata_and_errors_are_redacted(client: TestClient) -> None:
    from apps.api.app import trace

    secret = "sk-traceprivacy123456789"
    raw_prompt = "customer Alice account 12345 wants private pricing"
    run_id = trace.start_run(
        tenant_id="local",
        user_id="privacy-test",
        entrypoint="trace_privacy",
        input_value={"prompt": raw_prompt, "api_key": secret},
        metadata={
            "language": "en",
            "api_key": secret,
            "prompt": raw_prompt,
            "nested": {
                "authorization": f"Bearer {secret}",
                "result_count": 3,
            },
            "items": [{"token": secret}, "safe-label"],
        },
    )
    trace.record_step(
        run_id=run_id,
        step_type="privacy_step",
        input_value={"content": raw_prompt},
        output_value={"answer": raw_prompt},
        error=f"prompt: {raw_prompt}; api_key={secret}",
        metadata={"content": raw_prompt, "fetch_mode": "mock"},
    )
    trace.record_model_call(
        run_id=run_id,
        step_id=None,
        slot="generator",
        provider_id="openai",
        model_name="test-model",
        status="failed",
        started_at="2026-05-12T00:00:00+00:00",
        ended_at="2026-05-12T00:00:01+00:00",
        latency_ms=100,
        input_value=raw_prompt,
        output_value=None,
        error_type="network",
        error=f"Authorization: Bearer {secret}",
        metadata={"output": raw_prompt, "retryable": True},
    )
    trace.record_acceptance_check(
        run_id=run_id,
        step_id=None,
        verdict="needs_revision",
        verifier_used=False,
        input_value=raw_prompt,
        output_value={"private_content": raw_prompt},
        error=f"question: {raw_prompt}",
        metadata={"goal_fit_passed": False, "question": raw_prompt},
    )
    trace.record_audit_result(
        run_id=run_id,
        passed=False,
        score=0.1,
        source="unit",
        output_type="answer",
        input_value=raw_prompt,
        output_value=raw_prompt,
        metadata={"safe_count": 1, "password": secret},
    )
    trace.finish_run(
        run_id,
        status="failed",
        output_value={"content": raw_prompt},
        error=f"password={secret}; content={raw_prompt}",
    )

    payload = trace.get_run(run_id)
    assert payload is not None
    dumped = json.dumps(payload, ensure_ascii=False)
    assert secret not in dumped
    assert raw_prompt not in dumped
    assert payload["run"]["metadata"]["language"] == "en"
    assert payload["run"]["metadata"]["api_key"] == "[redacted]"
    assert payload["run"]["metadata"]["nested"]["authorization"] == "[redacted]"
    assert payload["steps"][0]["metadata"]["fetch_mode"] == "mock"
    assert payload["steps"][0]["metadata"]["content"] == "[redacted]"
