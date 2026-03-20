#!/usr/bin/env python
"""Generate schemas/execution_trace.json from Pydantic models.

Run via: make schema  (or: uv run python scripts/generate_schema.py)
"""

import sys
from pathlib import Path

# Allow running from repo root without installing the package
sys.path.insert(0, str(Path(__file__).parents[1] / "src"))

from verified_mortgage_agent.trace.schema import SCHEMA_PATH, dump_schema

if __name__ == "__main__":
    dump_schema()
    print(f"Schema written to {SCHEMA_PATH}")
