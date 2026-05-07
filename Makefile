.PHONY: install test lint format format-check type-check check normalize-sample db-up db-down db-logs db-reset clean

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

clean:
	rm -rf artifacts/ logs/ .pytest_cache/ .mypy_cache/ .ruff_cache/
	find . -type d -name __pycache__ -prune -exec rm -rf {} +
