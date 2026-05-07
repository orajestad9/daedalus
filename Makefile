.PHONY: install test lint format format-check type-check check normalize-sample db-up db-down db-logs db-reset migrate-db db-check clean

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
	if [ $$status -eq 0 ]; then set -a; . ./.env; set +a; $(PYTHON) -m daedalus.cli run-workflow --manifest workflows/readysetrentables_review_normalization.yaml --persist || status=$$?; fi; \
	if [ $$status -eq 0 ]; then set -a; . ./.env; set +a; $(PYTHON) -m daedalus.cli list-runs --limit 5 || status=$$?; fi; \
	$(MAKE) clean; \
	$(MAKE) db-down; \
	exit $$status

clean:
	rm -rf artifacts/ logs/ .pytest_cache/ .mypy_cache/ .ruff_cache/
	find . -type d -name __pycache__ -prune -exec rm -rf {} +
