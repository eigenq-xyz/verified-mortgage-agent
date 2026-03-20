import json
import tempfile
from pathlib import Path

import pytest

from verified_mortgage_agent.domain.enums import RoutingOutcome
from verified_mortgage_agent.trace.io import (
    TraceSchemaVersionError,
    TraceValidationError,
    loads,
    read,
    serialize,
    write,
)
from verified_mortgage_agent.trace.models import ExecutionTrace, RoutingDecision


def make_trace(application_approvable):  # type: ignore[no-untyped-def]
    decision = RoutingDecision(
        application_id=application_approvable.id,
        agent_name="underwriter",
        outcome=RoutingOutcome.APPROVE,
        confidence_score=0.9,
        model_id="anthropic/claude-sonnet-4-6",
    )
    return ExecutionTrace(
        application=application_approvable,
        decisions=[decision],
        final_outcome=RoutingOutcome.APPROVE,
        model_id="anthropic/claude-sonnet-4-6",
    )


def test_write_and_read_roundtrip(application_approvable) -> None:  # type: ignore[no-untyped-def]
    trace = make_trace(application_approvable)
    with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
        path = Path(f.name)
    write(trace, path)
    loaded = read(path)
    assert loaded.trace_id == trace.trace_id


def test_version_mismatch_raises(application_approvable) -> None:  # type: ignore[no-untyped-def]
    trace = make_trace(application_approvable)
    data = json.loads(serialize(trace))
    data["schema_version"] = "0.0.1"

    with pytest.raises(TraceSchemaVersionError):
        loads(json.dumps(data))


def test_invalid_json_raises(application_approvable) -> None:  # type: ignore[no-untyped-def]
    trace = make_trace(application_approvable)
    data = json.loads(serialize(trace))
    del data["final_outcome"]

    with pytest.raises(TraceValidationError):
        loads(json.dumps(data))
