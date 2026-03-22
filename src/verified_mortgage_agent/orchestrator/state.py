"""LangGraph state definition for the mortgage routing orchestrator."""

from __future__ import annotations

import operator
from typing import Annotated, Literal, TypedDict

from verified_mortgage_agent.domain.enums import RoutingOutcome
from verified_mortgage_agent.domain.models import MortgageApplication
from verified_mortgage_agent.record.models import ReasoningStep, RoutingDecision

AgentName = Literal[
    "intake",
    "risk_assessment",
    "compliance",
    "underwriter",
]


class GraphState(TypedDict):
    """State for the LangGraph mortgage orchestrator.

    Uses ``Annotated[list, operator.add]`` reducers so parallel branches
    (risk + compliance) accumulate decisions without race conditions.
    """

    application: MortgageApplication
    decisions: Annotated[list[RoutingDecision], operator.add]
    routing_steps: Annotated[list[ReasoningStep], operator.add]
    next_agent: AgentName | Literal["END"] | None
    escalation_required: bool
    escalation_reason: str | None
    final_outcome: RoutingOutcome | None
