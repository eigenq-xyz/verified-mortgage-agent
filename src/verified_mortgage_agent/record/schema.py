"""JSON Schema generation for DecisionRecord (v1) and DesignSessionRecord (v2)."""

from __future__ import annotations

import json
from pathlib import Path

from verified_mortgage_agent.record.models import DecisionRecord, DesignSessionRecord

SCHEMA_PATH = Path(__file__).parents[3] / "schemas" / "decision_record.json"
DESIGN_SESSION_SCHEMA_PATH = (
    Path(__file__).parents[3] / "schemas" / "design_session_record.json"
)


def get_json_schema() -> dict:  # type: ignore[type-arg]
    return DecisionRecord.model_json_schema()


def dump_schema(path: Path = SCHEMA_PATH) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    schema = get_json_schema()
    path.write_text(json.dumps(schema, indent=2) + "\n")


def get_design_session_schema() -> dict:  # type: ignore[type-arg]
    return DesignSessionRecord.model_json_schema()


def dump_design_session_schema(path: Path = DESIGN_SESSION_SCHEMA_PATH) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    schema = get_design_session_schema()
    path.write_text(json.dumps(schema, indent=2) + "\n")
