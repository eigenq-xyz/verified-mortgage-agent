from verified_mortgage_agent.domain.enums import DocumentType, RoutingOutcome
from verified_mortgage_agent.domain.models import MortgageApplication
from verified_mortgage_agent.domain.validators import (
    check_approval_eligibility,
    missing_documents,
    suggest_outcome,
)


def test_approvable_application(application_approvable: MortgageApplication) -> None:
    eligible, violations = check_approval_eligibility(application_approvable)
    assert eligible
    assert violations == []


def test_high_dti_rejected(application_high_dti: MortgageApplication) -> None:
    eligible, violations = check_approval_eligibility(application_high_dti)
    assert not eligible
    assert any("DTI" in v for v in violations)


def test_missing_docs_detected(application_missing_docs: MortgageApplication) -> None:
    missing = missing_documents(application_missing_docs)
    assert DocumentType.GOVERNMENT_ID in missing
    assert DocumentType.PAY_STUB in missing


def test_suggest_outcome_approve(application_approvable: MortgageApplication) -> None:
    assert suggest_outcome(application_approvable) == RoutingOutcome.APPROVE


def test_suggest_outcome_request_docs(
    application_missing_docs: MortgageApplication,
) -> None:
    assert suggest_outcome(application_missing_docs) == RoutingOutcome.REQUEST_DOCUMENTS


def test_suggest_outcome_reject(application_high_dti: MortgageApplication) -> None:
    assert suggest_outcome(application_high_dti) == RoutingOutcome.REJECT
