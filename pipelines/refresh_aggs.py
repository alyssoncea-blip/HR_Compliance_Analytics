"""
Aggregation Refresh Pipeline
Rebuilds dashboard pre-aggregations that depend on facts materialized by
the validation engine (e.g. fact_passivo_trabalhista -> agg_passivo_by_unit).
Reads the FINAL Gold state (post-validation), so these aggregations no
longer depend on running the full pipeline twice.
Writes ZSTD Parquet to data/gold/ and updates gold_manifest.json.
"""
import duckdb, os, json, time
from datetime import datetime, timezone

GOLD = "data/gold"
SILVER = "data/silver"
NOW_ISO = datetime.now(timezone.utc).isoformat()

os.makedirs(GOLD, exist_ok=True)
con = duckdb.connect()

def gq(path): return f"'{GOLD}/{path}.parquet'".replace(chr(92), "/")
def sq(path): return f"'{SILVER}/{path}.parquet'".replace(chr(92), "/")

def write_pq(name, sql):
    path = f"{GOLD}/{name}.parquet"
    con.execute(f"COPY ({sql}) TO '{path}' (FORMAT PARQUET, COMPRESSION ZSTD)")
    rows = con.execute(f"SELECT count(*) FROM read_parquet('{path}')").fetchone()[0]
    size_mb = os.path.getsize(path) / 1024 / 1024
    print(f"  {path.split('/')[-1]:35s} {rows:>10,} rows  {size_mb:>8.1f} MB")
    return rows

print("=" * 60)
print("AGGREGATION REFRESH PIPELINE")
print("=" * 60)

t0 = time.time()
rows = {}

# ============================================================
# 1. agg_passivo_by_unit — depends on fact_passivo_trabalhista
#    materialized by validation_engine.py
# ============================================================
print("\n[1/1] agg_passivo_by_unit")
rows["agg_passivo_by_unit"] = write_pq("agg_passivo_by_unit", f"""
SELECT u.name AS unit_name, u.state,
       fp.liability_type, fp.severity,
       COUNT(*) AS occurrence_count,
       ROUND(SUM(fp.estimated_impact), 0) AS total_estimated_impact,
       ROUND(AVG(fp.estimated_impact), 0) AS avg_impact
FROM read_parquet({gq('fact_passivo_trabalhista')}) fp
LEFT JOIN read_parquet({sq('dim_unit')}) u ON fp.unit_id = u.unit_id
GROUP BY u.name, u.state, fp.liability_type, fp.severity
""")

elapsed = time.time() - t0
print(f"\nDone in {elapsed:.1f}s")

# ============================================================
# Manifest: add/update agg_passivo_by_unit entry in gold manifest
# ============================================================
manifest_path = f"{GOLD}/gold_manifest.json"
if os.path.exists(manifest_path):
    with open(manifest_path, "r", encoding="utf-8") as f:
        manifest = json.load(f)
    targets = manifest.get("targets", [])
    if "agg_passivo_by_unit" not in targets:
        targets.append("agg_passivo_by_unit")
else:
    manifest = {"pipeline": "silver_to_gold"}
    targets = ["agg_passivo_by_unit"]

total_tables = len([f for f in os.listdir(GOLD) if f.endswith(".parquet")])
manifest.update({
    "pipeline": "refresh_aggs",
    "run_at": NOW_ISO,
    "elapsed_s": round(elapsed, 1),
    "output_tables": total_tables,
    "targets": targets,
    "agg_refresh": {
        "agg_passivo_by_unit_rows": rows["agg_passivo_by_unit"],
        "source": "fact_passivo_trabalhista (post validation_engine)",
    },
})
with open(manifest_path, "w", encoding="utf-8") as f:
    json.dump(manifest, f, indent=2)
print(f"  Manifest updated: {manifest_path}")

con.close()
