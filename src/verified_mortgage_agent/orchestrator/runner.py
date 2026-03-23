"""Synchronous and asynchronous runners for both orchestrator graphs."""

from __future__ import annotations

from verified_mortgage_agent.domain.models import (
    ApplicantSituation,
    MortgageApplication,
    MortgageGoal,
)
from verified_mortgage_agent.orchestrator.graph import (
    compile_design_graph,
    compile_graph,
)
from verified_mortgage_agent.orchestrator.state import DesignGraphState, GraphState
from verified_mortgage_agent.record.models import DecisionRecord, DesignSessionRecord


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
        "record": None,
    }

    result = compiled.invoke(initial_state)
    record: DecisionRecord = result["record"]
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
        "record": None,
    }

    result = await compiled.ainvoke(initial_state)
    record: DecisionRecord = result["record"]
    return record


def run_design_sync(
    situation: ApplicantSituation,
    goal: MortgageGoal,
    max_iterations: int = 3,
) -> DesignSessionRecord:
    """Run the design-loop orchestrator synchronously."""
    compiled = compile_design_graph()

    initial_state: DesignGraphState = {
        "situation": situation,
        "goal": goal,
        "max_iterations": max_iterations,
        "stage_1_outcome": None,
        "missing_documents": [],
        "block_reason": None,
        "qualification_path": [],
        "iteration": 1,
        "current_proposal": None,
        "reviewer_concerns": [],
        "lean_feedback": [],
        "verification_skipped": False,
        "all_proposals": [],
        "all_lean_feedback": [],
        "all_reviewer_concerns": [],
        "session_outcome": None,
        "accepted_proposal": None,
        "escalation_context": None,
        "record": None,
    }

    result = compiled.invoke(initial_state)
    design_record: DesignSessionRecord = result["record"]
    return design_record


async def run_design_async(
    situation: ApplicantSituation,
    goal: MortgageGoal,
    max_iterations: int = 3,
) -> DesignSessionRecord:
    """Run the design-loop orchestrator asynchronously."""
    compiled = compile_design_graph()

    initial_state: DesignGraphState = {
        "situation": situation,
        "goal": goal,
        "max_iterations": max_iterations,
        "stage_1_outcome": None,
        "missing_documents": [],
        "block_reason": None,
        "qualification_path": [],
        "iteration": 1,
        "current_proposal": None,
        "reviewer_concerns": [],
        "lean_feedback": [],
        "verification_skipped": False,
        "all_proposals": [],
        "all_lean_feedback": [],
        "all_reviewer_concerns": [],
        "session_outcome": None,
        "accepted_proposal": None,
        "escalation_context": None,
        "record": None,
    }

    result = await compiled.ainvoke(initial_state)
    design_record: DesignSessionRecord = result["record"]
    return design_record
