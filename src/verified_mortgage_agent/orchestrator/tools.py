"""Pydantic structured-output schemas for agent responses.

Each agent returns a structured response that gets converted into
a ``RoutingDecision`` for the decision record.
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from verified_mortgage_agent.domain.enums import DocumentType, RoutingOutcome


class ReasoningStepOutput(BaseModel):
    """A single reasoning step produced by an agent."""

    description: str
    inputs_considered: list[str] = Field(default_factory=list)
    rule_cited: str | None = None


class AgentResponse(BaseModel):
    """Structured output expected from every agent."""

    outcome: RoutingOutcome
    reasoning_steps: list[ReasoningStepOutput] = Field(default_factory=list)
    confidence_score: float = Field(ge=0.0, le=1.0)
    documents_requested: list[DocumentType] = Field(default_factory=list)
    escalation_reason: str | None = None
