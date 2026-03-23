.PHONY: install lint test test-all test-design schema lean-build lean-test lean-test-predatory

install:
	uv sync --all-extras

lint:
	uv run ruff check src/ tests/
	uv run mypy src/

test:
	uv run pytest -m "not integration" --cov=src --cov-report=term-missing

test-all:
	uv run pytest --cov=src --cov-report=term-missing

test-design:
	uv run pytest -m "not integration" tests/orchestrator/test_design_agents.py \
		tests/orchestrator/test_design_graph.py \
		tests/integration/test_design_end_to_end.py -v

schema:
	uv run python scripts/generate_schema.py

lean-build:
	cd lean && lake build MortgageVerifier && lake build verify-trace

lean-test:
	cd lean && lake exe verify-trace ../tests/fixtures/sample_record_valid.json
	cd lean && lake exe verify-trace ../tests/fixtures/sample_record_dti_violation.json; \
		[ $$? -eq 1 ] && echo "PASS: violation correctly detected" || echo "FAIL: expected exit code 1"

lean-test-predatory:
	uv run pytest -m integration tests/integration/test_predatory_lean.py -v
