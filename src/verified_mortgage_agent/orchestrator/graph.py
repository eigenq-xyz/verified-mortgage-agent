"""LangGraph graph construction for both mortgage orchestrators.

v1 Graph flow (build_graph):
  START → intake → [router]
      ├─ documents missing → assemble_record → END
      └─ complete → Send(risk_assessment, compliance)  ← parallel fan-out
                        └── both converge → [router]
                                └─ underwriter → assemble_record → END

v2 Design graph flow (build_design_graph):
  START → feasibility_gate
      ├─ blocking (HARD_BLOCK / DOCUMENTS_REQUIRED) → assemble_block → END
      └─ PROCEED → package_designer → package_reviewer → lean_verify
                        ├─ no violations → assemble_pending → END
                        ├─ violations AND iter < max → package_designer (loop)
                        └─ violations AND iter >= max → assemble_escalated → END
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, Union

from langchain_core.messages import HumanMessage, SystemMessage
from langgraph.graph import END, StateGraph
from langgraph.types import Send

from verified_mortgage_agent.domain.enums import RoutingOutcome, SessionOutcome
from verified_mortgage_agent.lean_bridge.runner import (
    LeanBinaryNotFoundError,
    verify_proposal,
)
from verified_mortgage_agent.orchestrator.agents.compliance import compliance_node
from verified_mortgage_agent.orchestrator.agents.intake import intake_node
from verified_mortgage_agent.orchestrator.agents.package_designer import (
    package_designer_node,
)
from verified_mortgage_agent.orchestrator.agents.package_reviewer import (
    package_reviewer_node,
)
from verified_mortgage_agent.orchestrator.agents.risk import risk_node
from verified_mortgage_agent.orchestrator.agents.router import route_after_analysis
from verified_mortgage_agent.orchestrator.agents.underwriter import underwriter_node
from verified_mortgage_agent.orchestrator.config import get_llm
from verified_mortgage_agent.orchestrator.prompts import (
    ESCALATION_SUMMARY_HUMAN,
    ESCALATION_SUMMARY_SYSTEM,
)
from verified_mortgage_agent.orchestrator.state import DesignGraphState, GraphState
from verified_mortgage_agent.record.models import DecisionRecord, DesignSessionRecord


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
    return {"final_outcome": final_outcome, "record": record}


def build_graph() -> Any:
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


def compile_graph() -> Any:
    """Build and compile the graph for execution."""
    return build_graph().compile()


# ---------------------------------------------------------------------------
# Phase 4 design graph
# ---------------------------------------------------------------------------


def _feasibility_gate(state: DesignGraphState) -> dict:  # type: ignore[type-arg]
    """Stage 1: deterministic Python checks — no LLM involved.

    Blocks on:
    - Missing critical documents (if provided_documents tracking is added
      in a future phase — currently a stub that always proceeds).
    - Mathematical impossibility: DTI of existing debt alone already exceeds
      the strictest cap (0.41, VA) for all loan types.
    """
    situation = state["situation"]
    goal = state["goal"]

    monthly_income = situation.monthly_income_usd
    if monthly_income and monthly_income > 0:
        existing_dti = situation.debt_obligations_monthly_usd / monthly_income
    else:
        existing_dti = situation.debt_obligations_monthly_usd  # treat as very high

    # Hard block: if existing debt alone exceeds the most permissive DTI cap
    # (FHA at 0.50), no loan product can work without debt reduction.
    if existing_dti >= 1:
        return {
            "stage_1_outcome": SessionOutcome.HARD_BLOCK,
            "block_reason": (
                f"Existing monthly debt obligations "
                f"(${situation.debt_obligations_monthly_usd}) already equal or "
                f"exceed monthly gross income "
                f"(${monthly_income:.2f}). "
                "No standard mortgage product is viable without first reducing "
                "debt obligations."
            ),
            "qualification_path": [
                "Reduce total monthly debt obligations to below "
                f"${monthly_income * 1 / 2:.0f} (50% of monthly gross income)",
                "Consider debt consolidation or payoff before applying",
            ],
        }

    # Down-payment sanity: principal must be > 0
    principal_estimate = goal.target_property_price - goal.available_down_payment
    if principal_estimate <= 0:
        # Down payment covers full price — unusual but not a hard block;
        # the designer will propose a small loan or cash deal note.
        pass

    return {
        "stage_1_outcome": None,
        "missing_documents": [],
        "block_reason": None,
        "qualification_path": [],
    }


def _route_after_feasibility(state: DesignGraphState) -> str:
    if state.get("stage_1_outcome") is not None:
        return "assemble_block"
    return "package_designer"


def _lean_verify_node(state: DesignGraphState) -> dict:  # type: ignore[type-arg]
    """Pure-Python node: run lean_verify on the current proposal."""
    proposal = state.get("current_proposal")
    if proposal is None:
        return {
            "lean_feedback": ["internal: no proposal to verify"],
            "all_lean_feedback": [["internal: no proposal to verify"]],
            "verification_skipped": False,
        }

    try:
        result = verify_proposal(proposal, state["situation"], state["goal"])
        violations = [v.description or v.invariant_name for v in result.violations]
    except LeanBinaryNotFoundError:
        # Binary not available — treat as pass but flag verification_skipped.
        violations = []
        return {
            "lean_feedback": [],
            "all_lean_feedback": [[]],
            "verification_skipped": True,
        }

    return {
        "lean_feedback": violations,
        "all_lean_feedback": [violations],
        "verification_skipped": False,
    }


def _route_after_lean(state: DesignGraphState) -> str:
    violations = state.get("lean_feedback", [])
    iteration = state.get("iteration", 1)
    max_iterations = state.get("max_iterations", 3)

    if not violations or state.get("verification_skipped", False):
        return "assemble_pending"
    if iteration > max_iterations:
        return "assemble_escalated"
    return "package_designer"


def _assemble_pending(state: DesignGraphState) -> dict:  # type: ignore[type-arg]
    """Seal a PENDING_REVIEW DesignSessionRecord."""
    record = DesignSessionRecord(
        situation=state["situation"],
        goal=state["goal"],
        proposals=state.get("all_proposals", []),
        lean_feedback_history=state.get("all_lean_feedback", []),
        reviewer_concerns_history=state.get("all_reviewer_concerns", []),
        final_outcome=SessionOutcome.PENDING_REVIEW,
        accepted_proposal=state.get("current_proposal"),
        verification_skipped=state.get("verification_skipped", False),
        generated_at=datetime.now(UTC),
    )
    return {"session_outcome": SessionOutcome.PENDING_REVIEW, "record": record}


def _assemble_block(state: DesignGraphState) -> dict:  # type: ignore[type-arg]
    """Seal a HARD_BLOCK or DOCUMENTS_REQUIRED DesignSessionRecord."""
    outcome = state.get("stage_1_outcome") or SessionOutcome.HARD_BLOCK
    record = DesignSessionRecord(
        situation=state["situation"],
        goal=state["goal"],
        final_outcome=outcome,
        block_reason=state.get("block_reason"),
        qualification_path=state.get("qualification_path", []),
        generated_at=datetime.now(UTC),
    )
    return {"session_outcome": outcome, "record": record}


def _assemble_escalated(state: DesignGraphState) -> dict:  # type: ignore[type-arg]
    """Call the LLM for an escalation summary, then seal the record."""
    situation = state["situation"]
    goal = state["goal"]
    all_proposals = state.get("all_proposals", [])
    all_lean_feedback = state.get("all_lean_feedback", [])

    # Build iteration summary for the prompt
    iterations_summary_lines: list[str] = []
    for i, (prop, feedback) in enumerate(
        zip(all_proposals, all_lean_feedback, strict=False), start=1
    ):
        vcount = len(feedback)
        iterations_summary_lines.append(
            f"  Iter {i}: {prop.loan_type} ${prop.principal_usd} "
            f"{prop.term_years}yr — {vcount} violation(s)"
        )

    lean_violations_summary = "\n".join(
        f"  Iter {i+1}: {'; '.join(fb) or 'none'}"
        for i, fb in enumerate(all_lean_feedback)
    )

    monthly_income = situation.monthly_income_usd
    existing_dti = (
        situation.debt_obligations_monthly_usd / monthly_income
        if monthly_income else 0
    )

    llm = get_llm("escalation_summary")
    summary_response = llm.invoke([
        SystemMessage(content=ESCALATION_SUMMARY_SYSTEM),
        HumanMessage(content=ESCALATION_SUMMARY_HUMAN.format(
            applicant_name=situation.name,
            annual_income=situation.annual_income_usd,
            credit_score=situation.credit_score,
            existing_dti=float(existing_dti),
            target_price=goal.target_property_price,
            down_payment=goal.available_down_payment,
            priority=goal.priority.value,
            iterations_summary="\n".join(iterations_summary_lines) or "  (none)",
            lean_violations_summary=lean_violations_summary or "  (none)",
        )),
    ])
    raw_content = (
        summary_response.content
        if hasattr(summary_response, "content")
        else summary_response
    )
    escalation_context: str = (
        raw_content if isinstance(raw_content, str) else str(raw_content)
    )

    record = DesignSessionRecord(
        situation=situation,
        goal=goal,
        proposals=all_proposals,
        lean_feedback_history=all_lean_feedback,
        reviewer_concerns_history=state.get("all_reviewer_concerns", []),
        final_outcome=SessionOutcome.ESCALATED,
        escalation_context=escalation_context,
        verification_skipped=state.get("verification_skipped", False),
        generated_at=datetime.now(UTC),
    )
    return {
        "session_outcome": SessionOutcome.ESCALATED,
        "escalation_context": escalation_context,
        "record": record,
    }


def build_design_graph() -> Any:
    """Construct the Phase 4 generative design graph (not yet compiled)."""
    graph = StateGraph(DesignGraphState)

    graph.add_node("feasibility_gate", _feasibility_gate)
    graph.add_node("package_designer", package_designer_node)
    graph.add_node("package_reviewer", package_reviewer_node)
    graph.add_node("lean_verify", _lean_verify_node)
    graph.add_node("assemble_pending", _assemble_pending)
    graph.add_node("assemble_escalated", _assemble_escalated)
    graph.add_node("assemble_block", _assemble_block)

    graph.set_entry_point("feasibility_gate")

    graph.add_conditional_edges(
        "feasibility_gate",
        _route_after_feasibility,
        {"assemble_block": "assemble_block", "package_designer": "package_designer"},
    )
    graph.add_edge("package_designer", "package_reviewer")
    graph.add_edge("package_reviewer", "lean_verify")
    graph.add_conditional_edges(
        "lean_verify",
        _route_after_lean,
        {
            "assemble_pending": "assemble_pending",
            "assemble_escalated": "assemble_escalated",
            "package_designer": "package_designer",
        },
    )
    graph.add_edge("assemble_pending", END)
    graph.add_edge("assemble_escalated", END)
    graph.add_edge("assemble_block", END)

    return graph


def compile_design_graph() -> Any:
    """Build and compile the design graph for execution."""
    return build_design_graph().compile()
