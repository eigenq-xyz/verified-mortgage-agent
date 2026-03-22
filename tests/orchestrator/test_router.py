"""Unit tests for routing logic in orchestrator/agents/router.py."""

from __future__ import annotations

from decimal import Decimal

import pytest

from verified_mortgage_agent.domain.enums import RoutingOutcome
from verified_mortgage_agent.orchestrator.agents.router import (
    route_after_analysis,
    route_after_intake,
)
from verified_mortgage_agent.record.models import RoutingDecision


def _decision(agent: str, outcome: RoutingOutcome, app_id=None) -> RoutingDecision:  # type: ignore[no-untyped-def]
    import uuid
    return RoutingDecision(
        application_id=app_id or uuid.uuid4(),
        agent_name=agent,
        outcome=outcome,
        confidence_score=0.9,
        model_id="anthropic/claude-sonnet-4-6",
    )


def _state_with_decisions(decisions, application=None):  # type: ignore[no-untyped-def]
    return {
        "decisions": decisions,
        "routing_steps": [],
        "next_agent": None,
        "escalation_required": False,
        "escalation_reason": None,
        "final_outcome": None,
        "application": application,
    }


def test_route_after_intake_no_docs_goes_fan_out() -> None:
    state = _state_with_decisions(
        [_decision("intake", RoutingOutcome.APPROVE)]
    )
    assert route_after_intake(state) != "assemble_record"


def test_route_after_intake_missing_docs_stops() -> None:
    state = _state_with_decisions(
        [_decision("intake", RoutingOutcome.REQUEST_DOCUMENTS)]
    )
    assert route_after_intake(state) == "assemble_record"


def test_route_after_analysis_reject_stops() -> None:
    state = _state_with_decisions([
        _decision("risk_assessment", RoutingOutcome.REJECT),
    ])
    assert route_after_analysis(state) == "assemble_record"


def test_route_after_analysis_approve_goes_underwriter() -> None:
    state = _state_with_decisions([
        _decision("risk_assessment", RoutingOutcome.APPROVE),
        _decision("compliance", RoutingOutcome.APPROVE),
    ])
    assert route_after_analysis(state) == "underwriter"
