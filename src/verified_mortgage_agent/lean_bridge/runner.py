"""Invoke the Lean ``verify-trace`` binary and parse its JSON output.

Exit code contract (from lean/Main.lean):
  0  — all invariants pass
  1  — one or more violations
  2  — parse / schema error

The binary is invoked as:
  ``verify-trace <path-to-record.json>``
"""

from __future__ import annotations

import json
import subprocess
import tempfile
from pathlib import Path

from verified_mortgage_agent.domain.models import (
    ApplicantSituation,
    MortgageGoal,
    MortgagePackageProposal,
)
from verified_mortgage_agent.lean_bridge.config import (
    get_binary_path,
    get_timeout_seconds,
)
from verified_mortgage_agent.lean_bridge.result import VerificationResult, Violation
from verified_mortgage_agent.lean_bridge.synthesis import (
    synthesize_record_from_proposal,
)
from verified_mortgage_agent.record.io import serialize
from verified_mortgage_agent.record.models import DecisionRecord


class LeanBinaryNotFoundError(FileNotFoundError):
    """Raised when the ``verify-trace`` binary cannot be located."""


class LeanVerifierError(RuntimeError):
    """Raised when the verifier exits with an unexpected code or bad JSON."""


def verify(record: DecisionRecord) -> VerificationResult:
    """Write *record* to a temp file, invoke ``verify-trace``, return result."""
    binary = get_binary_path()
    if not binary.exists():
        raise LeanBinaryNotFoundError(
            f"Lean verifier binary not found at {binary}. "
            "Run `make lean-build` to compile it, or set LEAN_VERIFIER_BIN."
        )

    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".json", delete=False
    ) as tmp:
        tmp.write(serialize(record))
        tmp_path = Path(tmp.name)

    try:
        proc = subprocess.run(
            [str(binary), str(tmp_path)],
            capture_output=True,
            text=True,
            timeout=get_timeout_seconds(),
        )
    finally:
        tmp_path.unlink(missing_ok=True)

    if proc.returncode == 2:
        raise LeanVerifierError(
            f"Lean verifier parse error (exit 2):\n{proc.stdout}\n{proc.stderr}"
        )

    if proc.returncode not in (0, 1):
        raise LeanVerifierError(
            f"Lean verifier unexpected exit code {proc.returncode}:\n"
            f"{proc.stdout}\n{proc.stderr}"
        )

    return _parse_output(proc.stdout)


def verify_file(path: Path) -> VerificationResult:
    """Invoke ``verify-trace`` directly on an existing JSON file."""
    binary = get_binary_path()
    if not binary.exists():
        raise LeanBinaryNotFoundError(
            f"Lean verifier binary not found at {binary}."
        )

    proc = subprocess.run(
        [str(binary), str(path)],
        capture_output=True,
        text=True,
        timeout=get_timeout_seconds(),
    )

    if proc.returncode == 2:
        raise LeanVerifierError(
            f"Lean verifier parse error (exit 2):\n{proc.stdout}\n{proc.stderr}"
        )

    if proc.returncode not in (0, 1):
        raise LeanVerifierError(
            f"Lean verifier unexpected exit code {proc.returncode}:\n"
            f"{proc.stdout}\n{proc.stderr}"
        )

    return _parse_output(proc.stdout)


def verify_proposal(
    proposal: MortgagePackageProposal,
    situation: ApplicantSituation,
    goal: MortgageGoal,
) -> VerificationResult:
    """Synthesise a v1 record from *proposal* and run the existing verify().

    The Lean binary never sees a DesignSessionRecord.  Python wraps the
    proposal as a minimal v1 DecisionRecord (outcome=APPROVE, schema 1.0.0)
    and passes it through the unchanged ``verify-trace`` binary.
    """
    record = synthesize_record_from_proposal(proposal, situation, goal)
    return verify(record)


def _parse_output(stdout: str) -> VerificationResult:
    """Parse the JSON output from ``verify-trace``."""
    try:
        data = json.loads(stdout)
    except json.JSONDecodeError as exc:
        raise LeanVerifierError(
            f"Lean verifier produced non-JSON output:\n{stdout}"
        ) from exc

    violations = [
        Violation(
            invariant_name=v.get("invariant_name", "unknown"),
            description=v.get("description", ""),
            severity=v.get("severity", "error"),
        )
        for v in data.get("violations", [])
    ]

    return VerificationResult(
        passed=data.get("passed", False),
        record_id=data.get("record_id", ""),
        violations=violations,
        lean_version=data.get("lean_version", ""),
        raw=data,
    )
