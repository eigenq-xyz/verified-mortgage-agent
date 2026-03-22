"""Intake agent — checks document completeness."""

from __future__ import annotations

from datetime import UTC, datetime

from langchain_core.messages import HumanMessage, SystemMessage

from verified_mortgage_agent.domain.validators import REQUIRED_DOCUMENTS
from verified_mortgage_agent.orchestrator.config import get_llm, get_model_id
from verified_mortgage_agent.orchestrator.prompts import INTAKE_HUMAN, INTAKE_SYSTEM
from verified_mortgage_agent.orchestrator.state import GraphState
from verified_mortgage_agent.orchestrator.tools import AgentResponse
from verified_mortgage_agent.record.models import ReasoningStep, RoutingDecision

AGENT_NAME = "intake"


def intake_node(state: GraphState) -> dict:  # type: ignore[type-arg]
    """LangGraph node: check document completeness."""
    app = state["application"]
    loan_type = app.loan.loan_type

    required = REQUIRED_DOCUMENTS.get(loan_type, [])

    llm = get_llm(AGENT_NAME).with_structured_output(AgentResponse)
    response: AgentResponse = llm.invoke([
        SystemMessage(content=INTAKE_SYSTEM),
        HumanMessage(content=INTAKE_HUMAN.format(
            loan_type=loan_type.value,
            provided_documents=", ".join(d.value for d in app.provided_documents),
            required_documents=", ".join(d.value for d in required),
            applicant_name=app.applicant.name,
            application_id=str(app.id),
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
        documents_requested=response.documents_requested,
        decided_at=datetime.now(UTC),
        model_id=get_model_id(AGENT_NAME),
    )

    return {"decisions": [decision]}
