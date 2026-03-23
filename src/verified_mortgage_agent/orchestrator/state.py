"""LangGraph state definitions for the mortgage orchestrators."""

from __future__ import annotations

import operator
from typing import Annotated, Literal, TypedDict

from verified_mortgage_agent.domain.enums import RoutingOutcome, SessionOutcome
from verified_mortgage_agent.domain.models import (
    ApplicantSituation,
    MortgageApplication,
    MortgageGoal,
    MortgagePackageProposal,
)
from verified_mortgage_agent.record.models import (
    DecisionRecord,
    DesignSessionRecord,
    ReasoningStep,
    RoutingDecision,
)

AgentName = Literal[
    "intake",
    "risk_assessment",
    "compliance",
    "underwriter",
]


class GraphState(TypedDict):
    """State for the LangGraph mortgage orchestrator.

    Uses ``Annotated[list, operator.add]`` reducers so parallel branches
    (risk + compliance) accumulate decisions without race conditions.
    """

    application: MortgageApplication
    decisions: Annotated[list[RoutingDecision], operator.add]
    routing_steps: Annotated[list[ReasoningStep], operator.add]
    next_agent: AgentName | Literal["END"] | None
    escalation_required: bool
    escalation_reason: str | None
    final_outcome: RoutingOutcome | None
    record: DecisionRecord | None


class DesignGraphState(TypedDict):
    """State for the Phase 4 generative design-loop orchestrator.

    Stage 1: feasibility_gate sets stage_1_outcome to short-circuit the loop.
    Stage 2: package_designer → package_reviewer → lean_verify loop.
    Stage 3: assemble_* nodes seal the DesignSessionRecord.
    """

    # ---- Inputs ----
    situation: ApplicantSituation
    goal: MortgageGoal
    max_iterations: int

    # ---- Stage 1 ----
    # Set only when feasibility_gate finds a blocking condition.
    stage_1_outcome: SessionOutcome | None
    missing_documents: list[str]       # populated on DOCUMENTS_REQUIRED
    block_reason: str | None
    qualification_path: list[str]

    # ---- Stage 2 iteration state ----
    iteration: int
    current_proposal: MortgagePackageProposal | None
    reviewer_concerns: list[str]       # advisory, from current iteration
    lean_feedback: list[str]           # violations from lean_verify this iter
    verification_skipped: bool

    # ---- Accumulators ----
    # operator.add on list[list[str]] concatenates the outer lists, so each
    # node returning ["all_lean_feedback": [violations]] accumulates correctly:
    # [[iter1_violations]] + [[iter2_violations]] → [[v1], [v2]]
    all_proposals: Annotated[list[MortgagePackageProposal], operator.add]
    all_lean_feedback: Annotated[list[list[str]], operator.add]
    all_reviewer_concerns: Annotated[list[list[str]], operator.add]

    # ---- Stage 3 ----
    session_outcome: SessionOutcome | None
    accepted_proposal: MortgagePackageProposal | None
    escalation_context: str | None

    # ---- Final sealed record ----
    record: DesignSessionRecord | None
