"""Synchronous and asynchronous runners for the orchestrator graph."""

from __future__ import annotations

from verified_mortgage_agent.domain.models import MortgageApplication
from verified_mortgage_agent.orchestrator.graph import compile_graph
from verified_mortgage_agent.orchestrator.state import GraphState
from verified_mortgage_agent.record.models import DecisionRecord


def run_sync(application: MortgageApplication) -> DecisionRecord:
    """Run the orchestrator synchronously and return the sealed record."""
    compiled = compile_graph()

    initial_state: GraphState = {
        "application": application,
        "decisions": [],
        "routing_steps": [],
        "next_agent": None,
        "escalation_required": False,
        "escalation_reason": None,
        "final_outcome": None,
    }

    result = compiled.invoke(initial_state)
    record: DecisionRecord = result["_record"]
    return record


async def run_async(application: MortgageApplication) -> DecisionRecord:
    """Run the orchestrator asynchronously and return the sealed record."""
    compiled = compile_graph()

    initial_state: GraphState = {
        "application": application,
        "decisions": [],
        "routing_steps": [],
        "next_agent": None,
        "escalation_required": False,
        "escalation_reason": None,
        "final_outcome": None,
    }

    result = await compiled.ainvoke(initial_state)
    record: DecisionRecord = result["_record"]
    return record
