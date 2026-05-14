"""
Exports all generated data to Bronze layer: CSV + Parquet + JSON schema.
"""
import os
import csv
import json
import io
from datetime import date, time
from typing import List, Dict, Any

from config import BRONZE_PATH


def _serialize(val):
    """Convert Python objects to serializable types."""
    if val is None:
        return None
    if isinstance(val, (date,)):
        return val.isoformat()
    if isinstance(val, (time,)):
        return val.strftime("%H:%M")
    return val


def _schema_from_sample(sample: dict) -> Dict[str, str]:
    type_map = {
        str: "string",
        int: "integer",
        float: "number",
        bool: "boolean",
        type(None): "string",
    }
    schema = {}
    for key, val in sample.items():
        if key.startswith("__"):
            continue
        val_type = type(val)
        if val_type == date:
            schema[key] = "date"
        elif val_type == time:
            schema[key] = "time"
        else:
            schema[key] = type_map.get(val_type, "string")
    return schema


def write_dataset(name: str, data: List[dict], subfolder: str = "") -> str:
    """Write dataset as CSV, Parquet, and schema JSON. Returns the path."""
    base = os.path.join(BRONZE_PATH, subfolder)
    os.makedirs(base, exist_ok=True)

    # Filter internal fields (__ prefix)
    clean_data = []
    for row in data:
        clean = {k: v for k, v in row.items() if not k.startswith("__")}
        clean_data.append(clean)

    if not clean_data:
        return base

    # CSV
    csv_path = os.path.join(base, f"{name}.csv")
    fieldnames = list(clean_data[0].keys())
    with open(csv_path, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, delimiter=";")
        writer.writeheader()
        for row in clean_data:
            writer.writerow({k: _serialize(v) for k, v in row.items()})

    # Schema JSON
    schema = _schema_from_sample(clean_data[0])
    schema_path = os.path.join(base, f"{name}_schema.json")
    with open(schema_path, "w", encoding="utf-8") as f:
        json.dump({
            "dataset": name,
            "row_count": len(clean_data),
            "columns": schema,
            "fields": fieldnames,
        }, f, indent=2, ensure_ascii=False)

    # Parquet
    _write_parquet(clean_data, os.path.join(base, f"{name}.parquet"))

    print(f"  {name}: {len(clean_data)} rows -> {base}")
    return base


def _write_parquet(data: List[dict], path: str):
    """Write Parquet using pyarrow if available, or a no-op warning."""
    try:
        import pyarrow as pa
        import pyarrow.parquet as pq

        # Convert to pyarrow table
        arrays = {}
        for key in data[0].keys():
            col = []
            for row in data:
                v = row.get(key)
                col.append(_serialize(v) if isinstance(v, (date, time)) else v)
            arrays[key] = col

        schema = pa.schema([pa.field(k, _pyarrow_type(arrays[k])) for k in data[0].keys()])
        table = pa.table(arrays, schema=schema)
        pq.write_table(table, path)
        print(f"    (parquet written)")
    except ImportError:
        print(f"    (pyarrow not installed; parquet skipped)")


def _pyarrow_type(values):
    import pyarrow as pa
    non_none = [v for v in values if v is not None]
    if not non_none:
        return pa.string()
    sample = non_none[0]
    if isinstance(sample, bool):
        return pa.bool_()
    if isinstance(sample, int):
        return pa.int64()
    if isinstance(sample, float):
        return pa.float64()
    return pa.string()


def export_all(
    employees: List[dict], positions: List[dict], unions_: List[dict],
    units_: List[dict], holidays: List[dict], time_records: List[dict],
    payroll: List[dict], payments: List[dict], hour_bank: List[dict],
    vacations: List[dict], leaves: List[dict], salary_history: List[dict],
    terminations: List[dict], inconsistency_log: List[dict],
    dependents: List[dict] = None,
):
    print(f"\n{'='*60}")
    print(f"Exporting to Bronze layer: {BRONZE_PATH}")
    print(f"{'='*60}")

    write_dataset("employees", employees, "hr_system")
    write_dataset("positions", positions, "hr_system")
    write_dataset("unions", unions_, "hr_system")
    write_dataset("units", units_, "hr_system")
    write_dataset("holidays", holidays, "hr_system")

    write_dataset("time_records", time_records, "time_clock")
    write_dataset("hour_bank", hour_bank, "time_clock")

    write_dataset("payroll", payroll, "payroll")

    write_dataset("bank_payments", payments, "bank")

    write_dataset("vacations", vacations, "events")
    write_dataset("leaves", leaves, "events")
    write_dataset("salary_history", salary_history, "events")
    write_dataset("terminations", terminations, "events")

    if dependents:
        write_dataset("dependents", dependents, "hr_system")

    write_dataset("inconsistency_log", inconsistency_log, "audit")

    # Write data lineage manifest
    manifest = {
        "pipeline": "data_generation",
        "generated_at": str(date.today()),
        "datasets": {
            "hr_system": ["employees", "positions", "unions", "units", "holidays", "dependents"],
            "time_clock": ["time_records", "hour_bank"],
            "payroll": ["payroll"],
            "bank": ["bank_payments"],
            "events": ["vacations", "leaves", "salary_history", "terminations"],
            "audit": ["inconsistency_log"],
        },
        "use_cases_covered": 32,
        "employee_count": len(employees),
        "time_record_count": len(time_records),
        "payroll_count": len(payroll),
        "payment_count": len(payments),
    }
    manifest_path = os.path.join(BRONZE_PATH, "lineage_manifest.json")
    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2, ensure_ascii=False)
    print(f"  lineage_manifest written -> {manifest_path}")
    print(f"{'='*60}\n")
