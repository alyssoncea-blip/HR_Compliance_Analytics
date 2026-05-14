# AGENTS.md

## Project Identity

Portfolio project: **Plataforma de Auditoria Trabalhista Inteligente** — an intelligent labor audit & people analytics platform for the Brazilian sanitation sector. Inspired by Aegea Saneamento's multi-state operations.

## What Exists Now

- `Docs/Plataforma de Auditoria Trabalhista Inteligente com Engenharia de Dados, Governança e IA.txt` — full specification (single source of truth for scope)
- `Docs/CCTs/` — real Collective Bargaining Agreements (ACTs) from 3 states, archived offline

## CCT Source Layout

```
Docs/CCTs/
  MG/Copasa/2023-2024, 2024-2025, 2025-2027  (44h jornada)
  RJ/Aguas-do-Rio/2023-2024, 2024-2025, 2025-2026  (44h, múltiplas concessionárias)
  RN/CAERN/2020-2022, 2022-2024, 2024-2026  (30h adm / 3x3 operacional — diferencial crítico)
```

All ACTs downloaded from official union sites (Sindágua-MG, Sindágua-RJ, Sindágua-RN). They are signed and registered with the Ministry of Labor.

## Key Domain Facts

- **Setor**: Saneamento básico (água e esgoto)
- **3 estados com regras diferentes**: MG (Copasa/estatal, 44h), RJ (Águas do Rio/privada, 44h), RN (CAERN/estatal, 30h)
- **Principais regras a validar**: jornada, horas extras (50%/100%), adicional noturno, periculosidade (30%), insalubridade (40%), banco de horas, reajustes, pisos salariais
- **Fonte real**: ACTs baixados (única fonte real do projeto)
- **Dados simulados**: folha de pagamento, cartão de ponto, comprovantes financeiros (gerados sinteticamente)

## Tech Stack (Actual)

- **Core**: Python 3.11+, SQL, DuckDB (in-process OLAP), Pandas
- **Frontend**: Dash + Plotly (7 dashboards, Bootstrap components, corporate theme)
- **Data formats**: CSV (bronze), Parquet/Zstd (silver/gold), JSON (governance)
- **Data Quality & Governance**: 48 automated checks (completude, unicidade, integ_ref, consistencia, validade), data catalog (5618-line JSON), lineage docs, audit manifest
- **Validation**: 32 labor compliance rules cross-referencing ponto x folha x financeiro x CCT x cadastro
- **IA/NLP**: Entity extraction treemap (CCT rule classification, entity recognition)
- **Orchestration**: Sequential Python script (phased pipeline). Planned: Dagster/Prefect
- **Cloud**: Local-only. Planned: GCP/AWS with BigQuery/Redshift

## Architecture

**Camadas**: Bronze (landing → raw CSV) → Silver (curated → typed Parquet + lineage) → Gold (analytics → SCD2 + monthly facts + pre-aggregations)

**Pipelines** (all in `pipelines/`):
| # | Script | Phase |
|---|--------|-------|
| 1 | `ingest/main.py` | Synthetic data generation (10k employees, 7 phases, 32 inconsistency types) |
| 2 | `bronze_to_silver.py` | Schema standardization, type casting, lineage columns |
| 3 | `silver_to_gold.py` | SCD2 employee dim, monthly consolidated fact, passivo fact, 5 aggregations |
| 4 | `validation_engine.py` | 32-rule validation with financial impact calculation |
| 5 | `governance.py` | 48 quality checks, catalog, lineage, manifest |

**Star schema**: 7 fact tables + 5 dimensions + SCD2 versioning + 5 pre-aggregations.

## Conventions

- Portuguese for domain documentation, business rules, and CCT content
- English for code (Python, SQL, config files)
- All dashboards in `app/`, all pipelines in `pipelines/`, synthetic data gen in `pipelines/ingest/`
- CCT PDFs are reference material — do not edit them, only read/extract rules
- Data is reproducible: `random.seed(SEED + N)` across all generators

## How to Run

### Local

```bash
# Generate data + run pipelines
python pipelines/ingest/main.py
python pipelines/bronze_to_silver.py
python pipelines/silver_to_gold.py
python pipelines/validation_engine.py
python pipelines/governance.py

# Launch dashboards
python app/main.py                    # → http://localhost:8050

# Run tests
python -m pytest tests/ -v
```

### Docker

```bash
# Build and launch (auto-generates data on first run)
docker compose up -d                  # → http://localhost:8050

# Run pipeline inside container
docker compose run --rm app pipeline

# Run tests inside container
docker compose run --rm app test

# Stop
docker compose down
```

### Makefile shortcuts

```bash
make dev              # local dev server
make pipeline         # full data pipeline
make test             # test suite
make docker-build     # build Docker image
make docker-up        # launch via Docker
```
