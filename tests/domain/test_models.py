from decimal import Decimal

import pytest

from verified_mortgage_agent.domain.enums import EmploymentStatus, LoanType
from verified_mortgage_agent.domain.models import Applicant, LoanRequest, MortgageApplication


def test_monthly_income(applicant_good: Applicant) -> None:
    assert applicant_good.monthly_income_usd == Decimal("10000")


def test_dti_ratio(application_approvable: MortgageApplication) -> None:
    # 500 / (120000/12) = 500/10000 = 0.05
    assert application_approvable.debt_to_income_ratio == Decimal("0.05")


def test_ltv_ratio(application_approvable: MortgageApplication) -> None:
    # 320000 / 400000 = 0.8
    assert application_approvable.loan_to_value_ratio == Decimal("0.8")


def test_credit_score_bounds() -> None:
    with pytest.raises(Exception):
        Applicant(
            name="X",
            annual_income_usd=Decimal("100000"),
            credit_score=299,
            employment_status=EmploymentStatus.EMPLOYED,
            debt_obligations_monthly_usd=Decimal("0"),
        )
    with pytest.raises(Exception):
        Applicant(
            name="X",
            annual_income_usd=Decimal("100000"),
            credit_score=851,
            employment_status=EmploymentStatus.EMPLOYED,
            debt_obligations_monthly_usd=Decimal("0"),
        )


def test_loan_term_validation() -> None:
    with pytest.raises(Exception):
        LoanRequest(
            principal_usd=Decimal("300000"),
            term_years=7,
            loan_type=LoanType.CONVENTIONAL,
        )


def test_application_has_uuid(application_approvable: MortgageApplication) -> None:
    assert application_approvable.id is not None
