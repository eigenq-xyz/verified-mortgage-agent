"""Decision record serialization and deserialization."""

from __future__ import annotations

import json
from pathlib import Path

from pydantic import ValidationError

from verified_mortgage_agent.record.models import DecisionRecord, SCHEMA_VERSION


class RecordSchemaVersionError(Exception):
    """Raised when a record file has an incompatible schema_version."""


class RecordValidationError(Exception):
    """Raised when a record file fails Pydantic validation."""


def serialize(record: DecisionRecord) -> str:
    return record.model_dump_json(indent=2)


def write(record: DecisionRecord, path: Path) -> None:
    path.write_text(serialize(record))


def read(path: Path) -> DecisionRecord:
    raw = json.loads(path.read_text())

    version = raw.get("schema_version")
    if version != SCHEMA_VERSION:
        raise RecordSchemaVersionError(
            f"Record schema version {version!r} is incompatible "
            f"with expected {SCHEMA_VERSION!r}"
        )

    try:
        return DecisionRecord.model_validate(raw)
    except ValidationError as exc:
        raise RecordValidationError(str(exc)) from exc


def loads(data: str) -> DecisionRecord:
    raw = json.loads(data)

    version = raw.get("schema_version")
    if version != SCHEMA_VERSION:
        raise RecordSchemaVersionError(
            f"Record schema version {version!r} is incompatible "
            f"with expected {SCHEMA_VERSION!r}"
        )

    try:
        return DecisionRecord.model_validate(raw)
    except ValidationError as exc:
        raise RecordValidationError(str(exc)) from exc
