#!/bin/bash
# HR Compliance Analytics — Docker entrypoint
set -e

MODE="${1:-app}"

case "$MODE" in
    # ------------------------------------------------------------------
    # Full pipeline: generate data + transform + validate + govern
    # ------------------------------------------------------------------
    pipeline)
        echo "=== Running full data pipeline ==="
        python pipelines/ingest/main.py
        python pipelines/bronze_to_silver.py
        python pipelines/silver_to_gold.py
        python pipelines/validation_engine.py
        python pipelines/governance.py
        echo "=== Pipeline complete ==="
        ;;

    # ------------------------------------------------------------------
    # Generate synthetic data only (Bronze)
    # ------------------------------------------------------------------
    generate)
        echo "=== Generating synthetic data ==="
        python pipelines/ingest/main.py
        echo "=== Bronze data generated ==="
        ;;

    # ------------------------------------------------------------------
    # Transform only (Bronze -> Silver -> Gold)
    # ------------------------------------------------------------------
    transform)
        echo "=== Running transformations ==="
        python pipelines/bronze_to_silver.py
        python pipelines/silver_to_gold.py
        echo "=== Transform complete ==="
        ;;

    # ------------------------------------------------------------------
    # Run tests
    # ------------------------------------------------------------------
    test)
        echo "=== Running test suite ==="
        python -m pytest tests/ -v
        ;;

    # ------------------------------------------------------------------
    # Default: launch Dash app (auto-generates data if missing)
    # ------------------------------------------------------------------
    app|*)
        # Check if data exists, generate if missing
        if [ ! -f data/silver/dim_employee.parquet ]; then
            echo "=== Data not found. Generating... ==="
            python pipelines/ingest/main.py
            python pipelines/bronze_to_silver.py
            python pipelines/silver_to_gold.py
            python pipelines/validation_engine.py
            python pipelines/governance.py
            echo "=== Data generation complete ==="
        else
            echo "=== Existing data found, launching app ==="
        fi

        echo "=== HR Compliance Analytics running on http://0.0.0.0:8050 ==="
        exec python app/main.py
        ;;
esac
