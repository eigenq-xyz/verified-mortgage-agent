"""Underwriter agent — final synthesizing decision."""

from __future__ import annotations

from datetime import UTC, datetime

from langchain_core.messages import HumanMessage, SystemMessage

from verified_mortgage_agent.orchestrator.config import get_llm, get_model_id
from verified_mortgage_agent.orchestrator.prompts import (
    UNDERWRITER_HUMAN,
    UNDERWRITER_SYSTEM,
)
from verified_mortgage_agent.orchestrator.state import GraphState
from verified_mortgage_agent.orchestrator.tools import AgentResponse
from verified_mortgage_agent.record.models import ReasoningStep, RoutingDecision

AGENT_NAME = "underwriter"


def _format_prior_decisions(state: GraphState) -> str:
    """Render prior agent decisions as readable text for the underwriter prompt."""
    lines: list[str] = []
    for d in state["decisions"]:
        lines.append(f"  [{d.agent_name}] {d.outcome.value} "
                     f"(confidence: {d.confidence_score})")
        for step in d.reasoning_steps:
            lines.append(f"    - {step.description}")
        if d.escalation_reason:
            lines.append(f"    escalation_reason: {d.escalation_reason}")
    return "\n".join(lines) if lines else "  (no prior decisions)"


def underwriter_node(state: GraphState) -> dict:  # type: ignore[type-arg]
    """LangGraph node: make the final underwriting decision."""
    app = state["application"]

    llm = get_llm(AGENT_NAME).with_structured_output(AgentResponse)
    response: AgentResponse = llm.invoke([
        SystemMessage(content=UNDERWRITER_SYSTEM),
        HumanMessage(content=UNDERWRITER_HUMAN.format(
            application_id=str(app.id),
            applicant_name=app.applicant.name,
            prior_decisions=_format_prior_decisions(state),
            loan_type=app.loan.loan_type.value,
            principal=app.loan.principal_usd,
            dti=float(app.debt_to_income_ratio),
            ltv=float(app.loan_to_value_ratio),
            credit_score=app.applicant.credit_score,
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

    return {
        "decisions": [decision],
        "final_outcome": response.outcome,
        "escalation_required": (
            response.outcome.value == "ESCALATE_TO_UNDERWRITER"
        ),
        "escalation_reason": response.escalation_reason,
    }
