"""JSON Schema generation for the DecisionRecord contract."""

from __future__ import annotations

import json
from pathlib import Path

from verified_mortgage_agent.record.models import DecisionRecord

SCHEMA_PATH = Path(__file__).parents[3] / "schemas" / "decision_record.json"


def get_json_schema() -> dict:  # type: ignore[type-arg]
    return DecisionRecord.model_json_schema()


def dump_schema(path: Path = SCHEMA_PATH) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    schema = get_json_schema()
    path.write_text(json.dumps(schema, indent=2) + "\n")
