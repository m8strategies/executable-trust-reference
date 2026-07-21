# =============================================================================
# executable-trust-reference — developer entry points
#
# Every gate that CI enforces is reachable from this file, and `make all` runs
# the same sequence CI runs. If `make all` passes locally and CI fails, that
# discrepancy is a defect in this Makefile.
#
# The package requires no API keys, no network access, no database, and no
# cloud credentials. Every target below runs offline.
# =============================================================================

PYTHON ?= python

.DEFAULT_GOAL := help

.PHONY: help install lint format format-check typecheck test contracts \
        traceability boundary baseline baseline-check release-check all

help:
	@echo "executable-trust-reference — available targets"
	@echo ""
	@echo "  install         Install the package and dev dependencies (editable)"
	@echo "  lint            Run ruff lint checks"
	@echo "  format          Apply ruff formatting"
	@echo "  format-check    Verify formatting without modifying files"
	@echo "  typecheck       Run mypy in strict mode"
	@echo "  test            Run pytest with coverage (fails under 90%)"
	@echo "  contracts       Validate contracts and schemas"
	@echo "  traceability    Verify every contract rule id maps to a test"
	@echo "  boundary        Verify the publication boundary holds"
	@echo "  baseline        Regenerate the reference baseline reports"
	@echo "  baseline-check  Verify committed baseline reports are current"
	@echo "  release-check   Validate release metadata placeholders"
	@echo "  all             lint, format-check, typecheck, contracts,"
	@echo "                  traceability, boundary, test, baseline-check"

install:
	$(PYTHON) -m pip install -e ".[dev]"

lint:
	ruff check .

format:
	ruff format .

format-check:
	ruff format --check .

typecheck:
	mypy

test:
	pytest --cov=executable_trust --cov-report=term-missing --cov-fail-under=90

contracts:
	$(PYTHON) scripts/validate_contracts.py

traceability:
	$(PYTHON) scripts/validate_traceability.py

boundary:
	$(PYTHON) scripts/validate_publication_boundary.py

baseline:
	$(PYTHON) evaluation/run_baseline.py

baseline-check:
	$(PYTHON) evaluation/run_baseline.py --check

release-check:
	$(PYTHON) scripts/validate_release_metadata.py

all: lint format-check typecheck contracts traceability boundary test baseline-check
	@echo "All checks passed."
