"""Risk assessment agent — analyzes DTI, LTV, credit score."""

from __future__ import annotations

from datetime import UTC, datetime

from langchain_core.messages import HumanMessage, SystemMessage

from verified_mortgage_agent.domain.validators import (
    credit_score_min,
    dti_cap,
    ltv_cap,
)
from verified_mortgage_agent.orchestrator.config import get_llm, get_model_id
from verified_mortgage_agent.orchestrator.prompts import RISK_HUMAN, RISK_SYSTEM
from verified_mortgage_agent.orchestrator.state import GraphState
from verified_mortgage_agent.orchestrator.tools import AgentResponse
from verified_mortgage_agent.record.models import ReasoningStep, RoutingDecision

AGENT_NAME = "risk_assessment"


def risk_node(state: GraphState) -> dict:  # type: ignore[type-arg]
    """LangGraph node: assess financial risk."""
    app = state["application"]
    loan_type = app.loan.loan_type

    llm = get_llm(AGENT_NAME).with_structured_output(AgentResponse)
    response: AgentResponse = llm.invoke([
        SystemMessage(content=RISK_SYSTEM),
        HumanMessage(content=RISK_HUMAN.format(
            applicant_name=app.applicant.name,
            annual_income=app.applicant.annual_income_usd,
            monthly_debt=app.applicant.debt_obligations_monthly_usd,
            credit_score=app.applicant.credit_score,
            employment_status=app.applicant.employment_status.value,
            loan_type=loan_type.value,
            principal=app.loan.principal_usd,
            appraised_value=app.property.appraised_value_usd,
            dti=float(app.debt_to_income_ratio),
            ltv=float(app.loan_to_value_ratio),
            dti_cap=dti_cap(loan_type),
            ltv_cap=ltv_cap(loan_type),
            credit_min=credit_score_min(loan_type),
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
