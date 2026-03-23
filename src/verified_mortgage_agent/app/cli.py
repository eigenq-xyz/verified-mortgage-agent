"""Command-line interface for the verified mortgage agent.

Commands:
  vma process <application.json>       — run the full v1 pipeline end-to-end
  vma verify  <record.json>            — run the Lean verifier on an existing record
  vma schema  dump                     — print the DecisionRecord JSON Schema
  vma design  <situation.json>         — run the Phase 4 generative design loop
"""

from __future__ import annotations

import json
from pathlib import Path

import typer

app = typer.Typer(
    name="vma",
    help="LLM-orchestrated mortgage processor with Lean 4 formal verification.",
    add_completion=False,
)


@app.command()
def process(
    application_path: Path = typer.Argument(  # noqa: B008
        ..., help="Path to a MortgageApplication JSON file.", exists=True
    ),
    output: Path = typer.Option(  # noqa: B008
        None, "--output", "-o", help="Write DecisionRecord JSON to this path."
    ),
    skip_verify: bool = typer.Option(  # noqa: B008
        False, "--skip-verify", help="Skip Lean verification step."
    ),
) -> None:
    """Process a mortgage application end-to-end and verify the decision record."""
    from dotenv import load_dotenv

    from verified_mortgage_agent.domain.models import MortgageApplication
    from verified_mortgage_agent.lean_bridge.runner import (
        LeanBinaryNotFoundError,
        verify,
    )
    from verified_mortgage_agent.orchestrator.runner import run_sync
    from verified_mortgage_agent.record.io import write

    load_dotenv()

    typer.echo(f"Loading application from {application_path} …")
    raw = json.loads(application_path.read_text())
    try:
        application = MortgageApplication.model_validate(raw)
    except Exception as exc:
        typer.echo(f"ERROR: Invalid application JSON: {exc}", err=True)
        raise typer.Exit(1) from exc

    typer.echo("Running orchestrator …")
    record = run_sync(application)

    if output:
        write(record, output)
        typer.echo(f"Decision record written to {output}")
    else:
        typer.echo(json.loads(record.model_dump_json(indent=2)).__str__()[:200] + " …")

    if skip_verify:
        typer.echo("Verification skipped.")
        return

    typer.echo("Running Lean verifier …")
    try:
        result = verify(record)
    except LeanBinaryNotFoundError as exc:
        typer.echo(f"WARNING: {exc}", err=True)
        typer.echo("Skipping verification (build the Lean binary with `make lean-build`).")
        return

    if result.ok:
        typer.echo("✓ All invariants passed.")
    else:
        typer.echo(f"✗ {len(result.violations)} violation(s):", err=True)
        for v in result.violations:
            typer.echo(f"  [{v.invariant_name}] {v.description}", err=True)
        raise typer.Exit(1)


@app.command()
def verify(
    record_path: Path = typer.Argument(  # noqa: B008
        ..., help="Path to a DecisionRecord JSON file.", exists=True
    ),
) -> None:
    """Run the Lean verifier on an existing decision record."""
    from verified_mortgage_agent.lean_bridge.runner import (
        LeanBinaryNotFoundError,
        LeanVerifierError,
        verify_file,
    )

    try:
        result = verify_file(record_path)
    except LeanBinaryNotFoundError as exc:
        typer.echo(f"ERROR: {exc}", err=True)
        raise typer.Exit(2) from exc
    except LeanVerifierError as exc:
        typer.echo(f"ERROR: {exc}", err=True)
        raise typer.Exit(2) from exc

    if result.ok:
        typer.echo("✓ All invariants passed.")
    else:
        typer.echo(f"✗ {len(result.violations)} violation(s):", err=True)
        for v in result.violations:
            typer.echo(f"  [{v.invariant_name}] {v.description}", err=True)
        raise typer.Exit(1)


@app.command()
def design(
    situation_path: Path = typer.Argument(  # noqa: B008
        ..., help="Path to an ApplicantSituation JSON file.", exists=True
    ),
    goal: Path = typer.Option(  # noqa: B008
        None, "--goal", "-g", help="Path to a MortgageGoal JSON file."
    ),
    output: Path = typer.Option(  # noqa: B008
        None, "--output", "-o", help="Write DesignSessionRecord JSON to this path."
    ),
    max_iter: int = typer.Option(  # noqa: B008
        3, "--max-iter", help="Maximum design iterations (default: 3)."
    ),
) -> None:
    """Run the Phase 4 generative mortgage package design loop."""
    from dotenv import load_dotenv

    from verified_mortgage_agent.domain.models import ApplicantSituation, MortgageGoal
    from verified_mortgage_agent.orchestrator.runner import run_design_sync
    from verified_mortgage_agent.record.design_session_io import serialize

    load_dotenv()

    typer.echo(f"Loading applicant situation from {situation_path} …")
    situation_raw = json.loads(situation_path.read_text())
    try:
        applicant_situation = ApplicantSituation.model_validate(situation_raw)
    except Exception as exc:
        typer.echo(f"ERROR: Invalid situation JSON: {exc}", err=True)
        raise typer.Exit(1) from exc

    mortgage_goal: MortgageGoal
    if goal:
        typer.echo(f"Loading goal from {goal} …")
        goal_raw = json.loads(goal.read_text())
        try:
            mortgage_goal = MortgageGoal.model_validate(goal_raw)
        except Exception as exc:
            typer.echo(f"ERROR: Invalid goal JSON: {exc}", err=True)
            raise typer.Exit(1) from exc
    else:
        # Infer a minimal goal from the situation
        typer.echo("No goal file provided — inferring balanced goal from situation.")
        from decimal import Decimal

        from verified_mortgage_agent.domain.enums import GoalPriority

        target_price = applicant_situation.assets_liquid_usd * 5 or Decimal("400000")
        down = applicant_situation.assets_liquid_usd
        mortgage_goal = MortgageGoal(
            target_property_price=target_price,
            available_down_payment=down,
            priority=GoalPriority.BALANCED,
        )

    typer.echo(f"Running design loop (max {max_iter} iteration(s)) …")
    record = run_design_sync(applicant_situation, mortgage_goal, max_iterations=max_iter)

    _print_design_outcome(record)

    if output:
        output.write_text(serialize(record))
        typer.echo(f"\nDesign session record written to {output}")


def _print_design_outcome(record: object) -> None:
    """Print a human-readable summary of a DesignSessionRecord outcome."""
    from verified_mortgage_agent.record.models import DesignSessionRecord

    assert isinstance(record, DesignSessionRecord)
    typer.echo(f"\nOutcome: {record.final_outcome.value}")

    if record.final_outcome.value == "PENDING_REVIEW":
        _print_pending_review(record)
    elif record.final_outcome.value == "ESCALATED":
        typer.echo("Max iterations reached without a passing package.")
        typer.echo("Full session history sent to senior underwriter.")
        if record.escalation_context:
            typer.echo(f"\nEscalation summary:\n{record.escalation_context}")
    elif record.final_outcome.value in ("HARD_BLOCK", "DOCUMENTS_REQUIRED"):
        _print_block(record)


def _print_pending_review(record: object) -> None:
    from verified_mortgage_agent.record.models import DesignSessionRecord

    assert isinstance(record, DesignSessionRecord)
    if record.verification_skipped:
        typer.echo(
            "WARNING: Lean verification was skipped (binary unavailable). "
            "This record must NOT be treated as conditionally approvable "
            "until Lean is re-run.",
            err=True,
        )
    else:
        typer.echo("A proposed package has been found and Lean-verified.")
    if record.accepted_proposal:
        p = record.accepted_proposal
        typer.echo(
            f"  Proposal: {p.loan_type} ${p.principal_usd} "
            f"over {p.term_years}yr @ {p.estimated_rate_pct}%"
        )
        typer.echo(f"  Monthly P&I: ${p.estimated_monthly_pi}")
        typer.echo(f"  Customer benefit: {p.customer_benefit}")
    typer.echo("\nNext step: package sent to human loan officer for sign-off.")


def _print_block(record: object) -> None:
    from verified_mortgage_agent.record.models import DesignSessionRecord

    assert isinstance(record, DesignSessionRecord)
    typer.echo(f"{record.final_outcome.value}: {record.block_reason}")
    if record.qualification_path:
        label = (
            "Qualification roadmap:"
            if record.final_outcome.value == "HARD_BLOCK"
            else "Required documents:"
        )
        typer.echo(f"\n{label}")
        for step in record.qualification_path:
            typer.echo(f"  • {step}")


schema_app = typer.Typer(help="JSON schema utilities.")
app.add_typer(schema_app, name="schema")


@schema_app.command("dump")
def schema_dump(
    output: Path = typer.Option(  # noqa: B008
        None, "--output", "-o", help="Write to file instead of stdout."
    ),
) -> None:
    """Print the JSON Schema for DecisionRecord."""
    from verified_mortgage_agent.record.schema import get_json_schema

    text = json.dumps(get_json_schema(), indent=2)
    if output:
        output.write_text(text + "\n")
        typer.echo(f"Schema written to {output}")
    else:
        typer.echo(text)


if __name__ == "__main__":
    app()
