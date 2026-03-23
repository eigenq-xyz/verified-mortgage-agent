"""End-to-end integration tests for the Phase 4 generative design loop.

Tests the full graph with mocked LLMs and mocked Lean binary so the suite
runs without any external dependencies.

Scenario A — two-iteration correction loop:
  Iteration 1: designer proposes a DTI-violating package
                → mocked Lean returns a dtiCapConventional violation
  Iteration 2: designer corrects to a passing package
                → mocked Lean returns no violations
  Expected outcome: PENDING_REVIEW, accepted_proposal set, 2 proposals

Scenario B — stage-1 hard block:
  Existing debt >= monthly income (DTI ≥ 1.0)
  Expected outcome: HARD_BLOCK (no LLM calls, no Lean calls)

Scenario C — escalation after max iterations:
  All iterations produce violations; max_iterations=2
  Expected outcome: ESCALATED after 2 iterations
"""

from __future__ import annotations

from decimal import Decimal
from unittest.mock import MagicMock, patch

import pytest

from verified_mortgage_agent.domain.enums import (
    EmploymentStatus,
    GoalPriority,
    SessionOutcome,
)
from verified_mortgage_agent.domain.models import (
    ApplicantSituation,
    MortgageGoal,
)
from verified_mortgage_agent.lean_bridge.result import VerificationResult, Violation
from verified_mortgage_agent.orchestrator.runner import run_design_sync
from verified_mortgage_agent.orchestrator.tools import (
    PackageProposalOutput,
    PackageReviewOutput,
)

_DESIGNER_MODULE = "verified_mortgage_agent.orchestrator.agents.package_designer.get_llm"
_REVIEWER_MODULE = "verified_mortgage_agent.orchestrator.agents.package_reviewer.get_llm"
_ESCALATION_MODULE = "verified_mortgage_agent.orchestrator.graph.get_llm"
_VERIFY_MODULE = "verified_mortgage_agent.orchestrator.graph.verify_proposal"

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def situation() -> ApplicantSituation:
    return ApplicantSituation(
        name="Alice Nguyen",
        annual_income_usd=Decimal("95000"),
        credit_score=720,
        employment_status=EmploymentStatus.EMPLOYED,
        debt_obligations_monthly_usd=Decimal("400"),
        assets_liquid_usd=Decimal("60000"),
        employment_months_current=36,
    )


@pytest.fixture
def goal() -> MortgageGoal:
    return MortgageGoal(
        target_property_price=Decimal("450000"),
        available_down_payment=Decimal("45000"),
        desired_max_monthly_payment=Decimal("2200"),
        priority=GoalPriority.MINIMIZE_MONTHLY_PAYMENT,
    )


def _designer_mock(proposal_output: PackageProposalOutput) -> MagicMock:
    """Build a mock get_llm() for the package designer."""
    structured = MagicMock()
    structured.invoke.return_value = proposal_output
    llm = MagicMock()
    llm.with_structured_output.return_value = structured
    return llm


def _reviewer_mock(verdict: str = "ACCEPT") -> MagicMock:
    """Build a mock get_llm() for the package reviewer."""
    output = PackageReviewOutput(verdict=verdict, concerns=[])
    structured = MagicMock()
    structured.invoke.return_value = output
    llm = MagicMock()
    llm.with_structured_output.return_value = structured
    return llm


def _lean_violation_result(*invariant_names: str) -> VerificationResult:
    violations = [
        Violation(invariant_name=n, description=f"violated: {n}")
        for n in invariant_names
    ]
    return VerificationResult(passed=False, record_id="test", violations=violations)


_LEAN_PASS = VerificationResult(passed=True, record_id="test", violations=[])


# ---------------------------------------------------------------------------
# Scenario A: two-iteration correction loop → PENDING_REVIEW
# ---------------------------------------------------------------------------


def test_design_loop_corrects_dti_violation_and_produces_pending_review(
    situation: ApplicantSituation,
    goal: MortgageGoal,
) -> None:
    """Iter 1 violates DTI; iter 2 corrects it → PENDING_REVIEW."""
    # Iteration 1 proposal: over-leveraged (will violate DTI)
    proposal_iter1 = PackageProposalOutput(
        loan_type="CONVENTIONAL",
        principal_usd="500000",  # DTI violation territory
        term_years=30,
        estimated_rate_pct="6.75",
        rationale="First attempt",
        customer_benefit="Lower rate",
        estimated_monthly_pi="3240",
    )
    # Iteration 2 proposal: corrected principal
    proposal_iter2 = PackageProposalOutput(
        loan_type="CONVENTIONAL",
        principal_usd="380000",
        term_years=30,
        estimated_rate_pct="6.75",
        rationale="Corrected after DTI feedback",
        customer_benefit="Affordable payment",
        estimated_monthly_pi="2465",
    )

    call_count = {"n": 0}

    def designer_factory(_agent_name: str) -> MagicMock:
        call_count["n"] += 1
        if call_count["n"] == 1:
            return _designer_mock(proposal_iter1)
        return _designer_mock(proposal_iter2)

    def lean_factory(*_args, **_kwargs) -> VerificationResult:
        # First call: violation; subsequent: pass
        if call_count["n"] <= 1:
            return _lean_violation_result("dtiCapConventional")
        return _LEAN_PASS

    lean_call_count = {"n": 0}

    def lean_side_effect(*_args, **_kwargs) -> VerificationResult:
        lean_call_count["n"] += 1
        if lean_call_count["n"] == 1:
            return _lean_violation_result("dtiCapConventional")
        return _LEAN_PASS

    with (
        patch(_DESIGNER_MODULE, side_effect=designer_factory),
        patch(_REVIEWER_MODULE, return_value=_reviewer_mock()),
        patch(_VERIFY_MODULE, side_effect=lean_side_effect),
    ):
        record = run_design_sync(situation, goal, max_iterations=3)

    assert record.final_outcome == SessionOutcome.PENDING_REVIEW
    assert record.accepted_proposal is not None
    assert len(record.proposals) == 2
    assert record.verification_skipped is False
    # First iteration feedback recorded
    assert len(record.lean_feedback_history) == 2
    assert "dtiCapConventional" in record.lean_feedback_history[0][0]
    assert record.lean_feedback_history[1] == []


def test_pending_review_record_has_correct_schema_version(
    situation: ApplicantSituation,
    goal: MortgageGoal,
) -> None:
    proposal = PackageProposalOutput(
        loan_type="CONVENTIONAL",
        principal_usd="380000",
        term_years=30,
        estimated_rate_pct="6.75",
        rationale="ok",
        customer_benefit="ok",
        estimated_monthly_pi="2465",
    )

    with (
        patch(_DESIGNER_MODULE, return_value=_designer_mock(proposal)),
        patch(_REVIEWER_MODULE, return_value=_reviewer_mock()),
        patch(_VERIFY_MODULE, return_value=_LEAN_PASS),
    ):
        record = run_design_sync(situation, goal, max_iterations=3)

    assert record.schema_version == "2.0.0"
    assert record.situation.name == situation.name
    assert record.goal.target_property_price == goal.target_property_price


# ---------------------------------------------------------------------------
# Scenario B: Stage-1 hard block — no LLM calls
# ---------------------------------------------------------------------------


def test_hard_block_when_existing_dti_is_100_percent(
    goal: MortgageGoal,
) -> None:
    """Existing debt >= income → HARD_BLOCK before any LLM is called."""
    blocked_situation = ApplicantSituation(
        name="Carl Overloaded",
        annual_income_usd=Decimal("36000"),
        credit_score=680,
        employment_status=EmploymentStatus.EMPLOYED,
        debt_obligations_monthly_usd=Decimal("3000"),  # DTI = 1.0
        assets_liquid_usd=Decimal("5000"),
        employment_months_current=12,
    )

    with (
        patch(_DESIGNER_MODULE) as mock_designer,
        patch(_REVIEWER_MODULE) as mock_reviewer,
        patch(_VERIFY_MODULE) as mock_lean,
    ):
        record = run_design_sync(blocked_situation, goal, max_iterations=3)

    assert record.final_outcome == SessionOutcome.HARD_BLOCK
    assert record.block_reason is not None
    assert len(record.qualification_path) > 0
    # No LLM or Lean calls should have been made
    mock_designer.assert_not_called()
    mock_reviewer.assert_not_called()
    mock_lean.assert_not_called()


# ---------------------------------------------------------------------------
# Scenario C: Escalation after max iterations
# ---------------------------------------------------------------------------


def test_escalated_after_max_iterations(
    situation: ApplicantSituation,
    goal: MortgageGoal,
) -> None:
    """All iterations produce violations → ESCALATED after max_iterations=2."""
    proposal = PackageProposalOutput(
        loan_type="CONVENTIONAL",
        principal_usd="500000",
        term_years=30,
        estimated_rate_pct="6.75",
        rationale="attempt",
        customer_benefit="n/a",
        estimated_monthly_pi="3240",
    )

    escalation_llm = MagicMock()
    escalation_msg = MagicMock()
    escalation_msg.content = "DTI violations persist across 2 iterations. Recommend specialist review."
    escalation_llm.invoke.return_value = escalation_msg

    with (
        patch(_DESIGNER_MODULE, return_value=_designer_mock(proposal)),
        patch(_REVIEWER_MODULE, return_value=_reviewer_mock()),
        patch(_VERIFY_MODULE, return_value=_lean_violation_result("dtiCapConventional")),
        patch(_ESCALATION_MODULE, return_value=escalation_llm),
    ):
        record = run_design_sync(situation, goal, max_iterations=2)

    assert record.final_outcome == SessionOutcome.ESCALATED
    assert len(record.proposals) == 2
    assert record.escalation_context is not None
    assert all(len(fb) > 0 for fb in record.lean_feedback_history)


# ---------------------------------------------------------------------------
# Scenario D: Lean binary unavailable → verification_skipped=True
# ---------------------------------------------------------------------------


def test_verification_skipped_when_lean_binary_missing(
    situation: ApplicantSituation,
    goal: MortgageGoal,
) -> None:
    """When Lean binary is absent, graph treats as pass and sets verification_skipped."""
    from verified_mortgage_agent.lean_bridge.runner import LeanBinaryNotFoundError

    proposal = PackageProposalOutput(
        loan_type="CONVENTIONAL",
        principal_usd="380000",
        term_years=30,
        estimated_rate_pct="6.75",
        rationale="ok",
        customer_benefit="ok",
        estimated_monthly_pi="2465",
    )

    with (
        patch(_DESIGNER_MODULE, return_value=_designer_mock(proposal)),
        patch(_REVIEWER_MODULE, return_value=_reviewer_mock()),
        patch(_VERIFY_MODULE, side_effect=LeanBinaryNotFoundError("binary not found")),
    ):
        record = run_design_sync(situation, goal, max_iterations=3)

    assert record.final_outcome == SessionOutcome.PENDING_REVIEW
    assert record.verification_skipped is True
