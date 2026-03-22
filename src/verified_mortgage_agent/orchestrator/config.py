"""Provider-agnostic LLM factory.

Resolution order per agent:
  1. LLM_MODEL_<AGENT>  (e.g. LLM_MODEL_UNDERWRITER=anthropic/claude-sonnet-4-6)
  2. LLM_MODEL           (global fallback)
  3. DEFAULT_MODEL        (hardcoded default)

Uses ``langchain.chat_models.init_chat_model`` so any provider supported by
LangChain works without provider-specific imports in agent code.
"""

from __future__ import annotations

import os
from functools import lru_cache

from langchain.chat_models import init_chat_model
from langchain_core.language_models import BaseChatModel

DEFAULT_MODEL = "anthropic/claude-haiku-3-5"


def _resolve_model_id(agent_name: str) -> str:
    """Determine which model to use for *agent_name*."""
    env_key = f"LLM_MODEL_{agent_name.upper()}"
    return os.environ.get(env_key) or os.environ.get("LLM_MODEL") or DEFAULT_MODEL


@lru_cache(maxsize=16)
def get_llm(agent_name: str) -> BaseChatModel:
    """Return a cached ``BaseChatModel`` for the given agent role."""
    model_id = _resolve_model_id(agent_name)
    return init_chat_model(model_id)


def get_model_id(agent_name: str) -> str:
    """Return the resolved model identifier string for *agent_name*."""
    return _resolve_model_id(agent_name)
