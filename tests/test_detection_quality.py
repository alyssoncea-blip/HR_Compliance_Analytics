"""Unit tests for detection-quality metric methodology (no data/ access).

The metric module matches rule-engine detections against the injection ground
truth log. Employee-scoped UCs (log ref = ''), daily-ref UCs and the mean-F1
scope are exercised here on controlled in-memory frames.
"""
import os
import sys

import pandas as pd
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "pipelines"))
import detection_quality as dq


DETECTION_COLUMNS = [
    "use_case", "employee_id", "competence", "rule_origin", "rule_name",
]
LOG_COLUMNS = ["use_case", "employee_id", "ref", "detail"]


def _dets(rows):
    return pd.DataFrame(rows, columns=DETECTION_COLUMNS)


def _log(rows):
    df = pd.DataFrame(rows, columns=LOG_COLUMNS)
    df["use_case"] = df["use_case"].astype(int)
    return df


# ---------------------------------------------------------------------------


class TestMonthPairMatching:
    def test_tp_fp_fn_on_month_keyed_uc(self):
        dets = _dets([
            (1, 100, "2024-01", "rule_engine", "X"),
            (1, 100, "2024-02", "rule_engine", "X"),
            (1, 200, "2024-03", "rule_engine", "X"),
            (1, 200, "2024-04", "rule_engine", "X"),
        ])
        log = _log([
            (1, 100, "2024-01", "x"),
            (1, 100, "2024-02", "x"),
            (1, 300, "2024-05", "x"),
        ])
        m = dq.compute_uc_metrics(dets, log, dq.UC_DAILY_MAP)
        assert m[1]["tp"] == 2
        assert m[1]["fp"] == 2
        assert m[1]["fn"] == 1
        assert m[1]["precision"] == pytest.approx(0.5)
        assert m[1]["recall"] == pytest.approx(2 / 3, abs=1e-4)
        assert m[1]["f1"] == pytest.approx(2 * 0.5 * (2 / 3) / (0.5 + 2 / 3),
                                           abs=1e-4)

    def test_day_ref_counts_as_month_pair(self):
        dets = _dets([(1, 100, "2024-03-15", "rule_engine", "X")])
        log = _log([(1, 100, "2024-03-20", "x")])
        m = dq.compute_uc_metrics(dets, log, dq.UC_DAILY_MAP)
        assert m[1]["tp"] == 1
        assert m[1]["fp"] == 0
        assert m[1]["fn"] == 0

    def test_detection_on_same_day_but_only_month_ref(self):
        dets = _dets([(1, 100, "2024-03", "rule_engine", "X")])
        log = _log([(1, 100, "2024-03-01", "x")])
        m = dq.compute_uc_metrics(dets, log, dq.UC_DAILY_MAP)
        # truth carries both (emp, day) and (emp, month) pairs; month detection
        # matches the month pair
        assert m[1]["tp"] == 1
        assert m[1]["fp"] == 0

    def test_simulation_markers_excluded(self):
        dets = _dets([
            (1, 100, "2024-01", "rule_engine", "X"),
            (1, 100, "2024-01", "simulation_marker", "X"),
        ])
        log = _log([(1, 100, "2024-01", "x")])
        m = dq.compute_uc_metrics(dets, log, dq.UC_DAILY_MAP)
        # marker rows stay in the gold file but carry no prediction weight
        assert m[1]["detected_rows"] == 2
        assert m[1]["fp"] == 0
        assert m[1]["tp"] == 1


# ---------------------------------------------------------------------------


class TestEmployeeScopedMatching:
    def test_refless_uc_matches_on_employee_id(self):
        dets = _dets([
            (8, 100, "N/A", "rule_engine", "X"),
            (8, 200, "2026-09-25", "rule_engine", "X"),
        ])
        log = _log([
            (8, 100, "", "x"),
            (8, 300, "", "x"),
        ])
        m = dq.compute_uc_metrics(dets, log, dq.UC_DAILY_MAP)
        assert m[8]["tp"] == 1
        assert m[8]["fp"] == 1
        assert m[8]["fn"] == 1

    def test_repeated_log_rows_dedupe_to_one_employee(self):
        dets = _dets([(8, 100, "N/A", "rule_engine", "X")])
        log = _log([
            (8, 100, "", "x"),
            (8, 100, "", "x"),
            (8, 100, "", "x"),
        ])
        m = dq.compute_uc_metrics(dets, log, dq.UC_DAILY_MAP)
        assert m[8]["injected_pairs"] == 1
        assert m[8]["tp"] == 1
        assert m[8]["fn"] == 0

    def test_uc20_58_log_vs_deadline_competence(self):
        dets = _dets([
            (20, 7, "N/A", "rule_engine", "X"),
            (20, 8, "2024-06-01", "rule_engine", "X"),
        ])
        log = _log([
            (20, 7, "", "x"),
            (20, 9, "", "x"),
        ])
        m = dq.compute_uc_metrics(dets, log, dq.UC_DAILY_MAP)
        assert m[20]["tp"] == 1
        assert m[20]["fp"] == 1
        assert m[20]["fn"] == 1


# ---------------------------------------------------------------------------


class TestMeanF1Scope:
    def test_uc17_excluded_from_active_mean(self):
        dets = _dets([
            (1, 100, "2024-01", "rule_engine", "X"),
        ])
        log = _log([
            (1, 100, "2024-01", "x"),
            (17, 100, "", "x"),
        ])
        report = dq.build_report(
            dq.compute_uc_metrics(dets, log, dq.UC_DAILY_MAP), dets,
            {"injection_log_rows": 2, "baseline_ref": None,
             "calibration_notes": None},
        )
        # UC1 contributes F1 1.0, UC17 F1 0.0 -> all mean 0.5
        assert report["mean_f1_all_ucs"] == pytest.approx(0.5)
        # active mean excludes UC17
        assert report["mean_f1_active_ucs"] == pytest.approx(1.0)

    def test_calibration_notes_default_present(self):
        dets = _dets([(1, 100, "2024-01", "rule_engine", "X")])
        log = _log([(1, 100, "2024-01", "x")])
        report = dq.build_report(
            dq.compute_uc_metrics(dets, log, dq.UC_DAILY_MAP), dets,
            {"injection_log_rows": 1, "baseline_ref": None,
             "calibration_notes": None},
        )
        assert "uc28_undetectable" in report["calibration_notes"]
        assert "employee_scoped" in report["calibration_notes"]

    def test_high_severity_monthly_targets_uses_known_list(self):
        dets = _dets([(1, 100, "2024-01", "rule_engine", "X")])
        log = _log([(1, 100, "2024-01", "x")])
        report = dq.build_report(
            dq.compute_uc_metrics(dets, log, dq.UC_DAILY_MAP), dets,
            {"injection_log_rows": 1, "baseline_ref": None,
             "calibration_notes": None},
        )
        # targets only include UCs present in the metric scope
        assert sorted(report["high_severity_monthly_targets"]) == ["1"]
        assert 1 in dq.HIGH_SEV_MONTHLY
        assert set(dq.HIGH_SEV_MONTHLY) < set(range(1, 33))

    def test_uc_sorted_scoped_list_is_stable(self):
        assert dq.UC_EMPLOYEE_SCOPED == {8, 17, 19, 20, 23, 26, 31, 32}
