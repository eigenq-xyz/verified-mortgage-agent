"""Trace serialization and deserialization."""

from __future__ import annotations

import json
from pathlib import Path

from pydantic import ValidationError

from verified_mortgage_agent.trace.models import ExecutionTrace, SCHEMA_VERSION


class TraceSchemaVersionError(Exception):
    """Raised when a trace file has an incompatible schema_version."""


class TraceValidationError(Exception):
    """Raised when a trace file fails Pydantic validation."""


def serialize(trace: ExecutionTrace) -> str:
    return trace.model_dump_json(indent=2)


def write(trace: ExecutionTrace, path: Path) -> None:
    path.write_text(serialize(trace))


def read(path: Path) -> ExecutionTrace:
    raw = json.loads(path.read_text())

    version = raw.get("schema_version")
    if version != SCHEMA_VERSION:
        raise TraceSchemaVersionError(
            f"Trace schema version {version!r} is incompatible "
            f"with expected {SCHEMA_VERSION!r}"
        )

    try:
        return ExecutionTrace.model_validate(raw)
    except ValidationError as exc:
        raise TraceValidationError(str(exc)) from exc


def loads(data: str) -> ExecutionTrace:
    raw = json.loads(data)

    version = raw.get("schema_version")
    if version != SCHEMA_VERSION:
        raise TraceSchemaVersionError(
            f"Trace schema version {version!r} is incompatible "
            f"with expected {SCHEMA_VERSION!r}"
        )

    try:
        return ExecutionTrace.model_validate(raw)
    except ValidationError as exc:
        raise TraceValidationError(str(exc)) from exc
