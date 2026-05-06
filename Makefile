.PHONY: install test lint format format-check type-check check normalize-sample clean

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

clean:
	rm -rf artifacts/ logs/ .pytest_cache/ .mypy_cache/ .ruff_cache/
	find . -type d -name __pycache__ -prune -exec rm -rf {} +
