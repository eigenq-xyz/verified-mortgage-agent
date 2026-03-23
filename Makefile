.PHONY: install lint test test-all schema lean-build lean-test

install:
	uv sync --all-extras

lint:
	uv run ruff check src/ tests/
	uv run mypy src/

test:
	uv run pytest -m "not integration" --cov=src --cov-report=term-missing

test-all:
	uv run pytest --cov=src --cov-report=term-missing

schema:
	uv run python scripts/generate_schema.py

lean-build:
	cd lean && lake build MortgageVerifier && lake build verify-trace

lean-test:
	cd lean && lake exe verify-trace ../tests/fixtures/sample_record_valid.json
	cd lean && lake exe verify-trace ../tests/fixtures/sample_record_dti_violation.json; \
		[ $$? -eq 1 ] && echo "PASS: violation correctly detected" || echo "FAIL: expected exit code 1"
