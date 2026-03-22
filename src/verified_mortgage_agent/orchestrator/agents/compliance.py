"""Compliance agent — checks regulatory requirements."""

from __future__ import annotations

from datetime import UTC, datetime

from langchain_core.messages import HumanMessage, SystemMessage

from verified_mortgage_agent.orchestrator.config import get_llm, get_model_id
from verified_mortgage_agent.orchestrator.prompts import (
    COMPLIANCE_HUMAN,
    COMPLIANCE_SYSTEM,
)
from verified_mortgage_agent.orchestrator.state import GraphState
from verified_mortgage_agent.orchestrator.tools import AgentResponse
from verified_mortgage_agent.record.models import ReasoningStep, RoutingDecision

AGENT_NAME = "compliance"


def compliance_node(state: GraphState) -> dict:  # type: ignore[type-arg]
    """LangGraph node: check regulatory compliance."""
    app = state["application"]

    rate_str = (
        f"{app.loan.requested_rate_pct}%"
        if app.loan.requested_rate_pct is not None
        else "not specified"
    )

    llm = get_llm(AGENT_NAME).with_structured_output(AgentResponse)
    response: AgentResponse = llm.invoke([
        SystemMessage(content=COMPLIANCE_SYSTEM),
        HumanMessage(content=COMPLIANCE_HUMAN.format(
            applicant_name=app.applicant.name,
            employment_status=app.applicant.employment_status.value,
            loan_type=app.loan.loan_type.value,
            principal=app.loan.principal_usd,
            term_years=app.loan.term_years,
            requested_rate=rate_str,
            property_type=app.property.property_type.value,
            property_address=app.property.address,
        )),
    ])

    decision = RoutingDecision(
        application_id=app.id,
        agent_name=AGENT_NAME,
        outcome=response.outcome,
        reasoning_steps=[
            ReasoningStep(
                step_index=i,
                description=s.description,
                inputs_considered=s.inputs_considered,
                rule_cited=s.rule_cited,
            )
            for i, s in enumerate(response.reasoning_steps)
        ],
        confidence_score=response.confidence_score,
        escalation_reason=response.escalation_reason,
        decided_at=datetime.now(UTC),
        model_id=get_model_id(AGENT_NAME),
    )

    return {"decisions": [decision]}
