"""Package designer agent — customer-centric mortgage package generator."""

from __future__ import annotations

from decimal import Decimal
from typing import cast

from langchain_core.messages import HumanMessage, SystemMessage

from verified_mortgage_agent.domain.enums import LoanType
from verified_mortgage_agent.domain.models import MortgagePackageProposal
from verified_mortgage_agent.orchestrator.config import get_llm
from verified_mortgage_agent.orchestrator.prompts import (
    PACKAGE_DESIGNER_HUMAN,
    PACKAGE_DESIGNER_SYSTEM,
)
from verified_mortgage_agent.orchestrator.state import DesignGraphState
from verified_mortgage_agent.orchestrator.tools import PackageProposalOutput

AGENT_NAME = "package_designer"


def _format_prior_feedback(state: DesignGraphState) -> str:
    """Build the prior-feedback section for the designer prompt."""
    lean_history = state.get("all_lean_feedback", [])
    reviewer_history = state.get("all_reviewer_concerns", [])

    if not lean_history and not reviewer_history:
        return ""

    lines: list[str] = ["== PRIOR ITERATION FEEDBACK =="]
    for i, (lean, reviewer) in enumerate(
        zip(lean_history, reviewer_history, strict=False), start=1
    ):
        lines.append(f"\nIteration {i}:")
        if lean:
            lines.append("  Lean violations:")
            for v in lean:
                lines.append(f"    - {v}")
        else:
            lines.append("  Lean: passed")
        if reviewer:
            lines.append("  Reviewer concerns:")
            for c in reviewer:
                lines.append(f"    - {c}")
    return "\n".join(lines)


def _format_optional_constraints(state: DesignGraphState) -> str:
    goal = state["goal"]
    parts: list[str] = []
    if goal.desired_max_monthly_payment is not None:
        parts.append(
            f"Desired max monthly payment: ${goal.desired_max_monthly_payment}"
        )
    if goal.ownership_horizon_years is not None:
        parts.append(f"Planned ownership horizon: {goal.ownership_horizon_years} years")
    return "\n".join(parts)


def package_designer_node(state: DesignGraphState) -> dict:  # type: ignore[type-arg]
    """LangGraph node: propose a mortgage package for this iteration."""
    situation = state["situation"]
    goal = state["goal"]
    iteration = state.get("iteration", 1)
    max_iterations = state.get("max_iterations", 3)

    llm = get_llm(AGENT_NAME).with_structured_output(PackageProposalOutput)
    response = cast(
        PackageProposalOutput,
        llm.invoke([
            SystemMessage(content=PACKAGE_DESIGNER_SYSTEM),
            HumanMessage(content=PACKAGE_DESIGNER_HUMAN.format(
                applicant_name=situation.name,
                annual_income=situation.annual_income_usd,
                monthly_debt=situation.debt_obligations_monthly_usd,
                credit_score=situation.credit_score,
                employment_status=situation.employment_status.value,
                employment_months=situation.employment_months_current,
                liquid_assets=situation.assets_liquid_usd,
                target_price=goal.target_property_price,
                down_payment=goal.available_down_payment,
                priority=goal.priority.value,
                optional_constraints=_format_optional_constraints(state),
                iteration=iteration,
                max_iterations=max_iterations,
                prior_feedback_section=_format_prior_feedback(state),
            )),
        ]),
    )

    proposal = MortgagePackageProposal(
        loan_type=LoanType(response.loan_type),
        principal_usd=Decimal(response.principal_usd),
        term_years=response.term_years,
        estimated_rate_pct=Decimal(response.estimated_rate_pct),
        rationale=response.rationale,
        customer_benefit=response.customer_benefit,
        estimated_monthly_pi=Decimal(response.estimated_monthly_pi),
        special_considerations=response.special_considerations,
        iteration=iteration,
    )

    return {
        "current_proposal": proposal,
        "all_proposals": [proposal],
        "iteration": iteration + 1,
    }
