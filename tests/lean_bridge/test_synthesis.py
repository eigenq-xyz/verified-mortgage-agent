"""Unit tests for lean_bridge/synthesis.py — no Lean binary required."""

from __future__ import annotations

from decimal import Decimal

import pytest

from verified_mortgage_agent.domain.enums import (
    EmploymentStatus,
    GoalPriority,
    LoanType,
    RoutingOutcome,
)
from verified_mortgage_agent.domain.models import (
    ApplicantSituation,
    MortgageGoal,
    MortgagePackageProposal,
)
from verified_mortgage_agent.lean_bridge.synthesis import (
    synthesize_record_from_proposal,
)
from verified_mortgage_agent.record.models import SCHEMA_VERSION


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
        priority=GoalPriority.BALANCED,
    )


@pytest.fixture
def proposal() -> MortgagePackageProposal:
    return MortgagePackageProposal(
        loan_type=LoanType.CONVENTIONAL,
        principal_usd=Decimal("405000"),
        term_years=30,
        estimated_rate_pct=Decimal("6.75"),
        rationale="30-year term minimises monthly payment",
        customer_benefit="Lowest monthly cost at current rates",
        estimated_monthly_pi=Decimal("2627"),
        iteration=1,
    )


def test_synthesized_schema_version(
    proposal: MortgagePackageProposal,
    situation: ApplicantSituation,
    goal: MortgageGoal,
) -> None:
    record = synthesize_record_from_proposal(proposal, situation, goal)
    assert record.schema_version == SCHEMA_VERSION
    assert record.schema_version == "1.0.0"


def test_synthesized_outcome_is_approve(
    proposal: MortgagePackageProposal,
    situation: ApplicantSituation,
    goal: MortgageGoal,
) -> None:
    record = synthesize_record_from_proposal(proposal, situation, goal)
    assert record.final_outcome == RoutingOutcome.APPROVE
    assert len(record.decisions) == 1
    assert record.decisions[0].outcome == RoutingOutcome.APPROVE


def test_synthesized_principal_matches_proposal(
    proposal: MortgagePackageProposal,
    situation: ApplicantSituation,
    goal: MortgageGoal,
) -> None:
    record = synthesize_record_from_proposal(proposal, situation, goal)
    assert record.application.loan.principal_usd == proposal.principal_usd
    assert record.application.loan.loan_type == proposal.loan_type
    assert record.application.loan.term_years == proposal.term_years


def test_synthesized_property_value_from_goal(
    proposal: MortgagePackageProposal,
    situation: ApplicantSituation,
    goal: MortgageGoal,
) -> None:
    record = synthesize_record_from_proposal(proposal, situation, goal)
    assert record.application.property.appraised_value_usd == goal.target_property_price


def test_synthesized_applicant_matches_situation(
    proposal: MortgagePackageProposal,
    situation: ApplicantSituation,
    goal: MortgageGoal,
) -> None:
    record = synthesize_record_from_proposal(proposal, situation, goal)
    applicant = record.application.applicant
    assert applicant.name == situation.name
    assert applicant.annual_income_usd == situation.annual_income_usd
    assert applicant.credit_score == situation.credit_score
    assert (
        applicant.debt_obligations_monthly_usd
        == situation.debt_obligations_monthly_usd
    )


def test_synthesized_applicant_has_no_phase4_fields(
    proposal: MortgagePackageProposal,
    situation: ApplicantSituation,
    goal: MortgageGoal,
) -> None:
    """Phase-4-only fields (assets, employment_months) must not leak into v1."""
    record = synthesize_record_from_proposal(proposal, situation, goal)
    applicant = record.application.applicant
    assert not hasattr(applicant, "assets_liquid_usd")
    assert not hasattr(applicant, "employment_months_current")


def test_synthesized_dti_derived_correctly(
    proposal: MortgagePackageProposal,
    situation: ApplicantSituation,
    goal: MortgageGoal,
) -> None:
    record = synthesize_record_from_proposal(proposal, situation, goal)
    expected_dti = situation.debt_obligations_monthly_usd / situation.monthly_income_usd
    assert record.application.debt_to_income_ratio == expected_dti


def test_synthesized_ltv_derived_correctly(
    proposal: MortgagePackageProposal,
    situation: ApplicantSituation,
    goal: MortgageGoal,
) -> None:
    record = synthesize_record_from_proposal(proposal, situation, goal)
    expected_ltv = proposal.principal_usd / goal.target_property_price
    assert record.application.loan_to_value_ratio == expected_ltv


def test_synthesize_uses_placeholder_address(
    proposal: MortgagePackageProposal,
    situation: ApplicantSituation,
    goal: MortgageGoal,
) -> None:
    record = synthesize_record_from_proposal(proposal, situation, goal)
    assert "address" in record.application.property.address.lower()


def test_synthesize_different_calls_produce_unique_ids(
    proposal: MortgagePackageProposal,
    situation: ApplicantSituation,
    goal: MortgageGoal,
) -> None:
    r1 = synthesize_record_from_proposal(proposal, situation, goal)
    r2 = synthesize_record_from_proposal(proposal, situation, goal)
    assert r1.record_id != r2.record_id
    assert r1.application.id != r2.application.id
