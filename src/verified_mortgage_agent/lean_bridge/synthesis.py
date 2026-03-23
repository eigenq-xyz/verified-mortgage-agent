"""Synthesize a v1 DecisionRecord from a Phase 4 package proposal.

The Lean binary hard-checks ``EXPECTED_SCHEMA_VERSION = "1.0.0"`` and never
sees a ``DesignSessionRecord``.  To verify a proposal against the existing
Lean invariants, Python wraps it in a minimal v1 ``DecisionRecord``
(outcome=APPROVE, single underwriter decision) and passes that through the
unchanged ``verify-trace`` binary.

This synthesis is intentionally lossy in the other direction: the
``DesignSessionRecord`` (v2.0.0) carries far more context than Lean needs.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from verified_mortgage_agent.domain.enums import PropertyType, RoutingOutcome
from verified_mortgage_agent.domain.models import (
    ApplicantSituation,
    LoanRequest,
    MortgageApplication,
    MortgageGoal,
    MortgagePackageProposal,
    Property,
)
from verified_mortgage_agent.record.models import (
    SCHEMA_VERSION,
    DecisionRecord,
    ReasoningStep,
    RoutingDecision,
)

# Placeholder used when a specific address is not available pre-closing.
_PLACEHOLDER_ADDRESS = "[address to be provided at closing]"

# Model ID stamped on the synthesised record — not produced by a live LLM call.
_SYNTHESIS_MODEL_ID = "synthesis/lean-bridge-v1"


def synthesize_record_from_proposal(
    proposal: MortgagePackageProposal,
    situation: ApplicantSituation,
    goal: MortgageGoal,
) -> DecisionRecord:
    """Wrap a proposal as a v1 DecisionRecord (outcome=APPROVE) for Lean.

    The synthesised record satisfies the Lean parser requirements:
    - ``schema_version`` is exactly ``"1.0.0"``
    - a single underwriter decision with outcome APPROVE
    - DTI/LTV are derived from the proposal's principal, the situation's
      income/debts, and the goal's property price (used as appraised value)

    ``property_type`` defaults to ``SINGLE_FAMILY``; no current Lean invariant
    checks it.  ``requested_rate_pct`` is left null.
    """
    applicant = situation.to_applicant()

    property_ = Property(
        address=_PLACEHOLDER_ADDRESS,
        appraised_value_usd=goal.target_property_price,
        property_type=PropertyType.SINGLE_FAMILY,
    )

    loan = LoanRequest(
        principal_usd=proposal.principal_usd,
        term_years=proposal.term_years,
        loan_type=proposal.loan_type,
        requested_rate_pct=None,
    )

    application_id = uuid.uuid4()
    application = MortgageApplication(
        id=application_id,
        applicant=applicant,
        property=property_,
        loan=loan,
        submitted_at=datetime.now(UTC),
        provided_documents=[],
    )

    now = datetime.now(UTC)
    decision = RoutingDecision(
        application_id=application_id,
        agent_name="underwriter",
        outcome=RoutingOutcome.APPROVE,
        reasoning_steps=[
            ReasoningStep(
                step_index=0,
                description=(
                    f"Synthesised from proposal iteration {proposal.iteration}: "
                    f"{proposal.loan_type} {proposal.principal_usd} "
                    f"over {proposal.term_years}yr"
                ),
            )
        ],
        confidence_score=1.0,
        decided_at=now,
        model_id=_SYNTHESIS_MODEL_ID,
    )

    return DecisionRecord(
        application=application,
        decisions=[decision],
        routing_steps=[],
        final_outcome=RoutingOutcome.APPROVE,
        generated_at=now,
        model_id=_SYNTHESIS_MODEL_ID,
        schema_version=SCHEMA_VERSION,
    )
