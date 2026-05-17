"""Unit test for API key masking (Task 6.4, Property 25, R18.4).

``ModelConfig.to_dict(mask_key=True)`` must never return the plaintext
API key — only ``api_key_configured: bool`` and a short ``api_key_preview``
(<= 11 characters).
"""

from __future__ import annotations

from apps.api.app.model_registry import ModelConfig


def _config(api_key: str) -> ModelConfig:
    return ModelConfig(
        slot="generator",
        provider_id="openai",
        base_url="https://api.example.com",
        api_key=api_key,
        model_name="demo-model",
    )


def test_property_25_api_key_mask_to_dict_never_returns_raw() -> None:
    """The masked dict never echoes the raw key and the preview is short."""

    secret = "sk-abcdefghijklmnopqrstuvwxyz0123456789"
    payload = _config(secret).to_dict(mask_key=True)

    # The raw secret never appears anywhere in the serialised payload.
    assert secret not in repr(payload)
    assert payload["api_key_configured"] is True
    assert "api_key" not in payload  # only the *_configured / *_preview keys

    preview = payload["api_key_preview"]
    assert isinstance(preview, str)
    assert len(preview) <= 11
    assert preview != secret
    # The preview reveals at most the first/last 4 chars, never the middle.
    assert secret[8:-8] not in preview


def test_property_25_empty_key_reports_unconfigured() -> None:
    """An empty key reports ``api_key_configured=False`` and a blank preview."""

    payload = _config("").to_dict(mask_key=True)
    assert payload["api_key_configured"] is False
    assert payload["api_key_preview"] == ""


def test_property_25_short_key_is_not_split_revealed() -> None:
    """A short key falls back to ``***`` rather than leaking its characters."""

    payload = _config("sk-12345").to_dict(mask_key=True)
    assert payload["api_key_preview"] == "***"
    assert len(payload["api_key_preview"]) <= 11
