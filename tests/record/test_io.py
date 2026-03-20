import json
import tempfile
from pathlib import Path

import pytest

from verified_mortgage_agent.domain.enums import RoutingOutcome
from verified_mortgage_agent.record.io import (
    RecordSchemaVersionError,
    RecordValidationError,
    loads,
    read,
    serialize,
    write,
)
from verified_mortgage_agent.record.models import DecisionRecord, RoutingDecision


def make_record(application_approvable):  # type: ignore[no-untyped-def]
    decision = RoutingDecision(
        application_id=application_approvable.id,
        agent_name="underwriter",
        outcome=RoutingOutcome.APPROVE,
        confidence_score=0.9,
        model_id="anthropic/claude-sonnet-4-6",
    )
    return DecisionRecord(
        application=application_approvable,
        decisions=[decision],
        final_outcome=RoutingOutcome.APPROVE,
        model_id="anthropic/claude-sonnet-4-6",
    )


def test_write_and_read_roundtrip(application_approvable) -> None:  # type: ignore[no-untyped-def]
    record = make_record(application_approvable)
    with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
        path = Path(f.name)
    write(record, path)
    loaded = read(path)
    assert loaded.record_id == record.record_id


def test_version_mismatch_raises(application_approvable) -> None:  # type: ignore[no-untyped-def]
    record = make_record(application_approvable)
    data = json.loads(serialize(record))
    data["schema_version"] = "0.0.1"

    with pytest.raises(RecordSchemaVersionError):
        loads(json.dumps(data))


def test_invalid_json_raises(application_approvable) -> None:  # type: ignore[no-untyped-def]
    record = make_record(application_approvable)
    data = json.loads(serialize(record))
    del data["final_outcome"]

    with pytest.raises(RecordValidationError):
        loads(json.dumps(data))
