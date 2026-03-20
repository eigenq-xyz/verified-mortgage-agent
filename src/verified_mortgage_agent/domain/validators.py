"""Stateless domain-level sanity checks.

These mirror the formal invariants in lean/MortgageVerifier/Invariants.lean.
They are used by agents as a fast pre-flight check and by tests as ground truth.
"""

from __future__ import annotations

from decimal import Decimal

from verified_mortgage_agent.domain.enums import DocumentType, LoanType, RoutingOutcome
from verified_mortgage_agent.domain.models import MortgageApplication

# Thresholds — keep in sync with Invariants.lean
DTI_CAP_CONVENTIONAL = Decimal("0.43")
DTI_CAP_FHA = Decimal("0.50")
DTI_CAP_VA = Decimal("0.41")
DTI_CAP_JUMBO = Decimal("0.38")

LTV_CAP_CONVENTIONAL = Decimal("0.97")
LTV_CAP_FHA = Decimal("0.965")  # 3.5% down minimum
LTV_CAP_VA = Decimal("1.00")    # VA allows 100% financing
LTV_CAP_JUMBO = Decimal("0.80")

CREDIT_SCORE_MIN_CONVENTIONAL = 620
CREDIT_SCORE_MIN_FHA = 580
CREDIT_SCORE_MIN_VA = 580
CREDIT_SCORE_MIN_JUMBO = 700

JUMBO_LOAN_THRESHOLD_USD = Decimal("766_550")  # 2024 FHFA conforming limit

REQUIRED_DOCUMENTS: dict[LoanType, list[DocumentType]] = {
    LoanType.CONVENTIONAL: [
        DocumentType.GOVERNMENT_ID,
        DocumentType.PAY_STUB,
        DocumentType.TAX_RETURN,
        DocumentType.BANK_STATEMENT,
    ],
    LoanType.FHA: [
        DocumentType.GOVERNMENT_ID,
        DocumentType.PAY_STUB,
        DocumentType.TAX_RETURN,
        DocumentType.BANK_STATEMENT,
        DocumentType.CREDIT_REPORT,
    ],
    LoanType.VA: [
        DocumentType.GOVERNMENT_ID,
        DocumentType.EMPLOYMENT_VERIFICATION,
        DocumentType.TAX_RETURN,
        DocumentType.BANK_STATEMENT,
    ],
    LoanType.JUMBO: [
        DocumentType.GOVERNMENT_ID,
        DocumentType.PAY_STUB,
        DocumentType.TAX_RETURN,
        DocumentType.BANK_STATEMENT,
        DocumentType.CREDIT_REPORT,
        DocumentType.APPRAISAL,
    ],
}


def dti_cap(loan_type: LoanType) -> Decimal:
    return {
        LoanType.CONVENTIONAL: DTI_CAP_CONVENTIONAL,
        LoanType.FHA: DTI_CAP_FHA,
        LoanType.VA: DTI_CAP_VA,
        LoanType.JUMBO: DTI_CAP_JUMBO,
    }[loan_type]


def ltv_cap(loan_type: LoanType) -> Decimal:
    return {
        LoanType.CONVENTIONAL: LTV_CAP_CONVENTIONAL,
        LoanType.FHA: LTV_CAP_FHA,
        LoanType.VA: LTV_CAP_VA,
        LoanType.JUMBO: LTV_CAP_JUMBO,
    }[loan_type]


def credit_score_min(loan_type: LoanType) -> int:
    return {
        LoanType.CONVENTIONAL: CREDIT_SCORE_MIN_CONVENTIONAL,
        LoanType.FHA: CREDIT_SCORE_MIN_FHA,
        LoanType.VA: CREDIT_SCORE_MIN_VA,
        LoanType.JUMBO: CREDIT_SCORE_MIN_JUMBO,
    }[loan_type]


def missing_documents(app: MortgageApplication) -> list[DocumentType]:
    required = REQUIRED_DOCUMENTS.get(app.loan.loan_type, [])
    return [doc for doc in required if doc not in app.provided_documents]


def check_approval_eligibility(
    app: MortgageApplication,
) -> tuple[bool, list[str]]:
    """Return (eligible, list_of_violation_messages)."""
    violations: list[str] = []

    dti = app.debt_to_income_ratio
    max_dti = dti_cap(app.loan.loan_type)
    if dti > max_dti:
        violations.append(
            f"DTI {dti:.3f} exceeds cap of {max_dti} for {app.loan.loan_type}"
        )

    ltv = app.loan_to_value_ratio
    max_ltv = ltv_cap(app.loan.loan_type)
    if ltv > max_ltv:
        violations.append(
            f"LTV {ltv:.3f} exceeds cap of {max_ltv} for {app.loan.loan_type}"
        )

    score = app.applicant.credit_score
    min_score = credit_score_min(app.loan.loan_type)
    if score < min_score:
        violations.append(
            f"Credit score {score} below minimum {min_score} for {app.loan.loan_type}"
        )

    if (
        app.loan.loan_type == LoanType.JUMBO
        and app.loan.principal_usd <= JUMBO_LOAN_THRESHOLD_USD
    ):
        violations.append(
            f"Loan type JUMBO but principal {app.loan.principal_usd} "
            f"is at or below conforming limit {JUMBO_LOAN_THRESHOLD_USD}"
        )

    return len(violations) == 0, violations


def suggest_outcome(app: MortgageApplication) -> RoutingOutcome:
    """Deterministic outcome suggestion based on domain rules (used in tests)."""
    missing = missing_documents(app)
    if missing:
        return RoutingOutcome.REQUEST_DOCUMENTS

    eligible, _ = check_approval_eligibility(app)
    if eligible:
        return RoutingOutcome.APPROVE
    return RoutingOutcome.REJECT
