"""
Data Quality & Governance Pipeline
Runs quality checks across Bronze/Silver/Gold, builds data catalog,
and documents lineage. Writes to data/gold/governance/.
"""
import duckdb, os, json, time, hashlib
from datetime import datetime, timezone
from collections import defaultdict

SILVER = "data/silver"
BRONZE = "data/bronze"
GOLD = "data/gold"
GOV = f"{GOLD}/governance"
OBS = f"{GOLD}/observability"
NOW_ISO = datetime.now(timezone.utc).isoformat()

os.makedirs(GOV, exist_ok=True)
os.makedirs(OBS, exist_ok=True)
con = duckdb.connect()

def pq(path): return f"'{SILVER}/{path}.parquet'".replace(chr(92), "/")
def bq(path): return f"'{BRONZE}/{path}.parquet'".replace(chr(92), "/")
def gq(path): return f"'{GOLD}/{path}.parquet'".replace(chr(92), "/")

# Tables to check across layers
TABLES = {
    "bronze": {
        "employees": bq("hr_system/employees"),
        "positions": bq("hr_system/positions"),
        "unions": bq("hr_system/unions"),
        "units": bq("hr_system/units"),
        "time_records": bq("time_clock/time_records"),
        "payroll": bq("payroll/payroll"),
        "bank_payments": bq("bank/bank_payments"),
        "hour_bank": bq("time_clock/hour_bank"),
        "vacations": bq("events/vacations"),
    },
    "silver": {
        "dim_employee": pq("dim_employee"),
        "dim_position": pq("dim_position"),
        "dim_union": pq("dim_union"),
        "dim_unit": pq("dim_unit"),
        "dim_date": pq("dim_date"),
        "fact_payroll": pq("fact_payroll"),
        "fact_time_record": pq("fact_time_record"),
        "fact_payment": pq("fact_payment"),
        "fact_hour_bank": pq("fact_hour_bank"),
        "vacations": pq("vacations"),
        "leaves": pq("leaves"),
        "salary_history": pq("salary_history"),
        "terminations": pq("terminations"),
        "dependents": pq("dependents"),
    },
    "gold": {
        "dim_employee_scd2": gq("dim_employee_scd2"),
        "fact_monthly_employee": gq("fact_monthly_employee"),
        "fact_passivo_trabalhista": gq("fact_passivo_trabalhista"),
        "fact_detected_inconsistency": gq("fact_detected_inconsistency"),
        "agg_unit_monthly": gq("agg_unit_monthly"),
        "agg_union_monthly": gq("agg_union_monthly"),
    },
}

print("=" * 60)
print("DATA QUALITY & GOVERNANCE PIPELINE")
print("=" * 60)

# =========================================================================
# 1. DATA QUALITY CHECKS
# =========================================================================
print("\n[1/3] Running data quality checks...")

quality_results = []

def check(name, layer, path, dimension, sql, severity="medium"):
    """Run a single quality check."""
    try:
        cnt = con.execute(f"SELECT count(*) FROM ({sql}) _q").fetchone()[0]
        total = con.execute(f"SELECT count(*) FROM {path}").fetchone()[0]
        pct = round((total - cnt) / total * 100, 2) if total > 0 else 100.0
        quality_results.append({
            "table_name": name, "layer": layer, "dimension": dimension,
            "check_sql": sql[:200], "fail_count": cnt, "total_count": total,
            "pass_pct": pct, "severity": severity, "status": "FAIL" if cnt > 0 else "PASS",
            "checked_at": NOW_ISO,
        })
        return cnt
    except Exception as e:
        quality_results.append({
            "table_name": name, "layer": layer, "dimension": dimension,
            "check_sql": str(e)[:200], "fail_count": -1, "total_count": -1,
            "pass_pct": 0.0, "severity": "high", "status": "ERROR",
            "checked_at": NOW_ISO,
        })
        return -1

t0 = time.time()
total_checks = 0

for layer, tables in TABLES.items():
    for name, path in tables.items():

        # --- Layer-aware completeness checks ---
        if layer == "bronze":
            if name == "employees":
                total_checks += 1
                check(name, layer, path, "completude",
                      f"SELECT 1 FROM {path} WHERE name IS NULL OR cpf IS NULL OR hire_date IS NULL")
            if name in ("payroll",):
                total_checks += 1
                check(name, layer, path, "completude",
                      f"SELECT 1 FROM {path} WHERE employee_id IS NULL OR gross_total IS NULL")
            if name in ("bank_payments",):
                total_checks += 1
                check(name, layer, path, "completude",
                      f"SELECT 1 FROM {path} WHERE employee_id IS NULL OR expected_amount IS NULL")
            if name == "time_records":
                total_checks += 1
                check(name, layer, path, "completude",
                      f"SELECT 1 FROM {path} WHERE employee_id IS NULL OR date IS NULL", "high")
            if name == "positions":
                total_checks += 1
                check(name, layer, path, "completude",
                      f"SELECT 1 FROM {path} WHERE name IS NULL OR level IS NULL")

        elif layer == "silver":
            if name == "dim_employee":
                total_checks += 1
                check(name, layer, path, "completude",
                      f"SELECT 1 FROM {path} WHERE name IS NULL OR cpf IS NULL OR hire_date IS NULL")
            if name == "dim_position":
                total_checks += 1
                check(name, layer, path, "completude",
                      f"SELECT 1 FROM {path} WHERE name IS NULL OR level IS NULL")
            if name.startswith("fact_payroll"):
                total_checks += 1
                check(name, layer, path, "completude",
                      f"SELECT 1 FROM {path} WHERE employee_id IS NULL OR gross_total IS NULL")
            if name == "fact_payment":
                total_checks += 1
                check(name, layer, path, "completude",
                      f"SELECT 1 FROM {path} WHERE employee_id IS NULL OR expected_amount IS NULL")
            if name == "fact_time_record":
                total_checks += 1
                check(name, layer, path, "completude",
                      f"SELECT 1 FROM {path} WHERE employee_id IS NULL OR date_sk IS NULL", "high")

        elif layer == "gold":
            if name == "dim_employee_scd2":
                total_checks += 1
                check(name, layer, path, "completude",
                      f"SELECT 1 FROM {path} WHERE employee_id IS NULL OR cpf IS NULL")
            if name == "fact_monthly_employee":
                total_checks += 1
                check(name, layer, path, "completude",
                      f"SELECT 1 FROM {path} WHERE employee_id IS NULL OR gross_total IS NULL")
            if name == "fact_passivo_trabalhista":
                total_checks += 1
                check(name, layer, path, "completude",
                      f"SELECT 1 FROM {path} WHERE employee_id IS NULL OR passivo_id IS NULL")

        # --- Uniqueness ---
        pk_cols = {
            "employees": "employee_id", "positions": "position_id",
            "unions": "union_id", "units": "unit_id",
            "time_records": "record_id", "payroll": "payroll_id",
            "bank_payments": "payment_id", "hour_bank": "hour_bank_id",
            "dim_employee": "employee_id", "dim_position": "position_id",
            "dim_union": "union_id", "dim_unit": "unit_id",
            "dim_date": "date_sk",
            "fact_payroll": "payroll_id", "fact_time_record": "record_id",
            "fact_payment": "payment_id", "fact_hour_bank": "hour_bank_id",
            "dim_employee_scd2": "employee_id || '-' || scd_version",
        }
        if name in pk_cols:
            total_checks += 1
            pk = pk_cols[name]
            check(name, layer, path, "unicidade",
                  f"SELECT {pk} FROM {path} GROUP BY {pk} HAVING count(*) > 1", "high")

        # --- Integrity (FK) ---
        if layer == "silver" and name.startswith("fact_"):
            total_checks += 1
            check(name, layer, path, "integ_ref",
                  f"SELECT f.employee_id FROM {path} f LEFT JOIN {pq('dim_employee')} e ON f.employee_id = e.employee_id WHERE e.employee_id IS NULL LIMIT 100",
                  "critical")

        # --- Consistency (range checks) ---
        if "payroll" in name and not name.startswith("fact_monthly"):
            total_checks += 1
            check(name, layer, path, "consistencia",
                  f"SELECT 1 FROM {path} WHERE net_total > gross_total OR net_total <= 0")
        if "time_record" in name:
            total_checks += 1
            check(name, layer, path, "consistencia",
                  f"SELECT 1 FROM {path} WHERE total_hours < 0 OR total_hours > 24", "high")
        if "hour_bank" in name:
            total_checks += 1
            check(name, layer, path, "consistencia",
                  f"SELECT 1 FROM {path} WHERE current_balance > 1000 OR current_balance < -1000")
        if "vacations" in name:
            total_checks += 1
            check(name, layer, path, "consistencia",
                  f"SELECT 1 FROM {path} WHERE acquisition_end <= acquisition_start")

        # --- Validity ---
        if name == "employees" or name == "dim_employee":
            total_checks += 1
            check(name, layer, path, "validade",
                  f"SELECT 1 FROM {path} WHERE LENGTH(cpf) != 11 AND cpf IS NOT NULL", "high")

            total_checks += 1
            check(name, layer, path, "validade",
                  f"SELECT 1 FROM {path} WHERE gender NOT IN ('M', 'F') AND gender IS NOT NULL")

        if "detected_inconsistency" in name:
            total_checks += 1
            check(name, layer, path, "consistencia",
                  f"SELECT 1 FROM {path} WHERE use_case < 1 OR use_case > 32", "high")

# =========================================================================
# BUSINESS RULE CHECKS (cross-table, should detect injected inconsistencies)
# These checks INTENTIONALLY fail — they prove the quality system
# catches real business problems, not just structural defects.
# =========================================================================

# BR-1: Gross total must equal sum of all earnings components
# (UC01, UC02, UC03, UC06 inject payroll calculation errors)
total_checks += 1
check("fact_payroll", "silver", TABLES["silver"]["fact_payroll"], "regra_negocio",
      f"""SELECT 1 FROM {TABLES["silver"]["fact_payroll"]}
          WHERE ABS(COALESCE(base_salary,0) + COALESCE(overtime_50_amount,0) + COALESCE(overtime_70_amount,0) +
                    COALESCE(overtime_100_amount,0) + COALESCE(night_shift_amount,0) + COALESCE(periculosidade_amount,0) +
                    COALESCE(insalubridade_amount,0) + COALESCE(dsr_amount,0) + COALESCE(salary_family_amount,0)
                    - COALESCE(gross_total,0)) > 0.05""",
      "critical")

# BR-2: Night shift premium must be paid when night hours were worked
# (UC03 injects night_shift_amount = 0 while night_shift_hours > 0)
total_checks += 1
check("fact_payroll", "silver", TABLES["silver"]["fact_payroll"], "regra_negocio",
      f"""SELECT 1 FROM {TABLES["silver"]["fact_payroll"]}
          WHERE night_shift_hours > 0 AND night_shift_amount = 0""",
      "critical")

# BR-3: Hour bank should not exceed CCT limit (40h)
# (UC04 injects current_balance > 40)
total_checks += 1
check("fact_hour_bank", "silver", TABLES["silver"]["fact_hour_bank"], "regra_negocio",
      f"""SELECT 1 FROM {TABLES["silver"]["fact_hour_bank"]}
          WHERE current_balance > 40""",
      "high")

# BR-4: Periculosidade must be paid for eligible employees
# (UC13 injects missing periculosidade_amount)
total_checks += 1
check("fact_payroll", "silver", TABLES["silver"]["fact_payroll"], "regra_negocio",
      f"""SELECT 1 FROM {TABLES["silver"]["fact_payroll"]} p
          JOIN {pq('dim_employee')} e ON p.employee_id = e.employee_id
          WHERE e.periculosidade_eligible = true AND p.periculosidade_amount = 0""",
      "high")

# BR-5: Insalubridade must be paid for eligible employees
# (UC29 injects missing insalubridade_amount)
total_checks += 1
check("fact_payroll", "silver", TABLES["silver"]["fact_payroll"], "regra_negocio",
      f"""SELECT 1 FROM {TABLES["silver"]["fact_payroll"]} p
          JOIN {pq('dim_employee')} e ON p.employee_id = e.employee_id
          WHERE e.insalubridade_eligible = true AND p.insalubridade_amount = 0""",
      "high")

# =========================================================================
# 2. QUALITY SCORE PER TABLE
# =========================================================================
print(f"\n  Checks executed: {total_checks} in {time.time()-t0:.1f}s")

# Aggregate scores per table
scores = defaultdict(lambda: {"pass": 0, "fail": 0, "total": 0, "checks": []})
for r in quality_results:
    tbl = f"{r['layer']}.{r['table_name']}"
    scores[tbl]["total"] += 1
    if r["status"] == "PASS":
        scores[tbl]["pass"] += 1
    else:
        scores[tbl]["fail"] += 1
    scores[tbl]["checks"].append(r)

# Write quality results
path_q = f"{GOV}/data_quality_results.json"
with open(path_q, "w", encoding="utf-8") as f:
    json.dump({
        "pipeline": "data_quality",
        "run_at": NOW_ISO,
        "total_checks": total_checks,
        "tables_checked": len(scores),
        "results": quality_results,
        "scores": {k: {"score_pct": round(v["pass"]/v["total"]*100, 1) if v["total"] > 0 else 0,
                       "pass": v["pass"], "fail": v["fail"]}
                  for k, v in scores.items()}
    }, f, indent=2, ensure_ascii=False)
print(f"  Results: {path_q}")

# Observability event and SLA evaluation
failed_critical = len([r for r in quality_results if r["status"] in ("FAIL", "ERROR") and r["severity"] in ("critical", "high")])
obs_event = {
    "run_at": NOW_ISO,
    "pipeline": "governance",
    "checks_executed": total_checks,
    "failed_critical_or_high": failed_critical,
    "avg_score": None,
    "sla": {"max_failed_critical_or_high": 10},
}

# Print summary
print("\n  QUALITY SCORES:")
for tbl in sorted(scores):
    s = scores[tbl]
    pct = round(s["pass"]/s["total"]*100, 1) if s["total"] > 0 else 0
    print(f"  {tbl:45s} {pct:>5.1f}% ({s['pass']}/{s['total']} checks passed)")

# =========================================================================
# 3. DATA CATALOG
# =========================================================================
print("\n[2/3] Building data catalog...")

catalog = {
    "project": "HR Compliance Analytics",
    "description": "Plataforma de Auditoria Trabalhista Inteligente — labor audit & people analytics for Brazilian sanitation sector",
    "layers": {
        "bronze": {
            "description": "Raw landing zone. Data as-is from source systems.",
            "tables": {}
        },
        "silver": {
            "description": "Curated layer. Standardized schemas, cleaned, with lineage columns (source_file, ingested_at, source_hash).",
            "tables": {}
        },
        "gold": {
            "description": "Analytics layer. Dimensional model, SCD2, pre-aggregated metrics, detected inconsistencies.",
            "tables": {}
        }
    }
}

# Schema descriptions for key columns
COL_DESCRIPTIONS = {
    "employee_id": "Identificador unico do funcionario (PK natural)",
    "cpf": "Cadastro de Pessoa Fisica (11 digitos)",
    "name": "Nome completo do funcionario",
    "base_salary": "Salario base contratual",
    "hourly_rate": "Salario-hora calculado (base / (weekly_hours * 4.33))",
    "weekly_hours": "Carga horaria semanal contratual",
    "work_schedule": "Tipo de escala (5x2, 6x1, 12x36, 3x3)",
    "shift_entry_1": "Horario de entrada do primeiro turno",
    "shift_exit_1": "Horario de saida do primeiro turno",
    "shift_entry_2": "Horario de entrada do segundo turno (almoco)",
    "shift_exit_2": "Horario de saida do segundo turno",
    "shift_type": "Tipo de turno (diurno/noturno)",
    "hire_date": "Data de admissao",
    "termination_date": "Data de demissao (se aplicavel)",
    "status": "Status do funcionario (active/terminated)",
    "position_id": "Identificador do cargo (FK -> dim_position)",
    "unit_id": "Identificador da unidade (FK -> dim_unit)",
    "union_id": "Identificador do sindicato (FK -> dim_union)",
    "date_sk": "Chave surrogate da data (formato YYYYMMDD, FK -> dim_date)",
    "competence": "Competencia mensal (YYYY-MM)",
    "total_hours": "Total de horas trabalhadas no dia",
    "overtime_50": "Horas extras a 50%",
    "overtime_70": "Horas extras a 70% (progressivas)",
    "overtime_100": "Horas extras a 100% (domingos/feriados)",
    "night_hours": "Horas noturnas (22h-5h)",
    "interval_minutes": "Duracao do intervalo intrajornada em minutos",
    "absence_type": "Tipo de ausencia (medical/unjustified/missing)",
    "gross_total": "Total bruto da folha",
    "net_total": "Total liquido da folha (pos-descontos)",
    "inss_discount": "Desconto de INSS",
    "irrf_discount": "Desconto de IRRF",
    "periculosidade_amount": "Valor do adicional de periculosidade (30%)",
    "insalubridade_amount": "Valor do adicional de insalubridade (40%)",
    "dsr_amount": "Valor do Descanso Semanal Remunerado",
    "expected_amount": "Valor esperado do pagamento (deve igual net_total)",
    "paid_amount": "Valor efetivamente pago ao funcionario",
    "payment_status": "Status do pagamento (paid/partial/pending/missing)",
    "current_balance": "Saldo atual do banco de horas",
    "use_case": "Numero do caso de uso (1-32)",
    "rule_name": "Nome da regra de validacao",
    "severity": "Severidade (critico/alto/medio)",
    "financial_impact": "Impacto financeiro estimado em Reais",
    "source_file": "Arquivo de origem no Bronze layer",
    "ingested_at": "Timestamp de ingestao",
    "source_hash": "Hash MD5 da linha para deteccao de mudancas",
    "periculosidade_eligible": "Cargo elegivel ao adicional de periculosidade",
    "insalubridade_eligible": "Cargo elegivel ao adicional de insalubridade",
}

def describe_cols(table_name, columns_raw):
    """Build column descriptions for a table."""
    cols = []
    for row in columns_raw:
        name = row[0]
        dtype = row[1].upper()
        nullable = row[2] if len(row) > 2 else "YES"
        cols.append({
            "name": name,
            "type": dtype,
            "nullable": nullable == "YES",
            "description": COL_DESCRIPTIONS.get(name, ""),
            "is_pk": "id" in name.lower() and ("_id" in name.lower() or name.lower() in ["date_sk"]),
            "is_fk": any(fk in name.lower() for fk in ["employee_id", "position_id", "unit_id", "union_id", "date_sk"]),
        })
    return cols

# Read schemas from each layer
for layer, tables in TABLES.items():
    for name, path in tables.items():
        try:
            cols = con.execute(f"DESCRIBE SELECT * FROM {path}").fetchall()
            row_count = con.execute(f"SELECT count(*) FROM {path}").fetchone()[0]
            catalog["layers"][layer]["tables"][name] = {
                "description": f"Table {name} in {layer} layer",
                "path": path.strip("'"),
                "row_count": row_count,
                "columns": describe_cols(name, cols),
            }
        except Exception as e:
            catalog["layers"][layer]["tables"][name] = {
                "description": f"ERROR reading {name}: {str(e)[:100]}",
                "path": path.strip("'"),
                "row_count": -1,
                "columns": [],
            }

# Add facts from gold
catalog["gold_tables"] = {
    "fact_detected_inconsistency": {
        "description": "Inconsistencias detectadas pelo motor de validacao (32 regras)",
        "columns": describe_cols("detected",
            [("detection_id","BIGINT"),("employee_id","BIGINT"),("competence","VARCHAR"),
             ("use_case","INT"),("rule_name","VARCHAR"),("category","VARCHAR"),
             ("severity","VARCHAR"),("detected_value","VARCHAR"),("expected_value","VARCHAR"),
             ("financial_impact","DOUBLE"),("detail","VARCHAR"),("detected_at","TIMESTAMP")]),
    },
    "fact_passivo_trabalhista": {
        "description": "Passivo trabalhista consolidado por ocorrencia de inconsistencia",
    },
}

path_cat = f"{GOV}/data_catalog.json"
with open(path_cat, "w", encoding="utf-8") as f:
    json.dump(catalog, f, indent=2, ensure_ascii=False)
print(f"  Catalog: {path_cat}")

# =========================================================================
# 4. DATA LINEAGE
# =========================================================================
print("\n[3/3] Building data lineage...")

lineage = {
    "pipeline": "data_lineage",
    "generated_at": NOW_ISO,
    "description": "Documentacao da linhagem de dados: origem, transformacao e destino",
    "flows": [
        {
            "source_layer": "bronze",
            "source_tables": [
                "hr_system/employees.csv", "hr_system/positions.csv",
                "hr_system/unions.csv", "hr_system/units.csv",
                "hr_system/holidays.csv", "hr_system/dependents.csv",
                "time_clock/time_records.csv", "time_clock/hour_bank.csv",
                "payroll/payroll.csv", "bank/bank_payments.csv",
                "events/vacations.csv", "events/leaves.csv",
                "events/salary_history.csv", "events/terminations.csv",
            ],
            "transformation": "data_generation/ (Python) — geracao sintetica de dados com injecao de 32 tipos de inconsistencia",
            "target_layer": "bronze",
            "target_tables": ["todos os CSVs/Parquets acima"],
        },
        {
            "source_layer": "bronze",
            "source_tables": ["*/*.csv"],
            "transformation": "bronze_to_silver.py (DuckDB SQL) — padronizacao de schemas, normalizacao, adicao de colunas de linhagem",
            "target_layer": "silver",
            "target_tables": [
                "dim_employee", "dim_position", "dim_union", "dim_unit", "dim_date",
                "fact_payroll", "fact_time_record", "fact_payment", "fact_hour_bank",
                "vacations", "leaves", "salary_history", "terminations", "dependents",
            ],
            "columns_added": ["source_file", "ingested_at", "source_hash"],
        },
        {
            "source_layer": "silver",
            "source_tables": ["dim_employee", "dim_union", "dim_position", "dim_unit", "dim_date",
                              "fact_payroll", "fact_time_record", "fact_payment", "fact_hour_bank",
                              "vacations", "salary_history"],
            "transformation": "silver_to_gold.py (DuckDB SQL) — modelagem dimensional, SCD2, agregacoes, passivo",
            "target_layer": "gold",
            "target_tables": [
                "dim_employee_scd2", "fact_monthly_employee", "fact_passivo_trabalhista",
                "agg_unit_monthly", "agg_union_monthly", "agg_passivo_by_unit",
                "agg_vacation_risk", "agg_employee_annual",
            ],
        },
        {
            "source_layer": "gold + silver",
            "source_tables": ["fact_monthly_employee", "dim_employee", "dim_union", "dim_unit",
                              "dim_position", "dim_date", "fact_payroll", "fact_time_record",
                              "fact_payment", "fact_hour_bank", "vacations", "salary_history"],
            "transformation": "validation_engine.py (DuckDB SQL + Pandas) — 32 regras de validacao, calculo de impacto financeiro",
            "target_layer": "gold",
            "target_tables": ["fact_detected_inconsistency"],
        },
    ],
    "column_level": [
        {"from": "bronze.employees", "to": "silver.dim_employee", "key": "employee_id"},
        {"from": "silver.dim_employee + silver.dim_union", "to": "gold.dim_employee_scd2", "key": "employee_id"},
        {"from": ["silver.fact_payroll", "silver.fact_time_record", "silver.fact_payment",
                   "silver.fact_hour_bank", "silver.dim_employee", "silver.dim_union"],
         "to": "gold.fact_monthly_employee", "key": "employee_id + date_sk"},
        {"from": ["gold.fact_monthly_employee", "silver.dim_employee", "silver.dim_unit",
                   "silver.dim_union", "silver.fact_payroll", "silver.fact_time_record",
                   "silver.fact_payment", "silver.fact_hour_bank", "silver.vacations",
                   "silver.salary_history", "bronze.audit.inconsistency_log"],
         "to": "gold.fact_detected_inconsistency", "key": "employee_id + competence"},
    ],
}

path_lin = f"{GOV}/data_lineage.json"
with open(path_lin, "w", encoding="utf-8") as f:
    json.dump(lineage, f, indent=2, ensure_ascii=False)
print(f"  Lineage: {path_lin}")

# =========================================================================
# 5. GOVERNANCE MANIFEST
# =========================================================================
governance_manifest = {
    "pipeline": "data_quality_and_governance",
    "run_at": NOW_ISO,
    "outputs": {
        "data_quality": "data/gold/governance/data_quality_results.json",
        "data_catalog": "data/gold/governance/data_catalog.json",
        "data_lineage": "data/gold/governance/data_lineage.json",
    },
    "quality_summary": {
        "total_checks": total_checks,
        "tables_checked": len(scores),
        "avg_score": round(sum(s["pass"]/max(s["total"],1)*100 for s in scores.values())/max(len(scores),1), 1),
    },
}
obs_event["avg_score"] = governance_manifest["quality_summary"]["avg_score"]
obs_event["sla_status"] = "PASS" if failed_critical <= 10 else "FAIL"

history_path = f"{OBS}/governance_history.json"
history = []
if os.path.exists(history_path):
    with open(history_path, "r", encoding="utf-8") as f:
        history = json.load(f)
history.append(obs_event)
with open(history_path, "w", encoding="utf-8") as f:
    json.dump(history[-200:], f, indent=2, ensure_ascii=False)
if obs_event["sla_status"] == "FAIL":
    with open(f"{OBS}/alerts.log", "a", encoding="utf-8") as f:
        f.write(f"{NOW_ISO} | governance | SLA_FAIL | failed_critical_or_high={failed_critical}\n")

path_man = f"{GOV}/governance_manifest.json"
with open(path_man, "w", encoding="utf-8") as f:
    json.dump(governance_manifest, f, indent=2, ensure_ascii=False)
print(f"  Manifest: {path_man}")

con.close()

print(f"\n{'='*60}")
print("GOVERNANCE SUMMARY")
print(f"{'='*60}")
print(f"  Quality checks: {total_checks} across {len(scores)} tables")
print(f"  Average quality score: {governance_manifest['quality_summary']['avg_score']}%")
print(f"  Catalog entries: {sum(len(v['tables']) for v in catalog['layers'].values())} tables")
print(f"  Lineage flows: {len(lineage['flows'])}")
print(f"  Output: {GOV}/")
print("\nDone.")
