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


# ---------------------------------------------------------------------------
# Phase 4 design-loop structured outputs
# ---------------------------------------------------------------------------


class PackageProposalOutput(BaseModel):
    """Structured output from the package_designer agent."""

    loan_type: str  # LoanType value — validated on conversion
    principal_usd: str  # Decimal-safe string
    term_years: int
    estimated_rate_pct: str  # Decimal-safe string
    rationale: str
    customer_benefit: str
    estimated_monthly_pi: str  # Decimal-safe string
    special_considerations: list[str] = Field(default_factory=list)


class PackageReviewOutput(BaseModel):
    """Advisory output from the package_reviewer agent.

    The graph always proceeds to lean_verify regardless of verdict.
    """

    verdict: str  # "ACCEPT" or "REVISE"
    concerns: list[str] = Field(default_factory=list)
    suggested_principal_usd: str | None = None  # Decimal-safe string or None
    suggested_term_years: int | None = None
