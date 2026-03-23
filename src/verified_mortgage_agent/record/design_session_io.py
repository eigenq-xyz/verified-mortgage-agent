"""Serialization and deserialization for DesignSessionRecord (schema v2.0.0)."""

from __future__ import annotations

import json
from pathlib import Path

from pydantic import ValidationError

from verified_mortgage_agent.record.models import (
    DESIGN_SESSION_SCHEMA_VERSION,
    DesignSessionRecord,
)


class DesignSessionSchemaVersionError(Exception):
    """Raised when a record file has an incompatible schema_version."""


class DesignSessionValidationError(Exception):
    """Raised when a record file fails Pydantic validation."""


def serialize(record: DesignSessionRecord) -> str:
    return record.model_dump_json(indent=2)


def write(record: DesignSessionRecord, path: Path) -> None:
    path.write_text(serialize(record))


def read(path: Path) -> DesignSessionRecord:
    raw = json.loads(path.read_text())

    version = raw.get("schema_version")
    if version != DESIGN_SESSION_SCHEMA_VERSION:
        raise DesignSessionSchemaVersionError(
            f"Record schema version {version!r} is incompatible "
            f"with expected {DESIGN_SESSION_SCHEMA_VERSION!r}"
        )

    try:
        return DesignSessionRecord.model_validate(raw)
    except ValidationError as exc:
        raise DesignSessionValidationError(str(exc)) from exc


def loads(data: str) -> DesignSessionRecord:
    raw = json.loads(data)

    version = raw.get("schema_version")
    if version != DESIGN_SESSION_SCHEMA_VERSION:
        raise DesignSessionSchemaVersionError(
            f"Record schema version {version!r} is incompatible "
            f"with expected {DESIGN_SESSION_SCHEMA_VERSION!r}"
        )

    try:
        return DesignSessionRecord.model_validate(raw)
    except ValidationError as exc:
        raise DesignSessionValidationError(str(exc)) from exc
