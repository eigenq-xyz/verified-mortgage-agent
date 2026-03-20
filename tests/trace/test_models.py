import uuid
from datetime import datetime
from decimal import Decimal

from verified_mortgage_agent.domain.enums import LoanType, RoutingOutcome
from verified_mortgage_agent.trace.models import (
    SCHEMA_VERSION,
    ExecutionTrace,
    ReasoningStep,
    RoutingDecision,
)


def test_reasoning_step_defaults() -> None:
    step = ReasoningStep(step_index=0, description="Checked DTI ratio")
    assert step.inputs_considered == []
    assert step.rule_cited is None


def test_routing_decision_requires_model_id(
    application_approvable,  # type: ignore[no-untyped-def]
) -> None:
    decision = RoutingDecision(
        application_id=application_approvable.id,
        agent_name="underwriter",
        outcome=RoutingOutcome.APPROVE,
        confidence_score=0.95,
        model_id="anthropic/claude-sonnet-4-6",
    )
    assert decision.decision_id is not None
    assert decision.decided_at is not None


def test_execution_trace_schema_version(
    application_approvable,  # type: ignore[no-untyped-def]
) -> None:
    decision = RoutingDecision(
        application_id=application_approvable.id,
        agent_name="underwriter",
        outcome=RoutingOutcome.APPROVE,
        confidence_score=0.9,
        model_id="anthropic/claude-sonnet-4-6",
    )
    trace = ExecutionTrace(
        application=application_approvable,
        decisions=[decision],
        final_outcome=RoutingOutcome.APPROVE,
        model_id="anthropic/claude-sonnet-4-6",
    )
    assert trace.schema_version == SCHEMA_VERSION
    assert trace.trace_id is not None


def test_trace_serialization_roundtrip(
    application_approvable,  # type: ignore[no-untyped-def]
) -> None:
    from verified_mortgage_agent.trace.io import loads, serialize

    decision = RoutingDecision(
        application_id=application_approvable.id,
        agent_name="underwriter",
        outcome=RoutingOutcome.APPROVE,
        confidence_score=0.9,
        model_id="anthropic/claude-sonnet-4-6",
    )
    trace = ExecutionTrace(
        application=application_approvable,
        decisions=[decision],
        final_outcome=RoutingOutcome.APPROVE,
        model_id="anthropic/claude-sonnet-4-6",
    )
    roundtripped = loads(serialize(trace))
    assert roundtripped.trace_id == trace.trace_id
    assert roundtripped.final_outcome == RoutingOutcome.APPROVE
    assert len(roundtripped.decisions) == 1
