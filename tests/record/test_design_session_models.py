"""Unit tests for Phase 4 domain models and DesignSessionRecord."""

from __future__ import annotations

import json
from decimal import Decimal

import pytest

from verified_mortgage_agent.domain.enums import (
    EmploymentStatus,
    GoalPriority,
    LoanType,
    SessionOutcome,
)
from verified_mortgage_agent.domain.models import (
    ApplicantSituation,
    MortgageGoal,
    MortgagePackageProposal,
)
from verified_mortgage_agent.record.design_session_io import (
    DesignSessionSchemaVersionError,
    loads,
    serialize,
)
from verified_mortgage_agent.record.models import (
    DESIGN_SESSION_SCHEMA_VERSION,
    DesignSessionRecord,
)

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
        ownership_horizon_years=10,
        priority=GoalPriority.MINIMIZE_MONTHLY_PAYMENT,
    )


@pytest.fixture
def proposal(situation: ApplicantSituation) -> MortgagePackageProposal:
    return MortgagePackageProposal(
        loan_type=LoanType.CONVENTIONAL,
        principal_usd=Decimal("405000"),
        term_years=30,
        estimated_rate_pct=Decimal("6.75"),
        rationale="30-year term minimises monthly payment",
        customer_benefit="Lowest possible monthly obligation at current rates",
        estimated_monthly_pi=Decimal("2627"),
        iteration=1,
    )


@pytest.fixture
def pending_review_record(
    situation: ApplicantSituation,
    goal: MortgageGoal,
    proposal: MortgagePackageProposal,
) -> DesignSessionRecord:
    return DesignSessionRecord(
        situation=situation,
        goal=goal,
        proposals=[proposal],
        lean_feedback_history=[[]],
        reviewer_concerns_history=[[]],
        final_outcome=SessionOutcome.PENDING_REVIEW,
        accepted_proposal=proposal,
    )


# ---------------------------------------------------------------------------
# ApplicantSituation
# ---------------------------------------------------------------------------


def test_applicant_situation_monthly_income(situation: ApplicantSituation) -> None:
    assert situation.monthly_income_usd == Decimal("95000") / 12


def test_applicant_situation_to_applicant(situation: ApplicantSituation) -> None:
    applicant = situation.to_applicant()
    assert applicant.name == situation.name
    assert applicant.annual_income_usd == situation.annual_income_usd
    assert applicant.credit_score == situation.credit_score
    assert applicant.employment_status == situation.employment_status
    assert (
        applicant.debt_obligations_monthly_usd
        == situation.debt_obligations_monthly_usd
    )


def test_applicant_situation_to_applicant_no_extra_fields(
    situation: ApplicantSituation,
) -> None:
    """to_applicant() must not carry phase-4-only fields into the v1 model."""
    applicant = situation.to_applicant()
    assert not hasattr(applicant, "assets_liquid_usd")
    assert not hasattr(applicant, "employment_months_current")


# ---------------------------------------------------------------------------
# MortgageGoal defaults
# ---------------------------------------------------------------------------


def test_goal_default_priority() -> None:
    goal = MortgageGoal(
        target_property_price=Decimal("300000"),
        available_down_payment=Decimal("30000"),
    )
    assert goal.priority == GoalPriority.BALANCED


def test_goal_optional_fields_default_none() -> None:
    goal = MortgageGoal(
        target_property_price=Decimal("300000"),
        available_down_payment=Decimal("30000"),
    )
    assert goal.desired_max_monthly_payment is None
    assert goal.ownership_horizon_years is None


# ---------------------------------------------------------------------------
# MortgagePackageProposal validation
# ---------------------------------------------------------------------------


def test_proposal_invalid_term_year() -> None:
    with pytest.raises(ValueError, match="term_years must be one of"):
        MortgagePackageProposal(
            loan_type=LoanType.CONVENTIONAL,
            principal_usd=Decimal("300000"),
            term_years=7,  # invalid
            estimated_rate_pct=Decimal("6.5"),
            rationale="bad term",
            customer_benefit="n/a",
            estimated_monthly_pi=Decimal("1800"),
            iteration=1,
        )


@pytest.mark.parametrize("term", [10, 15, 20, 25, 30])
def test_proposal_valid_term_years(term: int) -> None:
    p = MortgagePackageProposal(
        loan_type=LoanType.FHA,
        principal_usd=Decimal("200000"),
        term_years=term,
        estimated_rate_pct=Decimal("5.5"),
        rationale="ok",
        customer_benefit="ok",
        estimated_monthly_pi=Decimal("1200"),
        iteration=1,
    )
    assert p.term_years == term


# ---------------------------------------------------------------------------
# DesignSessionRecord
# ---------------------------------------------------------------------------


def test_design_session_record_schema_version(
    pending_review_record: DesignSessionRecord,
) -> None:
    assert pending_review_record.schema_version == DESIGN_SESSION_SCHEMA_VERSION
    assert pending_review_record.schema_version == "2.0.0"


def test_design_session_record_pending_review_has_accepted_proposal(
    pending_review_record: DesignSessionRecord,
) -> None:
    assert pending_review_record.accepted_proposal is not None
    assert pending_review_record.final_outcome == SessionOutcome.PENDING_REVIEW


def test_design_session_record_verification_skipped_default(
    pending_review_record: DesignSessionRecord,
) -> None:
    assert pending_review_record.verification_skipped is False


def test_design_session_record_hard_block(
    situation: ApplicantSituation,
    goal: MortgageGoal,
) -> None:
    record = DesignSessionRecord(
        situation=situation,
        goal=goal,
        final_outcome=SessionOutcome.HARD_BLOCK,
        block_reason="DTI exceeds all product caps even at minimum viable principal",
        qualification_path=[
            "Reduce monthly debt obligations below $600",
            "Increase annual income above $110,000",
        ],
    )
    assert record.final_outcome == SessionOutcome.HARD_BLOCK
    assert record.block_reason is not None
    assert len(record.qualification_path) == 2
    assert record.accepted_proposal is None


def test_design_session_record_escalated(
    situation: ApplicantSituation,
    goal: MortgageGoal,
    proposal: MortgagePackageProposal,
) -> None:
    record = DesignSessionRecord(
        situation=situation,
        goal=goal,
        proposals=[proposal, proposal],
        lean_feedback_history=[["dtiCapConventional"], ["dtiCapConventional"]],
        reviewer_concerns_history=[[], []],
        final_outcome=SessionOutcome.ESCALATED,
        escalation_context="Max iterations reached; DTI violations persist.",
    )
    assert record.final_outcome == SessionOutcome.ESCALATED
    assert record.escalation_context is not None
    assert len(record.proposals) == 2


# ---------------------------------------------------------------------------
# design_session_io serialize / loads round-trip
# ---------------------------------------------------------------------------


def test_serialize_loads_round_trip(
    pending_review_record: DesignSessionRecord,
) -> None:
    raw = serialize(pending_review_record)
    data = json.loads(raw)
    assert data["schema_version"] == "2.0.0"
    assert data["final_outcome"] == "PENDING_REVIEW"

    restored = loads(raw)
    assert restored.session_id == pending_review_record.session_id
    assert restored.final_outcome == SessionOutcome.PENDING_REVIEW


def test_loads_wrong_version_raises(
    pending_review_record: DesignSessionRecord,
) -> None:
    raw = serialize(pending_review_record)
    data = json.loads(raw)
    data["schema_version"] = "1.0.0"
    with pytest.raises(DesignSessionSchemaVersionError):
        loads(json.dumps(data))
