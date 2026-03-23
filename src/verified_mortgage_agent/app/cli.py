"""Command-line interface for the verified mortgage agent.

Commands:
  vma process <application.json>   — run the full pipeline end-to-end
  vma verify  <record.json>        — run the Lean verifier on an existing record
  vma schema  dump                 — print the DecisionRecord JSON Schema
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
