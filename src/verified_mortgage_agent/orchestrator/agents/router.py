"""Router — pure-Python routing logic (no LLM call).

Determines the next agent based on current state. Records routing
reasoning steps for auditability (these go into ``routing_steps``,
not formally verified by Lean).
"""

from __future__ import annotations

from verified_mortgage_agent.domain.enums import RoutingOutcome
from verified_mortgage_agent.orchestrator.state import GraphState
from verified_mortgage_agent.record.models import ReasoningStep


def route_after_intake(state: GraphState) -> str:
    """Conditional edge after intake: fan out or stop."""
    decisions = state.get("decisions", [])
    if not decisions:
        return "fan_out"

    last = decisions[-1]
    if last.outcome == RoutingOutcome.REQUEST_DOCUMENTS:
        return "assemble_record"
    return "fan_out"


def route_after_analysis(state: GraphState) -> str:
    """Conditional edge after risk+compliance converge: underwriter or stop."""
    decisions = state.get("decisions", [])

    # If any analysis agent rejected, skip underwriter
    for d in decisions:
        if d.agent_name in ("risk_assessment", "compliance"):
            if d.outcome == RoutingOutcome.REJECT:
                return "assemble_record"

    return "underwriter"


def route_after_underwriter(state: GraphState) -> str:
    """After underwriter, always assemble the record."""
    return "assemble_record"


def make_routing_step(
    step_index: int,
    from_agent: str,
    to_agent: str,
    reason: str,
) -> ReasoningStep:
    """Create an auditable routing step."""
    return ReasoningStep(
        step_index=step_index,
        description=f"Routed from {from_agent} to {to_agent}: {reason}",
        inputs_considered=[f"{from_agent}_outcome"],
        rule_cited=None,
    )
