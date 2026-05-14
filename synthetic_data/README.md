# Synthetic Data Generators

This folder organizes the synthetic data generation scripts by source system.
All generators live in `pipelines/ingest/` and are orchestrated via `main.py`.

## Sources

- **payroll/** → Folha de pagamento (pipelines/ingest/gen_payroll.py)
- **time_tracking/** → Cartão de ponto (pipelines/ingest/gen_time.py)
- **financial/** → Comprovantes bancários (pipelines/ingest/gen_payments.py)
- **cct/** → Regras de CCT (pipelines/ingest/config.py)

## Running

```bash
# Generate all data (Bronze)
python -m pipelines.ingest.main

# Bronze → Silver
python pipelines/transform/bronze_to_silver.py

# Silver → Gold
python pipelines/transform/silver_to_gold.py

# Validation engine
python pipelines/reconciliation/validation_engine.py

# Data Quality & Governance
python pipelines/quality/governance.py

# Launch Dashboard
streamlit run app/main.py
```
