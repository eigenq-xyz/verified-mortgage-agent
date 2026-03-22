"""LangGraph graph construction for the mortgage orchestrator.

Graph flow:
  START → intake → [router]
      ├─ documents missing → assemble_record → END
      └─ complete → Send(risk_assessment, compliance)  ← parallel fan-out
                        └── both converge → [router]
                                └─ underwriter → assemble_record → END
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Union

from langgraph.graph import END, StateGraph
from langgraph.types import Send

from verified_mortgage_agent.domain.enums import RoutingOutcome
from verified_mortgage_agent.orchestrator.agents.compliance import compliance_node
from verified_mortgage_agent.orchestrator.agents.intake import intake_node
from verified_mortgage_agent.orchestrator.agents.risk import risk_node
from verified_mortgage_agent.orchestrator.agents.router import (
    route_after_analysis,
)
from verified_mortgage_agent.orchestrator.agents.underwriter import underwriter_node
from verified_mortgage_agent.orchestrator.state import GraphState
from verified_mortgage_agent.record.models import DecisionRecord


def _route_after_intake(
    state: GraphState,
) -> Union[list[Send], str]:
    """Conditional edge: fan out to parallel agents or stop early."""
    decisions = state.get("decisions", [])
    if decisions and decisions[-1].outcome == RoutingOutcome.REQUEST_DOCUMENTS:
        return "assemble_record"
    # Fan out to risk_assessment and compliance in parallel
    return [
        Send("risk_assessment", state),
        Send("compliance", state),
    ]


def _assemble_record(state: GraphState) -> dict:  # type: ignore[type-arg]
    """Pure-Python node: seal the DecisionRecord from accumulated state."""
    decisions = state.get("decisions", [])
    final_outcome = state.get("final_outcome")

    if final_outcome is None and decisions:
        final_outcome = decisions[-1].outcome
    elif final_outcome is None:
        final_outcome = RoutingOutcome.REJECT

    app = state["application"]
    model_id = decisions[-1].model_id if decisions else "unknown"

    record = DecisionRecord(
        application=app,
        decisions=decisions,
        routing_steps=state.get("routing_steps", []),
        final_outcome=final_outcome,
        generated_at=datetime.now(UTC),
        model_id=model_id,
    )
    return {"final_outcome": final_outcome, "_record": record}


def build_graph() -> StateGraph:
    """Construct the mortgage orchestrator graph (not yet compiled)."""
    graph = StateGraph(GraphState)

    # Nodes
    graph.add_node("intake", intake_node)
    graph.add_node("risk_assessment", risk_node)
    graph.add_node("compliance", compliance_node)
    graph.add_node("underwriter", underwriter_node)
    graph.add_node("assemble_record", _assemble_record)

    # START → intake
    graph.set_entry_point("intake")

    # intake → [parallel fan-out | assemble_record]
    graph.add_conditional_edges("intake", _route_after_intake)

    # risk_assessment, compliance → [underwriter | assemble_record]
    graph.add_conditional_edges(
        "risk_assessment",
        route_after_analysis,
        {"underwriter": "underwriter", "assemble_record": "assemble_record"},
    )
    graph.add_conditional_edges(
        "compliance",
        route_after_analysis,
        {"underwriter": "underwriter", "assemble_record": "assemble_record"},
    )

    # underwriter → assemble_record
    graph.add_edge("underwriter", "assemble_record")

    # assemble_record → END
    graph.add_edge("assemble_record", END)

    return graph


def compile_graph():  # type: ignore[no-untyped-def]
    """Build and compile the graph for execution."""
    return build_graph().compile()
