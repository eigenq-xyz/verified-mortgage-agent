"""Practitioner test suite — real Lean binary verifies each predatory fixture.

A compliance officer, lending professional, or regulator should be able to
point to this suite and say: "this system correctly identifies every major
category of predatory, reckless, or fraudulent mortgage product from the
last 30 years."

Run with:
    pytest -m integration tests/integration/test_predatory_lean.py -v

Each parameterised case is annotated with its legal or textbook basis.
Fixtures expected to PASS Lean are marked ``# KNOWN GAP`` and document
what invariant would be needed to catch the case.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from verified_mortgage_agent.lean_bridge.runner import verify
from verified_mortgage_agent.record.io import read

PREDATORY_DIR = Path(__file__).parents[1] / "fixtures" / "predatory"

# ---------------------------------------------------------------------------
# Parameterised fixture table
#
# Columns:
#   fixture_name                  — filename in tests/fixtures/predatory/
#   expected_pass                 — True if Lean should accept the record
#   expected_violation_substrings — non-empty only when expected_pass=False;
#                                   each string must appear in at least one
#                                   violation message
#   legal_basis                   — human-readable note, appears in test output
# ---------------------------------------------------------------------------

_CASES = [
    # -------------------------------------------------------------------------
    # Category 1 — Straight-up silly
    # -------------------------------------------------------------------------
    pytest.param(
        "silly_credit_350_jumbo.json",
        False,
        ["creditFloor"],
        "Broker origination fraud 2004–2006: fees collected on obviously "
        "unqualified borrowers (credit score 350, JUMBO loan).",
        id="silly_credit_350_jumbo",
    ),
    pytest.param(
        "silly_dti_095.json",
        False,
        ["dtiCap"],
        "Qualification inflation: broker-inflated income figures; DTI 0.95 "
        "fires all four DTI cap invariants simultaneously.",
        id="silly_dti_095",
    ),
    pytest.param(
        "silly_ltv_110_conventional.json",
        False,
        ["ltvCap"],
        "Bear Stearns / Countrywide 2006–2007: CONVENTIONAL loans routinely "
        "exceeding appraised value (LTV 1.10).",
        id="silly_ltv_110_conventional",
    ),
    pytest.param(
        "silly_escalate_no_reason.json",
        False,
        ["escalation"],
        "OCC enforcement actions 2007–2010: rubber-stamp escalation reviews "
        "with no documented rationale.",
        id="silly_escalate_no_reason",
    ),
    # -------------------------------------------------------------------------
    # Category 2 — Subtle / complex
    # -------------------------------------------------------------------------
    pytest.param(
        "subtle_fha_dti_exactly_at_cap.json",
        False,
        ["dtiCap"],
        "Off-by-one threshold errors in automated underwriting: DTI exactly "
        "at the FHA cap (0.50) must fire — the cap is strict, not inclusive.",
        id="subtle_fha_dti_exactly_at_cap",
    ),
    pytest.param(
        "subtle_va_high_dti.json",
        False,
        ["dtiCap"],
        "VA loan churning (VA Circular 26-18-13, 2018): serial refinancing "
        "incrementally raised DTI to 0.45, above the 0.41 VA cap.  "
        "VA LTV cap must NOT fire (VA allows 100% financing).",
        id="subtle_va_high_dti",
    ),
    pytest.param(
        "subtle_jumbo_one_point_below_credit_floor.json",
        False,
        ["creditFloor"],
        "Credit-score gaming: brokers temporarily boosted score to just "
        "below the 700 JUMBO floor (699) then reversed post-closing.",
        id="subtle_jumbo_one_point_below_credit_floor",
    ),
    pytest.param(
        "subtle_outcome_mismatch.json",
        False,
        ["finalOutcome", "consistency"],
        "Ameriquest Mortgage internal fraud (FTC settlement 2006): "
        "back-office staff manually altered decision records to convert "
        "REJECT to APPROVE post-fact.",
        id="subtle_outcome_mismatch",
    ),
    pytest.param(
        "subtle_empty_decisions.json",
        False,
        ["finalOutcome", "consistency"],
        "Ghost loans: loans present in securitisation pools with no "
        "underwriting documentation (discovered in post-crisis forensic audits).",
        id="subtle_empty_decisions",
    ),
    # -------------------------------------------------------------------------
    # Category 3 — Outright predatory / scammy
    # -------------------------------------------------------------------------
    pytest.param(
        "predatory_equity_stripper.json",
        False,
        ["dtiCap"],
        "FTC v. Associates First Capital Corporation (2002): equity stripping "
        "via cash-out refinancing with DTI ~0.85; foreclosure captured equity. "
        "Settled for $215M.",
        id="predatory_equity_stripper",
    ),
    pytest.param(
        "predatory_wamu_option_arm.json",
        False,
        ["dtiCap"],
        "Washington Mutual Option ARM / Pick-a-Pay (2003–2008): borrowers "
        "earning $45K/year given $500K loans; existing-debt DTI alone was 0.48. "
        "FDIC enforcement; $17B loss 2008.",
        id="predatory_wamu_option_arm",
    ),
    pytest.param(
        "predatory_ninja_2006.json",
        True,  # KNOWN GAP
        [],
        "KNOWN GAP — In re Countrywide Financial (C.D. Cal. 2010): NINJA loans "
        "(No Income, No Job, No Assets). Income fraud undetectable from a single "
        "DecisionRecord without income-verification fields.  Lean correctly passes "
        "this record; a Stage-1 deterministic check is needed.",
        id="predatory_ninja_2006",
    ),
    pytest.param(
        "predatory_balloon_retiree.json",
        False,
        ["dtiCap"],
        "People v. Ameriquest Mortgage (multi-state settlement 2006): "
        "balloon/short-term loans sold to elderly borrowers on fixed income; "
        "DTI ~0.643 on retirement income makes default inevitable.",
        id="predatory_balloon_retiree",
    ),
    pytest.param(
        "predatory_churning_refi.json",
        True,  # KNOWN GAP
        [],
        "KNOWN GAP — VA Circular 26-18-13 (2018); Ameriquest 2006; CFPB 2019: "
        "serial refinancing to collect origination fees. All caps satisfied in "
        "isolation; temporal history across records required to detect churning.",
        id="predatory_churning_refi",
    ),
    # -------------------------------------------------------------------------
    # Category 4 — Valid edge cases (must NOT over-block)
    # -------------------------------------------------------------------------
    pytest.param(
        "valid_va_zero_down.json",
        True,
        [],
        "Regression: VA 100% financing (LTV 1.00) is explicitly allowed. "
        "CONVENTIONAL/FHA LTV caps must not apply.",
        id="valid_va_zero_down",
    ),
    pytest.param(
        "valid_fha_credit_at_floor.json",
        True,
        [],
        "Boundary inclusive: FHA credit floor is 580. Score exactly 580 must "
        "not trigger the floor invariant (< 580 triggers, = 580 does not).",
        id="valid_fha_credit_at_floor",
    ),
    pytest.param(
        "valid_jumbo_strong.json",
        True,
        [],
        "Clean JUMBO case: score 780, DTI 0.30, LTV ~0.649. All caps satisfied.",
        id="valid_jumbo_strong",
    ),
    pytest.param(
        "valid_escalate_with_nonempty_reason.json",
        True,
        [],
        "Escalation with non-empty, non-whitespace reason must pass "
        "escalationRequiresReason invariant.",
        id="valid_escalate_with_nonempty_reason",
    ),
    pytest.param(
        "valid_conventional_borderline_dti.json",
        True,
        [],
        "Float boundary: DTI 0.4290 is unambiguously below the 0.43 cap.",
        id="valid_conventional_borderline_dti",
    ),
]


@pytest.mark.integration
@pytest.mark.parametrize(
    "fixture_name,expected_pass,expected_violation_substrings,legal_basis",
    _CASES,
)
def test_predatory_fixture(
    fixture_name: str,
    expected_pass: bool,
    expected_violation_substrings: list[str],
    legal_basis: str,
) -> None:
    """Verify each practitioner fixture against the Lean binary.

    Prints ``legal_basis`` on failure to give the practitioner context.
    """
    record = read(PREDATORY_DIR / fixture_name)
    result = verify(record)

    if expected_pass:
        assert result.ok, (
            f"Expected Lean to PASS {fixture_name} but got violations: "
            f"{result.violations}\n\nLegal basis: {legal_basis}"
        )
    else:
        assert not result.ok, (
            f"Expected Lean to FAIL {fixture_name} but it passed.\n\n"
            f"Legal basis: {legal_basis}"
        )
        violation_text = " ".join(result.violations).lower()
        for substring in expected_violation_substrings:
            assert substring.lower() in violation_text, (
                f"Expected violation containing {substring!r} in {fixture_name}.\n"
                f"Got violations: {result.violations}\n"
                f"Legal basis: {legal_basis}"
            )
