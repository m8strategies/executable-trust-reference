#!/usr/bin/env python3
"""Regenerate the synthetic baseline reports.

    python scripts/generate_evaluation_report.py

A thin wrapper over evaluation/run_baseline.py, provided because "regenerate the
report" is a distinct intent from "run the gate" even though they share an
implementation.
"""

from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "evaluation"))

from run_baseline import main as run_baseline  # noqa: E402

if __name__ == "__main__":
    raise SystemExit(run_baseline([]))
