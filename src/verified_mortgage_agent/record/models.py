"""Decision record models — the cross-system contract between Python and Lean 4.

These types are serialized to JSON and consumed by `lake exe verify-trace`.
Any schema change requires a version bump in SCHEMA_VERSION and a corresponding
update to lean/MortgageVerifier/Types.lean.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from pydantic import BaseModel, Field

from verified_mortgage_agent.domain.enums import (
    DocumentType,
    RoutingOutcome,
    SessionOutcome,
)
from verified_mortgage_agent.domain.models import (
    ApplicantSituation,
    MortgageApplication,
    MortgageGoal,
    MortgagePackageProposal,
)

SCHEMA_VERSION = "1.0.0"
DESIGN_SESSION_SCHEMA_VERSION = "2.0.0"


class ReasoningStep(BaseModel):
    """A single step in an agent's reasoning chain."""

    step_index: int = Field(ge=0)
    description: str
    inputs_considered: list[str] = Field(default_factory=list)
    # Formal rule cited, e.g. "DTI_CAP_CONVENTIONAL" — must match an invariant name in Lean
    rule_cited: str | None = None


class RoutingDecision(BaseModel):
    """A single agent's routing decision, including its full reasoning chain."""

    decision_id: uuid.UUID = Field(default_factory=uuid.uuid4)
    application_id: uuid.UUID
    # Which agent produced this decision
    agent_name: str
    outcome: RoutingOutcome
    reasoning_steps: list[ReasoningStep] = Field(default_factory=list)
    confidence_score: float = Field(ge=0.0, le=1.0)
    documents_requested: list[DocumentType] = Field(default_factory=list)
    escalation_reason: str | None = None
    decided_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    # Which LLM produced this decision (e.g. "anthropic/claude-sonnet-4-6")
    model_id: str


class DecisionRecord(BaseModel):
    """Complete record of all decisions made while processing one application.

    `decisions` is what Lean formally verifies.
    `routing_steps` records inter-agent routing steps (auditable, not formally proven).
    """

    record_id: uuid.UUID = Field(default_factory=uuid.uuid4)
    # Bump when the schema changes; Lean rejects mismatched versions with exit code 2
    schema_version: str = SCHEMA_VERSION
    application: MortgageApplication
    decisions: list[RoutingDecision] = Field(default_factory=list)
    # Router reasoning steps — separate from formally-verified decisions
    routing_steps: list[ReasoningStep] = Field(default_factory=list)
    final_outcome: RoutingOutcome
    generated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    # Model used by the authoritative (underwriter) agent
    model_id: str


class DesignSessionRecord(BaseModel):
    """Complete record of a Phase 4 generative design session.

    Schema v2.0.0 — Python-only; the Lean binary never processes this type.
    Every positive outcome is PENDING_REVIEW (requires human loan officer
    sign-off); no path auto-approves.

    ``verification_skipped=True`` means the Lean binary was unavailable during
    the session.  A PENDING_REVIEW record with this flag set must not be treated
    as conditionally approvable until Lean is re-run.
    """

    session_id: uuid.UUID = Field(default_factory=uuid.uuid4)
    schema_version: str = DESIGN_SESSION_SCHEMA_VERSION
    situation: ApplicantSituation
    goal: MortgageGoal
    # One entry per iteration
    proposals: list[MortgagePackageProposal] = Field(default_factory=list)
    # Lean violation strings per iteration (empty list = passed)
    lean_feedback_history: list[list[str]] = Field(default_factory=list)
    # package_reviewer concerns per iteration (empty list = no concerns)
    reviewer_concerns_history: list[list[str]] = Field(default_factory=list)
    final_outcome: SessionOutcome
    # Set when final_outcome == PENDING_REVIEW
    accepted_proposal: MortgagePackageProposal | None = None
    # Set when final_outcome == HARD_BLOCK or DOCUMENTS_REQUIRED
    block_reason: str | None = None
    # Actionable steps for HARD_BLOCK / DOCUMENTS_REQUIRED outcomes
    qualification_path: list[str] = Field(default_factory=list)
    # Set when final_outcome == ESCALATED; summary for the senior underwriter
    escalation_context: str | None = None
    # True when the Lean binary was unavailable during the session
    verification_skipped: bool = False
    generated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
