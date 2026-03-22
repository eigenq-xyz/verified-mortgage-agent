"""Unit tests for lean_bridge/runner.py — Lean binary is mocked."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from verified_mortgage_agent.domain.enums import RoutingOutcome
from verified_mortgage_agent.lean_bridge.runner import (
    LeanBinaryNotFoundError,
    LeanVerifierError,
    _parse_output,
    verify,
)
from verified_mortgage_agent.record.models import DecisionRecord, RoutingDecision


def _make_record(application_approvable, outcome: RoutingOutcome) -> DecisionRecord:  # type: ignore[no-untyped-def]
    decision = RoutingDecision(
        application_id=application_approvable.id,
        agent_name="underwriter",
        outcome=outcome,
        confidence_score=0.9,
        model_id="anthropic/claude-sonnet-4-6",
    )
    return DecisionRecord(
        application=application_approvable,
        decisions=[decision],
        final_outcome=outcome,
        model_id="anthropic/claude-sonnet-4-6",
    )


# ── _parse_output ────────────────────────────────────────────────────────────

def test_parse_output_passed() -> None:
    data = {"passed": True, "recordId": "abc-123", "violations": [], "leanVersion": "4.26.0"}
    result = _parse_output(json.dumps(data))
    assert result.passed is True
    assert result.ok is True
    assert result.record_id == "abc-123"


def test_parse_output_violations() -> None:
    data = {
        "passed": False,
        "recordId": "abc-123",
        "violations": [
            {"invariantName": "dti_cap", "description": "DTI 0.50 exceeds cap", "severity": "error"}
        ],
        "leanVersion": "4.26.0",
    }
    result = _parse_output(json.dumps(data))
    assert result.passed is False
    assert len(result.violations) == 1
    assert result.violations[0].invariant_name == "dti_cap"


def test_parse_output_bad_json_raises() -> None:
    with pytest.raises(LeanVerifierError, match="non-JSON"):
        _parse_output("not json")


# ── verify() with mocked subprocess ─────────────────────────────────────────

def test_verify_binary_not_found_raises(application_approvable) -> None:  # type: ignore[no-untyped-def]
    record = _make_record(application_approvable, RoutingOutcome.APPROVE)

    with patch(
        "verified_mortgage_agent.lean_bridge.runner.get_binary_path",
        return_value=Path("/nonexistent/verify-trace"),
    ):
        with pytest.raises(LeanBinaryNotFoundError):
            verify(record)


def test_verify_success(application_approvable) -> None:  # type: ignore[no-untyped-def]
    record = _make_record(application_approvable, RoutingOutcome.APPROVE)
    stdout = json.dumps({
        "passed": True,
        "recordId": str(record.record_id),
        "violations": [],
        "leanVersion": "4.26.0",
    })

    mock_proc = MagicMock()
    mock_proc.returncode = 0
    mock_proc.stdout = stdout
    mock_proc.stderr = ""

    with patch(
        "verified_mortgage_agent.lean_bridge.runner.get_binary_path",
        return_value=Path("/fake/verify-trace"),
    ), patch("pathlib.Path.exists", return_value=True), patch(
        "subprocess.run", return_value=mock_proc
    ):
        result = verify(record)

    assert result.ok is True


def test_verify_violation_exit_1(application_approvable) -> None:  # type: ignore[no-untyped-def]
    record = _make_record(application_approvable, RoutingOutcome.APPROVE)
    stdout = json.dumps({
        "passed": False,
        "recordId": str(record.record_id),
        "violations": [
            {"invariantName": "dti_cap", "description": "DTI exceeds cap", "severity": "error"}
        ],
        "leanVersion": "4.26.0",
    })

    mock_proc = MagicMock()
    mock_proc.returncode = 1
    mock_proc.stdout = stdout
    mock_proc.stderr = ""

    with patch(
        "verified_mortgage_agent.lean_bridge.runner.get_binary_path",
        return_value=Path("/fake/verify-trace"),
    ), patch("pathlib.Path.exists", return_value=True), patch(
        "subprocess.run", return_value=mock_proc
    ):
        result = verify(record)

    assert result.passed is False
    assert len(result.violations) == 1


def test_verify_parse_error_exit_2_raises(application_approvable) -> None:  # type: ignore[no-untyped-def]
    record = _make_record(application_approvable, RoutingOutcome.APPROVE)

    mock_proc = MagicMock()
    mock_proc.returncode = 2
    mock_proc.stdout = "parse error"
    mock_proc.stderr = ""

    with patch(
        "verified_mortgage_agent.lean_bridge.runner.get_binary_path",
        return_value=Path("/fake/verify-trace"),
    ), patch("pathlib.Path.exists", return_value=True), patch(
        "subprocess.run", return_value=mock_proc
    ):
        with pytest.raises(LeanVerifierError, match="parse error"):
            verify(record)
