# HR Compliance Analytics — Makefile
# Quick commands for local dev and Docker operations.

.PHONY: help app pipeline test clean dev docker-build docker-up docker-down docker-test

# Default target
help:
	@echo "HR Compliance Analytics — Makefile"
	@echo ""
	@echo "  make dev             Run Dash app locally"
	@echo "  make pipeline        Run full data pipeline locally"
	@echo "  make test            Run test suite"
	@echo "  make clean           Remove generated data"
	@echo ""
	@echo "  make docker-build    Build Docker image"
	@echo "  make docker-up       Start app in Docker (http://localhost:8050)"
	@echo "  make docker-down     Stop Docker containers"
	@echo "  make docker-pipeline Run pipeline inside Docker"
	@echo "  make docker-test     Run tests inside Docker"

# ---------------------------------------------------------------------------
# Local development
# ---------------------------------------------------------------------------
dev:
	DASH_HOST=0.0.0.0 DASH_DEBUG_MODE=true python app/main.py

pipeline:
	python pipelines/run_pipeline.py

test:
	python -m pytest tests/ -v

clean:
	rm -rf data/bronze/*.csv data/bronze/**/*.csv
	rm -rf data/silver/*.parquet data/gold/*.parquet
	rm -rf data/gold/governance/*.json
	rm -rf data/gold/validation_manifest.json
	rm -f tmp*.py tmp*.txt

# ---------------------------------------------------------------------------
# Docker
# ---------------------------------------------------------------------------
docker-build:
	docker compose build

docker-up:
	docker compose up -d
	@echo "App running at http://localhost:8050"

docker-down:
	docker compose down

docker-pipeline:
	docker compose run --rm app pipeline

docker-test:
	docker compose run --rm app test
