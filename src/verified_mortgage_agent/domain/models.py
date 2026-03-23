from __future__ import annotations

import uuid
from datetime import UTC, datetime
from decimal import Decimal

from pydantic import BaseModel, Field, field_validator

from verified_mortgage_agent.domain.enums import (
    DocumentType,
    EmploymentStatus,
    GoalPriority,
    LoanType,
    PropertyType,
)


class Applicant(BaseModel):
    name: str
    annual_income_usd: Decimal = Field(gt=0)
    credit_score: int = Field(ge=300, le=850)
    employment_status: EmploymentStatus
    debt_obligations_monthly_usd: Decimal = Field(ge=0)

    @property
    def monthly_income_usd(self) -> Decimal:
        return self.annual_income_usd / 12


class Property(BaseModel):
    address: str
    appraised_value_usd: Decimal = Field(gt=0)
    property_type: PropertyType


class LoanRequest(BaseModel):
    principal_usd: Decimal = Field(gt=0)
    term_years: int = Field(ge=1, le=30)
    loan_type: LoanType
    requested_rate_pct: Decimal | None = Field(default=None, ge=0, le=100)
    # NJ regulatory / federal compliance fields (optional — default 0 when absent)
    discount_points_pct: Decimal = Field(default=Decimal("0"), ge=0)
    total_points_and_fees_pct: Decimal = Field(default=Decimal("0"), ge=0)
    late_charge_pct: Decimal = Field(default=Decimal("0"), ge=0)
    prepayment_penalty_months: int = Field(default=0, ge=0)
    financed_points_usd: Decimal = Field(default=Decimal("0"), ge=0)
    apr_pct: Decimal = Field(default=Decimal("0"), ge=0)

    @field_validator("term_years")
    @classmethod
    def validate_term(cls, v: int) -> int:
        valid_terms = {10, 15, 20, 25, 30}
        if v not in valid_terms:
            raise ValueError(f"term_years must be one of {valid_terms}")
        return v


class MortgageApplication(BaseModel):
    id: uuid.UUID = Field(default_factory=uuid.uuid4)
    applicant: Applicant
    property: Property
    loan: LoanRequest
    submitted_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    provided_documents: list[DocumentType] = Field(default_factory=list)

    @property  # type: ignore[operator]
    def debt_to_income_ratio(self) -> Decimal:
        """Monthly debt obligations divided by monthly gross income."""
        monthly_income = self.applicant.monthly_income_usd
        if monthly_income == 0:
            return Decimal("999")
        return self.applicant.debt_obligations_monthly_usd / monthly_income

    @property  # type: ignore[operator]
    def loan_to_value_ratio(self) -> Decimal:
        """Loan principal divided by property appraised value."""
        appraised = self.property.appraised_value_usd
        if appraised == 0:
            return Decimal("999")
        return self.loan.principal_usd / appraised


# ---------------------------------------------------------------------------
# Phase 4 design-loop models
# ---------------------------------------------------------------------------


class ApplicantSituation(BaseModel):
    """Extended applicant profile for the generative design loop.

    Includes all fields from Applicant plus liquid assets and employment tenure,
    which the designer agent needs to propose down-payment-aware packages.
    """

    name: str
    annual_income_usd: Decimal = Field(gt=0)
    credit_score: int = Field(ge=300, le=850)
    employment_status: EmploymentStatus
    debt_obligations_monthly_usd: Decimal = Field(ge=0)
    assets_liquid_usd: Decimal = Field(ge=0)
    employment_months_current: int = Field(ge=0)

    @property
    def monthly_income_usd(self) -> Decimal:
        return self.annual_income_usd / 12

    def to_applicant(self) -> Applicant:
        """Return a plain Applicant for use in v1 DecisionRecord synthesis."""
        return Applicant(
            name=self.name,
            annual_income_usd=self.annual_income_usd,
            credit_score=self.credit_score,
            employment_status=self.employment_status,
            debt_obligations_monthly_usd=self.debt_obligations_monthly_usd,
        )


class MortgageGoal(BaseModel):
    """What the applicant is trying to achieve."""

    target_property_price: Decimal = Field(gt=0)
    available_down_payment: Decimal = Field(ge=0)
    desired_max_monthly_payment: Decimal | None = None
    ownership_horizon_years: int | None = None
    priority: GoalPriority = GoalPriority.BALANCED


class MortgagePackageProposal(BaseModel):
    """A concrete mortgage package proposed by the designer agent."""

    loan_type: LoanType
    principal_usd: Decimal = Field(gt=0)
    term_years: int = Field(ge=1, le=30)
    estimated_rate_pct: Decimal = Field(ge=0)
    rationale: str
    customer_benefit: str
    estimated_monthly_pi: Decimal = Field(ge=0)
    special_considerations: list[str] = Field(default_factory=list)
    iteration: int = Field(ge=1)

    @field_validator("term_years")
    @classmethod
    def validate_term(cls, v: int) -> int:
        valid_terms = {10, 15, 20, 25, 30}
        if v not in valid_terms:
            raise ValueError(f"term_years must be one of {valid_terms}")
        return v
