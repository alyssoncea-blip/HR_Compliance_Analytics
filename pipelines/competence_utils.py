"""
Competence-partition bookeeping for the validation engine.

Kept importable and side-effect free so tests can exercise merge /
resequencing helpers without running the full engine script.
"""
import re


CONTRACT_COLS = [
    "detection_id", "employee_id", "competence", "use_case", "rule_name",
    "category", "severity", "detected_value", "expected_value",
    "financial_impact", "detail", "rule_origin", "evidence_source", "detected_at",
]

# Sort key defines the canonical detection order; detection_id is the row
# position in this order, so the same content always maps to the same ids.
RESORT_COLS = [
    "competence", "use_case", "rule_name", "category", "severity",
    "employee_id", "detected_value", "expected_value",
    "financial_impact", "detail", "rule_origin", "evidence_source", "detected_at",
]

_CONTRACT_NO_ID = [c for c in CONTRACT_COLS if c != "detection_id"]

_NA = "N/A"


def normalize_competence(value):
    """Reduce any detection competence format to its 'YYYY-MM' month key."""
    if value is None:
        return _NA
    s = str(value)
    if re.fullmatch(r"\d{4}-\d{2}", s):
        return s
    if re.fullmatch(r"\d{4}-\d{2}(-\d{2}.*)?", s):
        return s[:7]
    if re.fullmatch(r"\d{8}", s):
        return f"{s[:4]}-{s[4:6]}"
    return _NA


def list_competences(con, gold_dir="data/gold"):
    """Derive the valid competence list from fact_monthly_employee (not hardcoded)."""
    path = f"{gold_dir}/fact_monthly_employee.parquet".replace("\\", "/")
    rows = con.execute(f"""
        SELECT DISTINCT year, month
        FROM read_parquet('{path}')
    """).fetchall()
    return sorted(f"{y}-{int(m):02d}" for y, m in rows)


def resolve_requested_competences(competences, from_comp, to_comp, available):
    """Build the target set from repeated --competence and/or from/to bounds."""
    if from_comp is not None or to_comp is not None:
        if from_comp is None or to_comp is None:
            raise ValueError("--competence-from and --competence-to must be used together")
        if from_comp not in available or to_comp not in available:
            raise ValueError(f"out-of-range competence: {from_comp}..{to_comp}")
        competences = sorted(set(competences or []) |
                             {c for c in available if from_comp <= c <= to_comp})
    if not competences:
        return None
    unknown = [c for c in competences if c not in available]
    if unknown:
        raise ValueError(f"unknown competences (derive list from fact_monthly_employee): {unknown}")
    return sorted(set(competences))


def resequence_detection_ids(df):
    """Deterministically renumber detection_id after any merge."""
    sort_df = df.copy()
    sort_df["use_case"] = sort_df["use_case"].astype(int)
    sort_df["_emp_key"] = sort_df["employee_id"].astype(str)
    for c in ("detected_value", "expected_value", "detail"):
        sort_df[c] = sort_df[c].fillna("").astype(str)
    sort_df = sort_df.sort_values(RESORT_COLS + ["_emp_key"], kind="stable", na_position="last")
    out = sort_df.drop(columns=["_emp_key"])
    out = out[[c for c in _CONTRACT_NO_ID if c in out.columns]].reset_index(drop=True)
    out["detection_id"] = range(1, len(out) + 1)
    return out[CONTRACT_COLS]


def merge_detections(old_df, new_df, target_competences):
    """
    Merge freshly computed target-competence detections into the stored set.

    - deletes every stored row whose normalized competence is in the target set
    - appends the new detections
    - deterministic resequencing over the full merged set
    - full mode (old_df=None) is a plain resequence of the fresh run
    """
    import pandas as pd
    if old_df is None:
        return resequence_detection_ids(new_df[_CONTRACT_NO_ID])
    target = set(target_competences)
    keep_mask = ~old_df["competence"].map(normalize_competence).isin(target)
    kept_cols = [c for c in CONTRACT_COLS if c in old_df.columns]
    kept = old_df.loc[keep_mask, kept_cols]
    combined = pd.concat([kept, new_df[_CONTRACT_NO_ID]], ignore_index=True)
    return resequence_detection_ids(combined)
