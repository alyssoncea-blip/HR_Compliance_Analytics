"""
Detection quality metrics (informativo) — precision/recall/F1 by use case,
cross-referencing rule-engine detections with the injection ground truth
(Bronze audit inconsistency_log).

Falso positivo detection wins: the engine should not claim an inconsistency
the generator never injected; omission wins: never count an injected fault as
successfully detected twice for the same ground-truth pair.

Run modes (CLI):
    python pipelines/detection_quality.py            -> refresh from stored Gold state
    python pipelines/detection_quality.py baseline   -> snapshot current state + engine baseline
    python pipelines/detection_quality.py compare    -> merge the baseline snapshot with current state

Reads:
    data/gold/fact_detected_inconsistency.parquet (rule_origin != 'simulation_marker')
    data/bronze/audit/inconsistency_log.parquet   (ground truth — source of truth)

Writes:
    data/gold/governance/detection_quality.json
    data/gold/validation_manifest.json (detection_quality pointer, informational)

IMPORTANT: this artifact is informative; it does not gate the pipeline and
governance.py does not read it yet by design (spec: quality/artifact only).
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
import time
from datetime import datetime, timezone
from decimal import Decimal, ROUND_HALF_UP

import pandas as pd

try:
    here = os.path.dirname(os.path.abspath(__file__))
    sys.path.insert(0, here)
    from competence_utils import normalize_competence
except Exception:
    from competence_utils import normalize_competence  # worktree-friendly

ROOT = os.path.abspath(os.path.join(here, ".."))
GOLD = os.path.join(ROOT, "data", "gold")
SILVER = os.path.join(ROOT, "data", "silver")
DET_PATH = os.path.join(GOLD, "fact_detected_inconsistency.parquet")
LOG_PATH = os.path.join(ROOT, "data", "bronze", "audit", "inconsistency_log.parquet")
SNAPSHOT_DIR = os.path.join(GOLD, "governance")
OUT_PATH = os.path.join(SNAPSHOT_DIR, "detection_quality.json")
SNAPSHOT_PATH = os.path.join(SNAPSHOT_DIR, "detection_quality_baseline.json")
MANIFEST_PATH = os.path.join(GOLD, "validation_manifest.json")

# Day-level UCs (rules driven by fact_time_record day granular rows). Their
# injection ref is a date; detection competence may be the same date or the
# month om — matching below normalizes both and unions day/any-date-day
# tolerance: for these UCs an employee-month pair counts as a hit when the
# employee had an injected event on ANY day of the detection month.
UC_DAILY = [5, 12, 22, 24, 27, 28]

#: day-level UCs whose injected ref is a DATE and detection competence is the
#: same DATE — for these the metric merges them to (employee, month) precision
UC_DAILY_MAP = {
    uc: True for uc in UC_DAILY
}

#: employee-scoped UCs (Cadastro-type rules with no competence ref): the log
#: row carries ref = "" and the engine emits competence = "N/A" (or a deadline
#: date for UC31/32). Matching is (employee_id) only — any monthless rule fires
#: (or may fire) once per employee, so month keys carry no extra signal.
UC_EMPLOYEE_SCOPED = {8, 17, 19, 20, 23, 26, 31, 32}

#: UCs whose detections are excluded from the aggregate F1: UC17 detections are
#: forwarded simulation markers (rule_origin = 'simulation_marker'), which are
#: filtered from the prediction set, so UC17 measures nothing about the engine.
UC_EXCLUDED_FROM_MEAN = {17}

#: alto/critico UCs keyed by competence-month (the engine's calibration scope)
HIGH_SEV_MONTHLY = [1, 2, 6, 7, 9, 10, 13, 14, 15, 18, 21, 25, 29]

#: Documented engine calibration outcome (2026-10 sweep against the frozen
#: baseline). Root causes that put a hard data-level ceiling on some UCs.
CALIBRATION_NOTES = {
    "uc28_undetectable": ("UC28 'Jornada sobreposta': the generator marks "
                          "overlaps with an in-memory __overlap key that is "
                          "never exported (rows keep the fixed time-record "
                          "schema), so no data signature exists. No rule "
                          "predicate can separate it; F1 stays 0.0 by design."),
    "uc27_no_signal": ("UC27 'Atestado ignorado': medical-leave records never "
                       "cover the injected absence events (independent "
                       "generators); the injected rows are empirically "
                       "indistinguishable from the 92 naturally deducted "
                       "unjustified absences. Severity 'medio' - kept as-is "
                       "(precision 0.7%, recall 1.0) out of the high-severity "
                       "F1 target scope."),
    "uc31_natural_expired": ("UC31 'Ferias vencidas': the injected mutation "
                             "(expired, scheduled_start=None, days_taken=0) is "
                             "record-identical to the natural ~10% expired "
                             "vacation base rate, so precision caps near 0.19 "
                             "with recall 0.94 at employee level."),
    "uc6_cascade_fps": ("UC6 'Ponto vs Folha': ~85% of FPs are genuine "
                        "cascades of other injections (UC15 hours zeroing, "
                        "UC25 ponto inflation, UC14/UC1/UC2/UC10 amount "
                        "mutations) that the log does not attribute to UC6. "
                        "Suppression and diff-cap/split-signature variants "
                        "were swept and all scored below the base predicate "
                        "ABS(hours diff) > 2; F1 0.413 (recall 0.75) is the "
                        "local optimum."),
    "uc12_cascade_fps": ("UC12 '12x36 excedida': all 373 truth rows are caught "
                         "(recall 1.0). Residual FPs are UC25-injected "
                         "12x36-point weeks (base 12h + delta) with an "
                         "identical ot50 signature; F1 ~0.53 accepted."),
    "uc18_expected_zero": ("UC18 'Pagamento orfao': predicate rewritten to "
                           "expected_amount = 0 AND paid_amount > 0 (the only "
                           "rows in the payments ledger with that signature "
                           "are the 200 ORPHAN receipts) - F1 1.0."),
    "uc4_crossing": ("UC4 'Banco de horas excedido': predicate rewritten to "
                     "the ledger crossing the 40h ceiling (current_balance "
                     "> 40 AND previous_balance <= 40); injected first-"
                     "month balances overlap the legit distribution, so "
                     "recall 1.0 with the semantics kept. Severity 'medio'."),
    "uc25_weekly": ("UC25 'Limite semanal': per-schedule ordinary-hour "
                    "thresholds via cct state (5x2 42h mg-rj / 32h rn, 6x1 "
                    "45.5, 12x36 45.5, 3x3 44.5) computed on weeks with >= 4 "
                    "days - pair F1 0.90 from baseline 0.11."),
    "employee_scoped": ("UC8/19/20/23/26/31/32 (and 17) log rows carry "
                        "ref = ': matching is (employee_id)-scoped; "
                        "competence carries no signal for N/A-competence "
                        "rules."),
    "metric_mean": ("mean_f1_active_ucs excludes UC17 (simulation markers are "
                    "filtered from predictions, so its score carries no "
                    "engine signal)."),
}

# ---------------------------------------------------------------------------


def _month_of(x) -> str | None:
    if x is None:
        return None
    normalized = normalize_competence(str(x))
    return None if normalized == "N/A" else normalized


def _month_to_day_regex(m: str) -> str:
    return f"{m[:4]}-{m[5:7]}-\\d\\d"


def _dedupe_pairs(pairs):
    seen = set()
    out = []
    for pair in pairs:
        if pair not in seen:
            seen.add(pair)
            out.append(pair)
    return out


def detection_pairs(detections: pd.DataFrame, uc: int) -> set:
    """(employee_id, month) pairs detected by the engine for a use case."""
    if detections.empty:
        return set()
    det = detections[detections["use_case"] == uc]
    if det.empty:
        return set()
    det = det.copy()
    det["month_key"] = det["competence"].map(_month_of)
    det = det.dropna(subset=["month_key", "employee_id"])
    return set(zip(det["employee_id"].astype(int), det["month_key"].astype(str)))


def detection_employees(detections: pd.DataFrame, uc: int) -> set:
    """employee ids detected by the engine for an employee-scoped use case."""
    if detections.empty:
        return set()
    det = detections[detections["use_case"] == uc]
    if det.empty:
        return set()
    return set(det["employee_id"].astype(int))


def injection_ground_truth_index(log: pd.DataFrame) -> dict:
    """
    Returns per-UC ground truth structures:

    month UC  -> {(employee_id, month), ...}
    daily UC  -> {(employee_id, day}, injected day pairs) UNION
                 {(employee_id, month}, injected month pairs)
    emp UC    -> {employee_id, ...} (employee ids)

    The daily UC dedupes (employee, day) and also merges to (employee, month)
    for diagnostics (see doc note on falso positivo detection).
    """
    ground_truth = {}
    for uc, group in log.groupby("use_case"):
        uc = int(uc)
        refs = group["ref"].fillna("").astype(str)
        if uc in UC_EMPLOYEE_SCOPED:
            ground_truth[uc] = set(int(e) for e in group["employee_id"])
        elif UC_DAILY_MAP.get(uc):
            days = set()
            months = set()
            for eid, ref in zip(group["employee_id"], refs):
                norm = normalize_competence(ref)
                if norm == "N/A":
                    continue
                if len(norm) == 10:
                    days.add((int(eid), norm))
                months.add((int(eid), norm[:7]))
            ground_truth[uc] = (days, months)
        else:
            pairs = set()
            for eid, ref in zip(group["employee_id"], refs):
                norm = normalize_competence(ref)
                if norm != "N/A":
                    pairs.add((int(eid), norm))
            ground_truth[uc] = (pairs, pairs)
    return ground_truth


def _f1(precision: Decimal, recall: Decimal) -> Decimal:
    if precision + recall == 0:
        return Decimal("0.0000")
    return (2 * precision * recall) / (precision + recall)


def _ratio(num: float, den: float) -> Decimal:
    if den == 0:
        return Decimal("0.0000")
    return (Decimal(num) / Decimal(den)).quantize(Decimal("0.0001"),
                                                  rounding=ROUND_HALF_UP)


def compute_uc_metrics(
    detections: pd.DataFrame,
    log: pd.DataFrame,
    uc_daily_map: dict,
) -> dict:
    """Compute TP / FP / FN / precision / recall / F1 per use case.

    Methodology:
      - detections come from fact_detected_inconsistency with rule_origin != 'simulation_marker'
      - ground truth is the Bronze audit injection log (source of truth per use_case)
      - matching granularity is (employee_id, month), with daily-UC tolerance:
        employees with an injected event on ANY day of the detection month match
      - TP: guessed when (emp, month) is in both true and pred sets (matched outer)
      - FP: detected pair with no matching injection
      - FN: injected pair with no matching detection
      - Untested / N/A-case UCs also exposed (use_case-to-detection file mapping)
    """
    out = {}
    for uc in sorted(set(detections["use_case"].astype(int)) | set(log["use_case"].astype(int))):
        uc = int(uc)
        gt_day, gt_month_set = None, None
        if uc in UC_EMPLOYEE_SCOPED:
            sub = log[log["use_case"] == uc]
            truth = set(int(e) for e in sub["employee_id"])
            preds = detection_employees(detections, uc)
        elif uc in uc_daily_map:
            ground_truth = injection_ground_truth_index(
                log[log["use_case"] == uc]) if not log[log["use_case"] == uc].empty else {
                uc: (set(), set())}
            gt_day, gt_month_set = ground_truth[uc]
            truth = gt_day | gt_month_set
            preds = detection_pairs(detections, uc)
        else:
            sub = log[log["use_case"] == uc]
            pairs = set(
                (int(e), _month_of(r)) for e, r in zip(sub["employee_id"],
                                                       sub["ref"].fillna("").astype(str))
                if _month_of(r))
            truth = pairs
            preds = detection_pairs(detections, uc)

        tp = len(truth & preds)
        fp = len(preds - truth)
        fn = len(truth - preds)

        precision = _ratio(tp, tp + fp)
        recall = _ratio(tp, tp + fn)
        out[uc] = {
            "tp": tp,
            "fp": fp,
            "fn": fn,
            "precision": float(precision),
            "recall": float(recall),
            "f1": float(_f1(precision, recall)),
            "injected_pairs": len(truth),
            "detected_rows": int((detections["use_case"] == uc).sum())
            if not detections.empty else 0,
        }
    return out


def _detections_from_gold() -> pd.DataFrame:
    det = pd.read_parquet(DET_PATH)
    det = det[det["rule_origin"] != "simulation_marker"].copy()
    det["use_case"] = det["use_case"].astype(int)
    return det


def _log_from_bronze() -> pd.DataFrame:
    return pd.read_parquet(LOG_PATH)


def _apply_baseline_mapping(dets_baseline: pd.DataFrame) -> pd.DataFrame:
    """Detections read from the baseline snapshot parquet."""
    return dets_baseline[dets_baseline["rule_origin"] != "simulation_marker"].copy() \
        if dets_baseline is not None else pd.DataFrame()


# ---------------------------------------------------------------------------


def _hc_metrics_governance_snapshot() -> dict | None:
    """Load a previous detection_quality.json governance run (for the deltas)."""
    try:
        with open(OUT_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None


def build_report(metrics: dict, detections: pd.DataFrame, extra: dict) -> dict:
    now = datetime.now(timezone.utc).isoformat()
    summary_by_uc = {
        str(uc): {
            "tp": m["tp"], "fp": m["fp"], "fn": m["fn"],
            "precision": m["precision"], "recall": m["recall"], "f1": m["f1"],
            "injected_pairs": m["injected_pairs"], "detected_rows": m["detected_rows"],
        } for uc, m in sorted(metrics.items())
    }

    all_f1 = [Decimal(str(m["f1"])) for m in metrics.values()]
    mean_f1 = float(_ratio(sum(all_f1), len(all_f1))) if all_f1 else 0.0

    # Aggregate restricted to engine-actionable UCs: UC17 detections are
    # simulation markers (filtered out of the prediction set), so its score
    # would drag the mean without carrying engine signal.
    active_f1 = [Decimal(str(m["f1"])) for uc, m in metrics.items()
                 if uc not in UC_EXCLUDED_FROM_MEAN]
    mean_f1_active = float(_ratio(sum(active_f1), len(active_f1))) if active_f1 else 0.0

    report = {
        "pipeline": "detection_quality",
        "computed_at": now,
        "methodology": {
            "matching_key": "(employee_id, competence-month), normalized by "
                            "competence_utils.normalize_competence",
            "daily_uc_tolerance": ("injections with a day ref count as owned month "
                                   "pair; detection month matches if the "
                                   "injection happened on any day of that month"),
            "tp": "injected pair detected by the rule engine",
            "fp": "detection with no corresponding injection",
            "fn": "injected inconsistency not detected by the engine",
            "precision": "tp / (tp + fp)",
            "recall": "tp / (tp + fn)",
            "f1": "harmonic mean of precision and recall (2PR / (P+R))",
            "employee_scoped_uc_tolerance": ("UCs whose log rows carry ref = '' "
                                             "(cadastro / N.A-competence rules) "
                                             "match on employee_id only"),
            "predictions_source": "data/gold/fact_detected_inconsistency.parquet "
                                  "(rule_origin != 'simulation_marker')",
            "source_of_truth": "data/bronze/audit/inconsistency_log.parquet "
                               "(all injected inconsistencies; the generator's "
                               "single self-labelled ground truth)",
            "unc_29_note": "UC29 was injected as a PF via generator bug and is "
                           "kept here for methodology transparency (fle precision"
                           " imputation onboarding)",
        },
        "uc_daily": sorted(uc for uc, is_daily in UC_DAILY_MAP.items() if is_daily),
        "uc_employee_scoped": sorted(UC_EMPLOYEE_SCOPED),
        "metrics_by_uc": summary_by_uc,
        "mean_f1_all_ucs": mean_f1,
        "mean_f1_active_ucs": mean_f1_active,
        "high_severity_monthly_targets": {
            str(uc): {
                "f1": summary_by_uc[str(uc)]["f1"],
                "target": "f1 >= 0.70 with recall >= 0.50 floor"
            } for uc in HIGH_SEV_MONTHLY if str(uc) in summary_by_uc
        },
        "mean_f1_all_ucs": mean_f1,
        "total_injected_log_rows": extra.get("injection_log_rows"),
        "total_rule_engine_rows": int(len(detections)),
        "baseline": extra.get("baseline_ref"),
        "calibration_notes": extra.get("calibration_notes") or CALIBRATION_NOTES,
    }
    return report


def _write_json(path: str, payload: dict) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False)


def _update_manifest(report: dict) -> None:
    if not os.path.exists(MANIFEST_PATH):
        return
    with open(MANIFEST_PATH, "r", encoding="utf-8") as f:
        manifest = json.load(f)
    f1_by_uc = {uc: m["f1"] for uc, m in report["metrics_by_uc"].items()}
    manifest["detection_quality"] = {
        "artifact": "data/gold/governance/detection_quality.json",
        "computed_at": report["computed_at"],
        "mean_f1_all_ucs": report["mean_f1_all_ucs"],
        "mean_f1_active_ucs": report.get("mean_f1_active_ucs"),
        "f1_by_uc": f1_by_uc,
        "informational": True,
    }
    _write_json(MANIFEST_PATH, manifest)


# ---------------------------------------------------------------------------


def cmd_refresh(args) -> int:
    t0 = time.time()
    detections = _detections_from_gold()
    log = _log_from_bronze()
    metrics = compute_uc_metrics(detections, log, UC_DAILY_MAP)

    calibration_notes = None
    if args.keep_calibration:
        previous = _hc_metrics_governance_snapshot()
        if previous:
            calibration_notes = previous.get("calibration_notes")

    report = build_report(
        metrics, detections,
        {
            "injection_log_rows": int(len(log)),
            "baseline_ref": None,
            "calibration_notes": calibration_notes,
        },
    )
    _write_json(OUT_PATH, report)
    _update_manifest(report)

    print(f"detection_quality -> {OUT_PATH} ({time.time() - t0:.1f}s)")
    print(f"{'UC':>4} {'TP':>8} {'FP':>8} {'FN':>8} {'P':>7} {'R':>7} {'F1':>7}")
    for uc, m in sorted(report["metrics_by_uc"].items(), key=lambda kv: int(kv[0])):
        print(f"{uc:>4} {m['tp']:>8} {m['fp']:>8} {m['fn']:>8} "
              f"{m['precision']:>7.4f} {m['recall']:>7.4f} {m['f1']:>7.4f}")
    print(f"mean F1 (all UCs): {report['mean_f1_all_ucs']:.4f}")
    return 0


def cmd_baseline(args) -> int:
    """
    Freeze the CURRENT engine state as the calibration baseline:

      1. copy fact_detected_inconsistency.parquet -> baseline snapshot file
      2. copy detection metrics JSON -> baseline JSON
      3. crops the current detection_quality.json (main artifact refresh)
    """
    t0 = time.time()
    detections = _detections_from_gold()
    log = _log_from_bronze()
    metrics = compute_uc_metrics(detections, log, UC_DAILY_MAP)
    report = build_report(metrics, detections, {
        "injection_log_rows": int(len(log)),
        "baseline_ref": "baseline (pre-calibration engine run)",
        "calibration_notes": "baseline engine state frozen at this timestamp; "
                             "post-calibration runs must compare against it",
    })

    os.makedirs(SNAPSHOT_DIR, exist_ok=True)
    shutil.copyfile(DET_PATH, os.path.join(SNAPSHOT_DIR,
                                           "fact_detected_inconsistency_baseline.parquet"))
    _write_json(SNAPSHOT_PATH, report)
    _write_json(OUT_PATH, report)
    _update_manifest(report)

    print(f"baseline snapshot frozen -> {SNAPSHOT_PATH} ({time.time() - t0:.1f}s)")
    print(f"{'UC':>4} {'TP':>8} {'FP':>8} {'FN':>8} {'P':>7} {'R':>7} {'F1':>7}")
    for uc, m in sorted(report["metrics_by_uc"].items(), key=lambda kv: int(kv[0])):
        print(f"{uc:>4} {m['tp']:>8} {m['fp']:>8} {m['fn']:>8} "
              f"{m['precision']:>7.4f} {m['recall']:>7.4f} {m['f1']:>7.4f}")
    print(f"mean F1 (all UCs): {report['mean_f1_all_ucs']:.4f}")
    return 0


def cmd_compare(args) -> int:
    """Compare current metrics against the frozen baseline snapshot."""
    if not os.path.exists(SNAPSHOT_PATH):
        print("baseline snapshot missing; run `python pipelines/detection_quality.py baseline`",
              file=sys.stderr)
        return 2
    t0 = time.time()
    with open(SNAPSHOT_PATH, "r", encoding="utf-8") as f:
        baseline = json.load(f)
    detections = _detections_from_gold()
    log = _log_from_bronze()
    metrics = compute_uc_metrics(detections, log, UC_DAILY_MAP)

    current = build_report(metrics, detections, {
        "injection_log_rows": int(len(log)),
        "baseline_ref": os.path.basename(SNAPSHOT_PATH),
        "calibration_notes": None,
    })

    print(f"{'UC':>4} | {'F1 base':>8} | {'F1 now':>8} | {'TP delta':>9} | {'FP delta':>9} | {'FN delta':>9}")
    rows = []
    for key, m in sorted(current["metrics_by_uc"].items(), key=lambda kv: int(kv[0])):
        base_m = baseline["metrics_by_uc"].get(key, {})
        rows.append({
            "uc": int(key),
            "f1_baseline": base_m.get("f1"),
            "f1_current": m["f1"],
            "tp_baseline": base_m.get("tp"), "tp_current": m["tp"],
            "fp_baseline": base_m.get("fp"), "fp_current": m["fp"],
            "fn_baseline": base_m.get("fn"), "fn_current": m["fn"],
        })
        print(f"{key:>4} | {base_m.get('f1', 0):>8.4f} | {m['f1']:>8.4f} | "
              f"{m['tp'] - base_m.get('tp', 0):>+9} | "
              f"{m['fp'] - base_m.get('fp', 0):>+9} | "
              f"{m['fn'] - base_m.get('fn', 0):>+9}")

    current["baseline_comparison"] = {
        "baseline_artifact": os.path.basename(SNAPSHOT_PATH),
        "rows": rows,
    }
    if args.save:
        _write_json(OUT_PATH, current)
        _update_manifest(current)
        print(f"current metrics (vs baseline) -> {OUT_PATH}")

    print(f"compare done ({time.time() - t0:.1f}s)")
    return 0


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        description="Detection quality metrics vs injection ground truth")
    parser.add_argument("mode", nargs="?", default="refresh",
                        choices=["refresh", "baseline", "compare"],
                        help="refresh (default) | baseline | compare")
    parser.add_argument("--save", action="store_true",
                        help="compare: persist current metrics into the artifact")
    parser.add_argument("--keep-calibration", action="store_true",
                        help="refresh: preserve prior calibration_notes")
    args = parser.parse_args(argv)
    if args.mode == "baseline":
        return cmd_baseline(args)
    if args.mode == "compare":
        return cmd_compare(args)
    return cmd_refresh(args)


if __name__ == "__main__":
    raise SystemExit(main())
