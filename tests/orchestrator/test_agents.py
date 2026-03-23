"""Unit tests for individual agent nodes — LLM is mocked."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from verified_mortgage_agent.domain.enums import DocumentType, RoutingOutcome
from verified_mortgage_agent.orchestrator.agents.compliance import compliance_node
from verified_mortgage_agent.orchestrator.agents.intake import intake_node
from verified_mortgage_agent.orchestrator.agents.risk import risk_node
from verified_mortgage_agent.orchestrator.agents.underwriter import underwriter_node
from verified_mortgage_agent.orchestrator.tools import (
    AgentResponse,
    ReasoningStepOutput,
)


def _make_llm_mock(outcome: RoutingOutcome, **kwargs) -> MagicMock:  # type: ignore[no-untyped-def]
    """Return a mock that behaves like ``llm.with_structured_output(…).invoke(…)``."""
    response = AgentResponse(
        outcome=outcome,
        reasoning_steps=[
            ReasoningStepOutput(description=f"Checked for {outcome.value}")
        ],
        confidence_score=0.9,
        **kwargs,
    )
    inner_mock = MagicMock()
    inner_mock.invoke.return_value = response

    outer_mock = MagicMock()
    outer_mock.with_structured_output.return_value = inner_mock
    return outer_mock


def _base_state(application_approvable):  # type: ignore[no-untyped-def]
    return {
        "application": application_approvable,
        "decisions": [],
        "routing_steps": [],
        "next_agent": None,
        "escalation_required": False,
        "escalation_reason": None,
        "final_outcome": None,
    }


def test_intake_approve(application_approvable) -> None:  # type: ignore[no-untyped-def]
    mock_llm = _make_llm_mock(RoutingOutcome.APPROVE)
    with patch(
        "verified_mortgage_agent.orchestrator.agents.intake.get_llm",
        return_value=mock_llm,
    ):
        result = intake_node(_base_state(application_approvable))

    assert len(result["decisions"]) == 1
    assert result["decisions"][0].outcome == RoutingOutcome.APPROVE
    assert result["decisions"][0].agent_name == "intake"


def test_intake_request_documents(application_missing_docs) -> None:  # type: ignore[no-untyped-def]
    mock_llm = _make_llm_mock(
        RoutingOutcome.REQUEST_DOCUMENTS,
        documents_requested=[DocumentType.PAY_STUB, DocumentType.TAX_RETURN],
    )
    state = {
        "application": application_missing_docs,
        "decisions": [],
        "routing_steps": [],
        "next_agent": None,
        "escalation_required": False,
        "escalation_reason": None,
        "final_outcome": None,
    }
    with patch(
        "verified_mortgage_agent.orchestrator.agents.intake.get_llm",
        return_value=mock_llm,
    ):
        result = intake_node(state)

    assert result["decisions"][0].outcome == RoutingOutcome.REQUEST_DOCUMENTS
    assert DocumentType.PAY_STUB in result["decisions"][0].documents_requested


def test_risk_approve(application_approvable) -> None:  # type: ignore[no-untyped-def]
    mock_llm = _make_llm_mock(RoutingOutcome.APPROVE)
    with patch(
        "verified_mortgage_agent.orchestrator.agents.risk.get_llm",
        return_value=mock_llm,
    ):
        result = risk_node(_base_state(application_approvable))

    assert result["decisions"][0].outcome == RoutingOutcome.APPROVE
    assert result["decisions"][0].agent_name == "risk_assessment"


def test_compliance_approve(application_approvable) -> None:  # type: ignore[no-untyped-def]
    mock_llm = _make_llm_mock(RoutingOutcome.APPROVE)
    with patch(
        "verified_mortgage_agent.orchestrator.agents.compliance.get_llm",
        return_value=mock_llm,
    ):
        result = compliance_node(_base_state(application_approvable))

    assert result["decisions"][0].agent_name == "compliance"


def test_underwriter_sets_final_outcome(application_approvable) -> None:  # type: ignore[no-untyped-def]
    mock_llm = _make_llm_mock(RoutingOutcome.APPROVE)
    with patch(
        "verified_mortgage_agent.orchestrator.agents.underwriter.get_llm",
        return_value=mock_llm,
    ):
        result = underwriter_node(_base_state(application_approvable))

    assert result["final_outcome"] == RoutingOutcome.APPROVE
    assert result["escalation_required"] is False


def test_underwriter_escalation(application_approvable) -> None:  # type: ignore[no-untyped-def]
    mock_llm = _make_llm_mock(
        RoutingOutcome.ESCALATE_TO_UNDERWRITER,
        escalation_reason="Borderline DTI requires senior review",
    )
    with patch(
        "verified_mortgage_agent.orchestrator.agents.underwriter.get_llm",
        return_value=mock_llm,
    ):
        result = underwriter_node(_base_state(application_approvable))

    assert result["final_outcome"] == RoutingOutcome.ESCALATE_TO_UNDERWRITER
    assert result["escalation_reason"] == "Borderline DTI requires senior review"
