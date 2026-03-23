"""Package reviewer agent — advisory risk and business review of a proposal."""

from __future__ import annotations

from decimal import Decimal, InvalidOperation
from typing import cast

from langchain_core.messages import HumanMessage, SystemMessage

from verified_mortgage_agent.orchestrator.config import get_llm
from verified_mortgage_agent.orchestrator.prompts import (
    PACKAGE_REVIEWER_HUMAN,
    PACKAGE_REVIEWER_SYSTEM,
)
from verified_mortgage_agent.orchestrator.state import DesignGraphState
from verified_mortgage_agent.orchestrator.tools import PackageReviewOutput

AGENT_NAME = "package_reviewer"


def package_reviewer_node(state: DesignGraphState) -> dict:  # type: ignore[type-arg]
    """LangGraph node: advisory review of the current proposal.

    The graph always proceeds to lean_verify regardless of verdict.
    """
    situation = state["situation"]
    proposal = state["current_proposal"]
    goal = state["goal"]

    if proposal is None:
        return {"reviewer_concerns": [], "all_reviewer_concerns": [[]]}

    monthly_income = situation.monthly_income_usd
    existing_dti = (
        situation.debt_obligations_monthly_usd / monthly_income
        if monthly_income else Decimal("999")
    )

    try:
        monthly_pi = Decimal(str(proposal.estimated_monthly_pi))
        projected_total_debt = situation.debt_obligations_monthly_usd + monthly_pi
        projected_dti = (
            projected_total_debt / monthly_income if monthly_income else Decimal("999")
        )
    except InvalidOperation:
        projected_dti = Decimal("999")

    ltv = (
        proposal.principal_usd / goal.target_property_price
        if goal.target_property_price else Decimal("999")
    )

    llm = get_llm(AGENT_NAME).with_structured_output(PackageReviewOutput)
    response = cast(
        PackageReviewOutput,
        llm.invoke([
            SystemMessage(content=PACKAGE_REVIEWER_SYSTEM),
            HumanMessage(content=PACKAGE_REVIEWER_HUMAN.format(
                applicant_name=situation.name,
                annual_income=situation.annual_income_usd,
                credit_score=situation.credit_score,
                monthly_debt=situation.debt_obligations_monthly_usd,
                existing_dti=float(existing_dti),
                loan_type=proposal.loan_type.value,
                principal=proposal.principal_usd,
                term_years=proposal.term_years,
                estimated_rate_pct=proposal.estimated_rate_pct,
                estimated_monthly_pi=proposal.estimated_monthly_pi,
                rationale=proposal.rationale,
                customer_benefit=proposal.customer_benefit,
                special_considerations=", ".join(proposal.special_considerations)
                or "none",
                projected_dti=float(projected_dti),
                ltv=float(ltv),
            )),
        ]),
    )

    concerns = response.concerns if response.verdict == "REVISE" else []
    return {
        "reviewer_concerns": concerns,
        "all_reviewer_concerns": [concerns],
    }
