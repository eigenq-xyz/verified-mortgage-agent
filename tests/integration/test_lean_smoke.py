"""Integration smoke test — invokes the real ``verify-trace`` binary.

Marked ``integration`` so they are excluded from the default ``make test`` run.
Requires the binary to be built: ``make lean-build``
"""

from __future__ import annotations

from pathlib import Path

import pytest

from verified_mortgage_agent.lean_bridge.runner import verify_file

FIXTURES = Path(__file__).parents[1] / "fixtures"


@pytest.mark.integration
def test_valid_record_passes() -> None:
    result = verify_file(FIXTURES / "sample_record_valid.json")
    assert result.ok, f"Expected pass but got violations: {result.violations}"


@pytest.mark.integration
def test_dti_violation_record_fails() -> None:
    result = verify_file(FIXTURES / "sample_record_dti_violation.json")
    assert not result.ok
    names = [v.invariant_name for v in result.violations]
    assert any("dti" in n.lower() for n in names), f"Expected DTI violation, got: {names}"
