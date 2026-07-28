SHELL := /bin/bash

UV ?= uv
UV_DEFAULT_INDEX ?= https://pypi.org/simple
UV_RUN := $(UV) run --default-index $(UV_DEFAULT_INDEX)
PYTEST := $(UV_RUN) pytest

.PHONY: help setup skills test-python test-hpc test-rust test-protocol test

help: ## Show available targets
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "%-16s %s\n", $$1, $$2}'

setup: ## Create the Python 3.11 environment with uv
	@command -v $(UV) >/dev/null 2>&1 || { echo "uv is required"; exit 1; }
	$(UV) sync --default-index $(UV_DEFAULT_INDEX) --python 3.11.13 --dev

skills: ## Validate the vendored local Ion skills
	@command -v ion >/dev/null 2>&1 || { echo "Ion is required"; exit 1; }
	ion --json validate

test-python: ## Run protocol and autoresearch unit tests
	$(PYTEST) -q \
		research/test_check_gate.py \
		research/test_care_bdd_design.py \
		autoresearch/test_autoresearch_protocol.py

test-hpc: ## Test bounded-run and Slurm adapters without touching a cluster
	$(PYTEST) -q \
		autoresearch/test_run_experiment.py \
		autoresearch/test_materialize_slurm_failures.py \
		scripts/tests/test_cluster_profile.py \
		scripts/tests/test_cluster_guardrail.py \
		scripts/tests/test_cluster_probe.py \
		scripts/tests/test_harness_slurm.py

test-rust: ## Run the locked Rust BDD/SAT/XAG test suite
	cargo fmt --all -- --check
	cargo test --locked --all-features --release

test-protocol: ## Check the frozen public protocol gate
	$(UV_RUN) python research/check_gate.py --phase protocol

test: test-python test-hpc test-rust test-protocol ## Run the complete local baseline
