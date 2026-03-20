"""Shared fixtures for all tests."""

from __future__ import annotations

from decimal import Decimal

import pytest

from verified_mortgage_agent.domain.enums import (
    DocumentType,
    EmploymentStatus,
    LoanType,
    PropertyType,
)
from verified_mortgage_agent.domain.models import (
    Applicant,
    LoanRequest,
    MortgageApplication,
    Property,
)


@pytest.fixture
def applicant_good() -> Applicant:
    return Applicant(
        name="Jane Smith",
        annual_income_usd=Decimal("120000"),
        credit_score=740,
        employment_status=EmploymentStatus.EMPLOYED,
        debt_obligations_monthly_usd=Decimal("500"),
    )


@pytest.fixture
def property_standard() -> Property:
    return Property(
        address="123 Main St, Springfield, IL 62701",
        appraised_value_usd=Decimal("400000"),
        property_type=PropertyType.SINGLE_FAMILY,
    )


@pytest.fixture
def loan_conventional() -> LoanRequest:
    return LoanRequest(
        principal_usd=Decimal("320000"),
        term_years=30,
        loan_type=LoanType.CONVENTIONAL,
    )


@pytest.fixture
def all_conventional_docs() -> list[DocumentType]:
    return [
        DocumentType.GOVERNMENT_ID,
        DocumentType.PAY_STUB,
        DocumentType.TAX_RETURN,
        DocumentType.BANK_STATEMENT,
    ]


@pytest.fixture
def application_approvable(
    applicant_good: Applicant,
    property_standard: Property,
    loan_conventional: LoanRequest,
    all_conventional_docs: list[DocumentType],
) -> MortgageApplication:
    """A complete, eligible conventional mortgage application."""
    return MortgageApplication(
        applicant=applicant_good,
        property=property_standard,
        loan=loan_conventional,
        provided_documents=all_conventional_docs,
    )


@pytest.fixture
def application_high_dti(
    property_standard: Property,
    loan_conventional: LoanRequest,
    all_conventional_docs: list[DocumentType],
) -> MortgageApplication:
    """Application with DTI > 0.43 — should be rejected."""
    applicant = Applicant(
        name="Bob Jones",
        annual_income_usd=Decimal("60000"),
        credit_score=700,
        employment_status=EmploymentStatus.EMPLOYED,
        debt_obligations_monthly_usd=Decimal("2500"),  # DTI ≈ 0.50
    )
    return MortgageApplication(
        applicant=applicant,
        property=property_standard,
        loan=loan_conventional,
        provided_documents=all_conventional_docs,
    )


@pytest.fixture
def application_missing_docs(
    applicant_good: Applicant,
    property_standard: Property,
    loan_conventional: LoanRequest,
) -> MortgageApplication:
    """Application with no documents provided."""
    return MortgageApplication(
        applicant=applicant_good,
        property=property_standard,
        loan=loan_conventional,
        provided_documents=[],
    )
