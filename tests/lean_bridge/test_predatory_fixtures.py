"""Structural tests for the practitioner fixture files (no Lean binary required).

Validates that each fixture:
  - parses as a valid v1 DecisionRecord
  - has the expected loan_type, outcome, and escalation fields

These tests run in the default ``make test`` target.  The real Lean
verification of each fixture lives in ``tests/integration/test_predatory_lean.py``
and requires ``@pytest.mark.integration``.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from verified_mortgage_agent.domain.enums import LoanType, RoutingOutcome
from verified_mortgage_agent.record.io import read
from verified_mortgage_agent.record.models import DecisionRecord

PREDATORY_DIR = Path(__file__).parents[1] / "fixtures" / "predatory"


def _load(name: str) -> DecisionRecord:
    return read(PREDATORY_DIR / name)


# ---------------------------------------------------------------------------
# Category 1 — Silly: parseable and has expected structural properties
# ---------------------------------------------------------------------------


def test_silly_credit_350_jumbo_parses() -> None:
    rec = _load("silly_credit_350_jumbo.json")
    assert rec.application.loan.loan_type == LoanType.JUMBO
    assert rec.application.applicant.credit_score == 350
    assert rec.final_outcome == RoutingOutcome.APPROVE


def test_silly_dti_095_parses() -> None:
    rec = _load("silly_dti_095.json")
    # DTI = 2850 / (36000/12) = 0.95
    dti = rec.application.debt_to_income_ratio
    assert float(dti) == pytest.approx(0.95, abs=1e-6)
    assert rec.final_outcome == RoutingOutcome.APPROVE


def test_silly_ltv_110_conventional_parses() -> None:
    rec = _load("silly_ltv_110_conventional.json")
    ltv = rec.application.loan_to_value_ratio
    assert float(ltv) == pytest.approx(1.10, abs=1e-6)
    assert rec.application.loan.loan_type == LoanType.CONVENTIONAL


def test_silly_escalate_no_reason_parses() -> None:
    rec = _load("silly_escalate_no_reason.json")
    assert rec.final_outcome == RoutingOutcome.ESCALATE_TO_UNDERWRITER
    assert rec.decisions[0].escalation_reason is None


# ---------------------------------------------------------------------------
# Category 2 — Subtle
# ---------------------------------------------------------------------------


def test_subtle_fha_dti_exactly_at_cap_parses() -> None:
    rec = _load("subtle_fha_dti_exactly_at_cap.json")
    dti = rec.application.debt_to_income_ratio
    assert float(dti) == pytest.approx(0.50, abs=1e-6)
    assert rec.application.loan.loan_type == LoanType.FHA


def test_subtle_va_high_dti_parses() -> None:
    rec = _load("subtle_va_high_dti.json")
    dti = rec.application.debt_to_income_ratio
    assert float(dti) == pytest.approx(0.45, abs=1e-6)
    assert rec.application.loan.loan_type == LoanType.VA
    # LTV must be exactly 1.00 (zero-down VA loan)
    ltv = rec.application.loan_to_value_ratio
    assert float(ltv) == pytest.approx(1.00, abs=1e-6)


def test_subtle_jumbo_one_below_credit_floor_parses() -> None:
    rec = _load("subtle_jumbo_one_point_below_credit_floor.json")
    assert rec.application.applicant.credit_score == 699
    assert rec.application.loan.loan_type == LoanType.JUMBO


def test_subtle_outcome_mismatch_parses() -> None:
    rec = _load("subtle_outcome_mismatch.json")
    # final_outcome says APPROVE but last decision says REJECT
    assert rec.final_outcome == RoutingOutcome.APPROVE
    assert rec.decisions[-1].outcome == RoutingOutcome.REJECT


def test_subtle_empty_decisions_parses() -> None:
    rec = _load("subtle_empty_decisions.json")
    assert rec.decisions == []
    assert rec.final_outcome == RoutingOutcome.APPROVE


# ---------------------------------------------------------------------------
# Category 3 — Predatory
# ---------------------------------------------------------------------------


def test_predatory_equity_stripper_high_dti() -> None:
    rec = _load("predatory_equity_stripper.json")
    dti = rec.application.debt_to_income_ratio
    assert float(dti) > 0.43  # conventional cap


def test_predatory_wamu_option_arm_dti_exceeds_cap() -> None:
    rec = _load("predatory_wamu_option_arm.json")
    dti = rec.application.debt_to_income_ratio
    assert float(dti) > 0.43
    assert rec.application.loan.loan_type == LoanType.CONVENTIONAL


def test_predatory_ninja_2006_near_zero_dti() -> None:
    """NINJA loan: stated income near-zero → DTI effectively 0; KNOWN GAP."""
    rec = _load("predatory_ninja_2006.json")
    assert rec.application.loan.loan_type == LoanType.FHA
    # All standard cap checks will pass — income fraud not detectable
    dti = rec.application.debt_to_income_ratio
    assert float(dti) < 0.43


def test_predatory_balloon_retiree_dti_exceeds_cap() -> None:
    rec = _load("predatory_balloon_retiree.json")
    dti = rec.application.debt_to_income_ratio
    assert float(dti) > 0.43
    assert rec.application.applicant.employment_status.value == "RETIRED"


def test_predatory_churning_refi_passes_caps() -> None:
    """Serial refinancing: all caps satisfied; KNOWN GAP — temporal pattern."""
    rec = _load("predatory_churning_refi.json")
    dti = rec.application.debt_to_income_ratio
    assert float(dti) < 0.43  # passes — churning invisible in single record


# ---------------------------------------------------------------------------
# Category 4 — Valid edge cases
# ---------------------------------------------------------------------------


def test_valid_va_zero_down_ltv_one() -> None:
    rec = _load("valid_va_zero_down.json")
    ltv = rec.application.loan_to_value_ratio
    assert float(ltv) == pytest.approx(1.00, abs=1e-6)
    assert rec.application.loan.loan_type == LoanType.VA


def test_valid_fha_credit_exactly_at_floor() -> None:
    rec = _load("valid_fha_credit_at_floor.json")
    assert rec.application.applicant.credit_score == 580
    assert rec.application.loan.loan_type == LoanType.FHA
    # LTV must be ≤ 0.965
    ltv = rec.application.loan_to_value_ratio
    assert float(ltv) <= 0.965


def test_valid_jumbo_strong_all_caps_satisfied() -> None:
    rec = _load("valid_jumbo_strong.json")
    assert rec.application.applicant.credit_score >= 700
    assert float(rec.application.debt_to_income_ratio) < 0.43
    ltv = rec.application.loan_to_value_ratio
    assert float(ltv) <= 0.80
    assert rec.application.loan.loan_type == LoanType.JUMBO


def test_valid_escalate_with_nonempty_reason() -> None:
    rec = _load("valid_escalate_with_nonempty_reason.json")
    assert rec.final_outcome == RoutingOutcome.ESCALATE_TO_UNDERWRITER
    assert rec.decisions[0].escalation_reason is not None
    assert rec.decisions[0].escalation_reason.strip() != ""


def test_valid_conventional_borderline_dti_below_cap() -> None:
    rec = _load("valid_conventional_borderline_dti.json")
    dti = rec.application.debt_to_income_ratio
    assert float(dti) < 0.43
    assert float(dti) > 0.42  # genuinely borderline
