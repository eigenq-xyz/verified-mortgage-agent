"""Tests for orchestrator/config.py — model resolution."""

from __future__ import annotations

import pytest

from verified_mortgage_agent.orchestrator.config import get_model_id


def test_default_model_returned_when_no_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("LLM_MODEL", raising=False)
    monkeypatch.delenv("LLM_MODEL_INTAKE", raising=False)
    model_id = get_model_id("intake")
    assert "/" in model_id  # provider/model format


def test_global_env_override(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LLM_MODEL", "openai/gpt-4o-mini")
    monkeypatch.delenv("LLM_MODEL_INTAKE", raising=False)
    assert get_model_id("intake") == "openai/gpt-4o-mini"


def test_agent_specific_env_override(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LLM_MODEL", "openai/gpt-4o-mini")
    monkeypatch.setenv("LLM_MODEL_UNDERWRITER", "anthropic/claude-sonnet-4-6")
    assert get_model_id("underwriter") == "anthropic/claude-sonnet-4-6"
    # Other agents still get global
    monkeypatch.delenv("LLM_MODEL_INTAKE", raising=False)
    assert get_model_id("intake") == "openai/gpt-4o-mini"
