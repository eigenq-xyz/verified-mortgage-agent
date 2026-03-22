"""Result types returned by the Lean verifier."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class Violation:
    """A single invariant violation reported by the Lean verifier."""

    invariant_name: str
    description: str
    severity: str = "error"


@dataclass(frozen=True)
class VerificationResult:
    """Outcome of running the Lean ``verify-trace`` binary."""

    passed: bool
    record_id: str
    violations: list[Violation] = field(default_factory=list)
    lean_version: str = ""
    raw: dict = field(default_factory=dict)  # type: ignore[type-arg]

    @property
    def ok(self) -> bool:
        return self.passed and len(self.violations) == 0
