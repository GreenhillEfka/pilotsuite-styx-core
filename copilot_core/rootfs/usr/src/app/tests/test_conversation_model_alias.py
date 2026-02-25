"""Tests for OpenAI conversation model alias normalization."""

from __future__ import annotations

import pytest

from copilot_core.api.v1.conversation import normalize_requested_model


def test_model_alias_pilotsuite_maps_to_configured_ollama_model(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("OLLAMA_MODEL", "qwen3:4b")
    assert normalize_requested_model("pilotsuite") == "primary"


def test_model_alias_local_maps_to_offline_selector() -> None:
    assert normalize_requested_model("local") == "offline"


def test_model_alias_cloud_maps_to_cloud_selector() -> None:
    assert normalize_requested_model("cloud") == "cloud"


def test_non_alias_model_is_preserved() -> None:
    assert normalize_requested_model("gpt-4o-mini") == "gpt-4o-mini"
