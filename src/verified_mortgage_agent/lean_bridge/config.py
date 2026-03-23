"""Configuration for the Lean bridge.

The binary path is resolved in this order:
  1. ``LEAN_VERIFIER_BIN`` env var (absolute path)
  2. ``<repo_root>/lean/.lake/build/bin/verify-trace``  (local dev build)
"""

from __future__ import annotations

import os
from pathlib import Path

# Walk up from this file to the repo root
_REPO_ROOT = Path(__file__).parents[4]
_DEFAULT_BIN = _REPO_ROOT / "lean" / ".lake" / "build" / "bin" / "verify-trace"


def get_binary_path() -> Path:
    """Return the path to the ``verify-trace`` binary."""
    env_val = os.environ.get("LEAN_VERIFIER_BIN")
    if env_val:
        return Path(env_val)
    return _DEFAULT_BIN


def get_timeout_seconds() -> int:
    """Maximum time (seconds) to wait for the verifier to complete."""
    return int(os.environ.get("LEAN_VERIFIER_TIMEOUT", "30"))
