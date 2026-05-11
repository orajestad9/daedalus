.PHONY: install test lint format format-check type-check check normalize-sample fake-summary-check graph-fake-summary-check evaluation-check comparison-check ollama-local-check ollama-summary-local-check db-up db-down db-logs db-reset migrate-db db-check fake-model-db-check fake-summary-db-check evaluation-db-check clean

PYTHON ?= .venv/bin/python

install:
	$(PYTHON) -m pip install -r requirements-dev.txt

test:
	$(PYTHON) -m pytest

lint:
	$(PYTHON) -m ruff check .

format:
	$(PYTHON) -m ruff format .

format-check:
	$(PYTHON) -m ruff format --check .

type-check:
	$(PYTHON) -m mypy src tests

check: test lint format-check type-check

normalize-sample:
	$(PYTHON) -m daedalus.cli normalize-reviews --input sample_data/readysetrentables_reviews/airbnb_reviews_sample.csv --output artifacts/readysetrentables/normalized_reviews.json

fake-summary-check:
	@$(MAKE) clean
	$(PYTHON) -m daedalus.cli normalize-reviews --input sample_data/readysetrentables_reviews/airbnb_reviews_sample.csv --output artifacts/readysetrentables/normalized_reviews.json
	$(PYTHON) -m daedalus.cli summarize-review-themes-fake --input artifacts/readysetrentables/normalized_reviews.json --output artifacts/readysetrentables/review_theme_summary.md
	@test -f artifacts/readysetrentables/review_theme_summary.md || (echo "Missing artifacts/readysetrentables/review_theme_summary.md"; exit 1)
	@echo "fake-summary-check passed: artifacts/readysetrentables/review_theme_summary.md was created."
	@$(MAKE) clean

graph-fake-summary-check:
	@$(MAKE) clean
	$(PYTHON) -m daedalus.cli run-review-graph --input sample_data/readysetrentables_reviews/airbnb_reviews_sample.csv --output artifacts/readysetrentables/normalized_reviews.json
	@test -f artifacts/readysetrentables/review_theme_summary.md || (echo "Missing artifacts/readysetrentables/review_theme_summary.md"; exit 1)
	@echo "graph-fake-summary-check passed: LangGraph created artifacts/readysetrentables/review_theme_summary.md."
	@$(MAKE) clean

evaluation-check:
	@$(MAKE) clean
	.venv/bin/daedalus run-workflow --manifest workflows/readysetrentables_review_normalization.yaml --execution-engine langgraph
	@test -f artifacts/readysetrentables/review_theme_summary.md || (echo "Missing artifacts/readysetrentables/review_theme_summary.md"; exit 1)
	.venv/bin/daedalus evaluate-review-theme-summary --summary artifacts/readysetrentables/review_theme_summary.md --output-json artifacts/readysetrentables/review_theme_summary.evaluation.json --output-md artifacts/readysetrentables/review_theme_summary.evaluation.md
	@test -f artifacts/readysetrentables/review_theme_summary.evaluation.json || (echo "Missing artifacts/readysetrentables/review_theme_summary.evaluation.json"; exit 1)
	@test -f artifacts/readysetrentables/review_theme_summary.evaluation.md || (echo "Missing artifacts/readysetrentables/review_theme_summary.evaluation.md"; exit 1)
	@echo "evaluation-check passed: review theme summary evaluation JSON and Markdown artifacts were created."
	@$(MAKE) clean

comparison-check:
	@$(MAKE) clean
	.venv/bin/daedalus run-workflow --manifest workflows/readysetrentables_review_normalization.yaml --execution-engine langgraph
	@test -f artifacts/readysetrentables/review_theme_summary.md || (echo "Missing artifacts/readysetrentables/review_theme_summary.md"; exit 1)
	@mkdir -p artifacts/readysetrentables/comparison
	@cp artifacts/readysetrentables/review_theme_summary.md artifacts/readysetrentables/comparison/baseline_review_theme_summary.md
	@cp artifacts/readysetrentables/review_theme_summary.md artifacts/readysetrentables/comparison/candidate_review_theme_summary.md
	.venv/bin/daedalus compare-review-theme-summaries --baseline artifacts/readysetrentables/comparison/baseline_review_theme_summary.md --candidate artifacts/readysetrentables/comparison/candidate_review_theme_summary.md --output-json artifacts/readysetrentables/review_theme_summary.comparison.json --output-md artifacts/readysetrentables/review_theme_summary.comparison.md
	@test -f artifacts/readysetrentables/review_theme_summary.comparison.json || (echo "Missing artifacts/readysetrentables/review_theme_summary.comparison.json"; exit 1)
	@test -f artifacts/readysetrentables/review_theme_summary.comparison.md || (echo "Missing artifacts/readysetrentables/review_theme_summary.comparison.md"; exit 1)
	@echo "comparison-check passed: review theme summary comparison JSON and Markdown artifacts were created."
	@$(MAKE) clean

ollama-local-check:
	$(PYTHON) -m daedalus.cli ollama-smoke-check --model llama3.1

ollama-summary-local-check:
	@$(MAKE) clean
	$(PYTHON) -m daedalus.cli normalize-reviews --input sample_data/readysetrentables_reviews/airbnb_reviews_sample.csv --output artifacts/readysetrentables/normalized_reviews.json
	$(PYTHON) -m daedalus.cli summarize-review-themes-ollama --input artifacts/readysetrentables/normalized_reviews.json --output artifacts/readysetrentables/review_theme_summary.md --model llama3.1
	@test -f artifacts/readysetrentables/review_theme_summary.md || (echo "Missing artifacts/readysetrentables/review_theme_summary.md"; exit 1)
	@echo "ollama-summary-local-check passed: artifacts/readysetrentables/review_theme_summary.md was created."
	@$(MAKE) clean

db-up:
	docker compose up -d postgres

db-down:
	docker compose down

db-logs:
	docker compose logs -f postgres

db-reset:
	@echo "WARNING: This will stop Postgres and delete the local Docker volume."
	@echo "All local Daedalus Postgres data will be lost."
	docker compose down -v

migrate-db:
	@test -f .env || (echo "Missing .env. Copy .env.example to .env and edit it locally before running migrations."; exit 1)
	@set -a; . ./.env; set +a; $(PYTHON) -m daedalus.cli migrate-db

db-check:
	@test -f .env || (echo "Missing .env. Copy .env.example to .env and edit it locally before running db-check."; exit 1)
	@$(MAKE) db-up; \
	status=0; \
	$(MAKE) migrate-db || status=$$?; \
	if [ $$status -eq 0 ]; then \
		RUN_OUTPUT=$$(set -a; . ./.env; set +a; $(PYTHON) -m daedalus.cli run-workflow --manifest workflows/readysetrentables_review_normalization.yaml --persist 2>&1); \
		status=$$?; \
		printf "%s\n" "$$RUN_OUTPUT"; \
		DETERMINISTIC_RUN_ID=$$(printf "%s\n" "$$RUN_OUTPUT" | sed -n 's/.*run_id=\([^ ]*\).*/\1/p' | head -n 1); \
		if [ $$status -eq 0 ] && [ -z "$$DETERMINISTIC_RUN_ID" ]; then echo "Could not capture run_id from deterministic persisted workflow output."; status=1; fi; \
	fi; \
	if [ $$status -eq 0 ]; then \
		GRAPH_RUN_OUTPUT=$$(set -a; . ./.env; set +a; $(PYTHON) -m daedalus.cli run-workflow --manifest workflows/readysetrentables_review_normalization.yaml --execution-engine langgraph --persist 2>&1); \
		status=$$?; \
		printf "%s\n" "$$GRAPH_RUN_OUTPUT"; \
		LANGGRAPH_RUN_ID=$$(printf "%s\n" "$$GRAPH_RUN_OUTPUT" | sed -n 's/.*run_id=\([^ ]*\).*/\1/p' | head -n 1); \
		if [ $$status -eq 0 ] && [ -z "$$LANGGRAPH_RUN_ID" ]; then echo "Could not capture run_id from LangGraph persisted workflow output."; status=1; fi; \
	fi; \
	if [ $$status -eq 0 ]; then set -a; . ./.env; set +a; $(PYTHON) -m daedalus.cli list-runs --limit 5 || status=$$?; fi; \
	if [ $$status -eq 0 ]; then \
		SHOW_RUN_OUTPUT=$$(set -a; . ./.env; set +a; $(PYTHON) -m daedalus.cli show-run --run-id "$$LANGGRAPH_RUN_ID" 2>&1); \
		status=$$?; \
		printf "%s\n" "$$SHOW_RUN_OUTPUT"; \
		if [ $$status -eq 0 ]; then printf "%s\n" "$$SHOW_RUN_OUTPUT" | grep -q '^steps:' || { echo "show-run output did not include workflow steps."; status=1; }; fi; \
		if [ $$status -eq 0 ]; then printf "%s\n" "$$SHOW_RUN_OUTPUT" | grep -q 'load_reviews' || { echo "show-run output did not include the load_reviews step."; status=1; }; fi; \
		if [ $$status -eq 0 ]; then printf "%s\n" "$$SHOW_RUN_OUTPUT" | grep -q 'review_theme_summary' || { echo "show-run output did not include the review_theme_summary artifact."; status=1; }; fi; \
		if [ $$status -eq 0 ]; then printf "%s\n" "$$SHOW_RUN_OUTPUT" | grep -q '^Model Invocations:' || { echo "show-run output did not include model invocations."; status=1; }; fi; \
		if [ $$status -eq 0 ]; then printf "%s\n" "$$SHOW_RUN_OUTPUT" | grep -q 'provider=fake' || { echo "show-run output did not include the fake model invocation."; status=1; }; fi; \
	fi; \
	$(MAKE) clean; \
	$(MAKE) db-down; \
	exit $$status

fake-model-db-check:
	@test -f .env || (echo "Missing .env. Copy .env.example to .env and edit it locally before running fake-model-db-check."; exit 1)
	@$(MAKE) db-up; \
	status=0; \
	$(MAKE) migrate-db || status=$$?; \
	if [ $$status -eq 0 ]; then \
		RUN_OUTPUT=$$(set -a; . ./.env; set +a; $(PYTHON) -m daedalus.cli run-workflow --manifest workflows/readysetrentables_review_normalization.yaml --persist 2>&1); \
		status=$$?; \
		printf "%s\n" "$$RUN_OUTPUT"; \
		RUN_ID=$$(printf "%s\n" "$$RUN_OUTPUT" | sed -n 's/.*run_id=\([^ ]*\).*/\1/p' | head -n 1); \
		if [ $$status -eq 0 ] && [ -z "$$RUN_ID" ]; then echo "Could not capture run_id from persisted workflow output."; status=1; fi; \
	fi; \
	if [ $$status -eq 0 ]; then \
		set -a; . ./.env; set +a; $(PYTHON) -m daedalus.cli record-fake-model-invocation --run-id "$$RUN_ID" || status=$$?; \
	fi; \
	if [ $$status -eq 0 ]; then \
		SHOW_RUN_OUTPUT=$$(set -a; . ./.env; set +a; $(PYTHON) -m daedalus.cli show-run --run-id "$$RUN_ID" 2>&1); \
		status=$$?; \
		printf "%s\n" "$$SHOW_RUN_OUTPUT"; \
		if [ $$status -eq 0 ]; then printf "%s\n" "$$SHOW_RUN_OUTPUT" | grep -q '^Model Invocations:' || { echo "show-run output did not include model invocations."; status=1; }; fi; \
		if [ $$status -eq 0 ]; then printf "%s\n" "$$SHOW_RUN_OUTPUT" | grep -q 'provider=fake' || { echo "show-run output did not include the fake model invocation."; status=1; }; fi; \
	fi; \
	$(MAKE) clean; \
	$(MAKE) db-down; \
	exit $$status

fake-summary-db-check:
	@test -f .env || (echo "Missing .env. Copy .env.example to .env and edit it locally before running fake-summary-db-check."; exit 1)
	@$(MAKE) db-up; \
	status=0; \
	$(MAKE) migrate-db || status=$$?; \
	if [ $$status -eq 0 ]; then \
		RUN_OUTPUT=$$(set -a; . ./.env; set +a; $(PYTHON) -m daedalus.cli run-workflow --manifest workflows/readysetrentables_review_normalization.yaml --execution-engine langgraph --persist 2>&1); \
		status=$$?; \
		printf "%s\n" "$$RUN_OUTPUT"; \
		RUN_ID=$$(printf "%s\n" "$$RUN_OUTPUT" | sed -n 's/.*run_id=\([^ ]*\).*/\1/p' | head -n 1); \
		if [ $$status -eq 0 ] && [ -z "$$RUN_ID" ]; then echo "Could not capture run_id from persisted workflow output."; status=1; fi; \
	fi; \
	if [ $$status -eq 0 ]; then \
		SHOW_RUN_OUTPUT=$$(set -a; . ./.env; set +a; $(PYTHON) -m daedalus.cli show-run --run-id "$$RUN_ID" 2>&1); \
		status=$$?; \
		printf "%s\n" "$$SHOW_RUN_OUTPUT"; \
		if [ $$status -eq 0 ]; then printf "%s\n" "$$SHOW_RUN_OUTPUT" | grep -q 'review_theme_summary' || { echo "show-run output did not include the review_theme_summary artifact."; status=1; }; fi; \
		if [ $$status -eq 0 ]; then printf "%s\n" "$$SHOW_RUN_OUTPUT" | grep -q '^Model Invocations:' || { echo "show-run output did not include model invocations."; status=1; }; fi; \
		if [ $$status -eq 0 ]; then printf "%s\n" "$$SHOW_RUN_OUTPUT" | grep -q 'provider=fake' || { echo "show-run output did not include the fake model invocation."; status=1; }; fi; \
	fi; \
	$(MAKE) clean; \
	$(MAKE) db-down; \
	exit $$status

evaluation-db-check:
	@test -f .env || (echo "Missing .env. Copy .env.example to .env and edit it locally before running evaluation-db-check."; exit 1)
	@$(MAKE) db-up; \
	status=0; \
	$(MAKE) migrate-db || status=$$?; \
	if [ $$status -eq 0 ]; then \
		$(MAKE) clean; \
		RUN_OUTPUT=$$(set -a; . ./.env; set +a; $(PYTHON) -m daedalus.cli run-workflow --manifest workflows/readysetrentables_review_normalization.yaml --execution-engine langgraph --persist 2>&1); \
		status=$$?; \
		printf "%s\n" "$$RUN_OUTPUT"; \
		RUN_ID=$$(printf "%s\n" "$$RUN_OUTPUT" | sed -n 's/.*run_id=\([^ ]*\).*/\1/p' | head -n 1); \
		if [ $$status -eq 0 ] && [ -z "$$RUN_ID" ]; then echo "Could not capture run_id from persisted workflow output."; status=1; fi; \
	fi; \
	if [ $$status -eq 0 ]; then \
		test -f artifacts/readysetrentables/review_theme_summary.md || { echo "Missing artifacts/readysetrentables/review_theme_summary.md"; status=1; }; \
	fi; \
	if [ $$status -eq 0 ]; then \
		set -a; . ./.env; set +a; $(PYTHON) -m daedalus.cli evaluate-review-theme-summary \
			--summary artifacts/readysetrentables/review_theme_summary.md \
			--run-id "$$RUN_ID" \
			--output-json artifacts/readysetrentables/review_theme_summary.evaluation.json \
			--output-md artifacts/readysetrentables/review_theme_summary.evaluation.md || status=$$?; \
	fi; \
	if [ $$status -eq 0 ]; then \
		test -f artifacts/readysetrentables/review_theme_summary.evaluation.json || { echo "Missing artifacts/readysetrentables/review_theme_summary.evaluation.json"; status=1; }; \
	fi; \
	if [ $$status -eq 0 ]; then \
		test -f artifacts/readysetrentables/review_theme_summary.evaluation.md || { echo "Missing artifacts/readysetrentables/review_theme_summary.evaluation.md"; status=1; }; \
	fi; \
	if [ $$status -eq 0 ]; then \
		set -a; . ./.env; set +a; $(PYTHON) -m daedalus.cli record-evaluation-report-artifact \
			--run-id "$$RUN_ID" \
			--path artifacts/readysetrentables/review_theme_summary.evaluation.json || status=$$?; \
	fi; \
	if [ $$status -eq 0 ]; then \
		SHOW_RUN_OUTPUT=$$(set -a; . ./.env; set +a; $(PYTHON) -m daedalus.cli show-run --run-id "$$RUN_ID" 2>&1); \
		status=$$?; \
		printf "%s\n" "$$SHOW_RUN_OUTPUT"; \
		if [ $$status -eq 0 ]; then printf "%s\n" "$$SHOW_RUN_OUTPUT" | grep -q 'evaluation_report' || { echo "show-run output did not include evaluation_report."; status=1; }; fi; \
	fi; \
	if [ $$status -eq 0 ]; then echo "evaluation-db-check passed: evaluation_report artifact recorded and verified in show-run."; fi; \
	$(MAKE) clean; \
	$(MAKE) db-down; \
	exit $$status

clean:
	rm -rf artifacts/ logs/ .pytest_cache/ .mypy_cache/ .ruff_cache/
	find . -type d -name __pycache__ -prune -exec rm -rf {} +
