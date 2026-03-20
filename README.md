# verified-mortgage-agent

LLM-orchestrated mortgage application processing with Lean 4 formal verification of routing decisions.

A LangGraph multi-agent system processes mortgage applications through specialized roles (intake, risk, compliance, underwriter). Every routing decision is recorded in a structured decision record, which is then validated against formal invariants written in Lean 4.

## Architecture

```
MortgageApplication (JSON)
    │
    ▼
LangGraph Orchestrator
    ├── IntakeAgent          — document completeness
    ├── RiskAssessmentAgent  — DTI, LTV, credit score (parallel)
    ├── ComplianceAgent      — regulatory rules         (parallel)
    └── UnderwriterAgent     — final decision
    │
    ▼
DecisionRecord (JSON)
    │
    ▼
Lean 4 Checker (lake exe verify-trace)
    │
    ▼
VerificationResult { passed, violations }
```

The LLM side is provider-agnostic — configure `LLM_MODEL=anthropic/claude-sonnet-4-6` or `openai/gpt-4o` (or per-agent overrides) via environment variables.

## Setup

1. Install [elan](https://github.com/leanprover/elan) (Lean toolchain manager)
2. Install [uv](https://docs.astral.sh/uv/)
3. Copy `.env.example` to `.env` and fill in your API key(s)

```bash
make install      # install Python dependencies
make lean-build   # build the Lean verifier
```

## Usage

```bash
# Process an application end-to-end
vma process path/to/application.json

# Only run the Lean verifier on an existing decision record
vma verify path/to/record.json

# Print the JSON Schema for DecisionRecord
vma schema dump
```

Or run the HTTP API:

```bash
uvicorn verified_mortgage_agent.app.api:app --reload
# POST /process   — full pipeline
# POST /verify    — Lean verification only
# GET  /health    — checks Lean binary availability
```

## Development

```bash
make lint       # ruff + mypy
make test       # unit tests (mocked LLM + Lean)
make test-all   # includes integration tests (requires live credentials)
make schema     # regenerate schemas/decision_record.json
```
