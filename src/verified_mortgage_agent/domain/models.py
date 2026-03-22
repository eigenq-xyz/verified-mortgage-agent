from __future__ import annotations

import uuid
from datetime import UTC, datetime
from decimal import Decimal

from pydantic import BaseModel, Field, field_validator

from verified_mortgage_agent.domain.enums import (
    DocumentType,
    EmploymentStatus,
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
