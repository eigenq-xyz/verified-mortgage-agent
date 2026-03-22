"""FastAPI application for the verified mortgage agent.

Endpoints:
  POST /applications/process   — run the full pipeline
  POST /records/verify         — run the Lean verifier on an existing record
  GET  /schema                 — return the DecisionRecord JSON schema
  GET  /health                 — liveness check
"""

from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from verified_mortgage_agent.domain.models import MortgageApplication
from verified_mortgage_agent.lean_bridge.result import VerificationResult
from verified_mortgage_agent.record.models import DecisionRecord

app = FastAPI(
    title="Verified Mortgage Agent",
    version="0.1.0",
    description=(
        "LLM-orchestrated mortgage processing with Lean 4 formal verification."
    ),
)


class ProcessRequest(BaseModel):
    application: MortgageApplication
    skip_verify: bool = False


class ProcessResponse(BaseModel):
    record: DecisionRecord
    verification: VerificationResult | None = None


class VerifyRequest(BaseModel):
    record: DecisionRecord


class VerifyResponse(BaseModel):
    verification: VerificationResult


@app.get("/health")
def health() -> dict:  # type: ignore[type-arg]
    return {"status": "ok"}


@app.get("/schema")
def schema() -> dict:  # type: ignore[type-arg]
    from verified_mortgage_agent.record.schema import get_json_schema
    return get_json_schema()


@app.post("/applications/process", response_model=ProcessResponse)
async def process_application(request: ProcessRequest) -> ProcessResponse:
    """Run the LangGraph orchestrator and optionally verify the decision record."""
    from verified_mortgage_agent.lean_bridge.runner import (
        LeanBinaryNotFoundError,
        LeanVerifierError,
        verify,
    )
    from verified_mortgage_agent.orchestrator.runner import run_async

    record = await run_async(request.application)

    verification: VerificationResult | None = None
    if not request.skip_verify:
        try:
            verification = verify(record)
        except (LeanBinaryNotFoundError, LeanVerifierError):
            # Verification is best-effort; don't fail the request
            pass

    return ProcessResponse(record=record, verification=verification)


@app.post("/records/verify", response_model=VerifyResponse)
def verify_record(request: VerifyRequest) -> VerifyResponse:
    """Run the Lean verifier on a previously generated decision record."""
    from verified_mortgage_agent.lean_bridge.runner import (
        LeanBinaryNotFoundError,
        LeanVerifierError,
        verify,
    )

    try:
        result = verify(request.record)
    except LeanBinaryNotFoundError as exc:
        raise HTTPException(status_code=503, detail=str(exc))
    except LeanVerifierError as exc:
        raise HTTPException(status_code=500, detail=str(exc))

    return VerifyResponse(verification=result)
