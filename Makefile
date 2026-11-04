# One-command checks for humans and agents (AGENTS.md -> Commands). Mirrors .github/workflows/ci.yml.
UV ?= uv run --extra dev
EPHE := data/ephe/sepl_18.se1

.PHONY: setup lint test verify
setup:            ## install dev deps and fetch the pinned ephemeris
	uv sync --extra dev
	$(UV) python scripts/fetch_ephemeris.py

$(EPHE):
	$(UV) python scripts/fetch_ephemeris.py

lint:             ## ruff + import-linter contracts
	$(UV) ruff check src tests scripts
	$(UV) lint-imports

test: $(EPHE)     ## pytest (oracle tests skip unless the oracle extra is installed)
	$(UV) pytest

verify: lint test ## everything CI runs; must pass before any task is reported done
	@echo "verify: OK"
