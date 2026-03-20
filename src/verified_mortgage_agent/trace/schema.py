"""JSON Schema generation for the ExecutionTrace contract."""

from __future__ import annotations

import json
from pathlib import Path

from verified_mortgage_agent.trace.models import ExecutionTrace

SCHEMA_PATH = Path(__file__).parents[3] / "schemas" / "execution_trace.json"


def get_json_schema() -> dict:  # type: ignore[type-arg]
    return ExecutionTrace.model_json_schema()


def dump_schema(path: Path = SCHEMA_PATH) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    schema = get_json_schema()
    path.write_text(json.dumps(schema, indent=2) + "\n")
