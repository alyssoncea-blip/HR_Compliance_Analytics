"""Trend regression and data freshness evaluation for the governance pipeline.

Pure logic, no DuckDB/filesystem coupling, so both evaluators can run against
plain dicts:

- evaluate_trend: compares the current run's checks against the persisted
  baseline of the previous run. Checks are matched by a normalized key
  (``layer.check_sql``). A check whose fail_count increased vs the baseline is
  a REGRESSION; decreased is IMPROVED; equal is STABLE. The trend gate then
  resolves to PASS/WARN/FAIL per configuration (>=1 critical regression -> FAIL;
  N regressions >= warn_on_regressions -> WARN).

- evaluate_freshness: reports the age (in hours) of key Parquet files per
  layer (path keys look like "bronze/employees") against per-layer thresholds
  (e.g. bronze >48h -> WARN, >168h -> FAIL). Receives a dict path -> age_hours.

- merge_overall_status: folds trend/freshness verdicts into the gates
  overall_status. Defaults are conservative: a blocking-mode trend FAIL blocks
  the overall status; freshness defaults to warn_only (never blocks).
"""
import json

TREND_CONFIG_DEFAULTS = {
    "mode": "blocking",
    "critical_severities": ["critical"],
    "fail_on_critical_regressions": 1,
    "warn_on_regressions": 3,
}

FRESHNESS_LAYER_DEFAULTS = {
    "bronze": {"warn_hours": 48, "fail_hours": 168},
    "silver": {"warn_hours": 72, "fail_hours": 336},
    "gold": {"warn_hours": 168, "fail_hours": 720},
}

FRESHNESS_CONFIG_DEFAULTS = {
    "mode": "warn_only",
    "layers": {k: dict(v) for k, v in FRESHNESS_LAYER_DEFAULTS.items()},
}


def load_trend_config(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def normalize_check_sql(sql):
    """Collapse whitespace and lowercase so semantically identical SQL matches."""
    return " ".join(str(sql or "").split()).lower()


def check_key(layer, check_sql):
    """Stable identity for a check across runs: layer + normalized SQL."""
    return f"{layer}.{normalize_check_sql(check_sql)}"


def _trend_cfg(config):
    cfg = dict(TREND_CONFIG_DEFAULTS)
    if config and isinstance(config.get("trend"), dict):
        cfg.update(config["trend"])
    return cfg


def _freshness_cfg(config):
    cfg = {
        "mode": FRESHNESS_CONFIG_DEFAULTS["mode"],
        "layers": {k: dict(v) for k, v in FRESHNESS_LAYER_DEFAULTS.items()},
    }
    if config and isinstance(config.get("freshness"), dict):
        fc = config["freshness"]
        cfg["mode"] = fc.get("mode", cfg["mode"])
        if isinstance(fc.get("layers"), dict):
            for layer, thresholds in fc["layers"].items():
                if isinstance(thresholds, dict):
                    cfg["layers"].setdefault(layer, {}).update(thresholds)
    return cfg


def _finding(key, check, change, baseline_fail_count, delta):
    return {
        "check_key": key,
        "layer": check.get("layer"),
        "table_name": check.get("table_name"),
        "dimension": check.get("dimension"),
        "severity": check.get("severity"),
        "change": change,
        "fail_count": check.get("fail_count"),
        "baseline_fail_count": baseline_fail_count,
        "delta": delta,
    }


def _is_numeric_fail_count(value):
    return isinstance(value, (int, float)) and value >= 0


def evaluate_trend(results, baseline, config=None):
    """Compare current checks against the previous run's baseline.

    results: iterable of check dicts (layer, table_name, dimension, check_sql,
    fail_count, pass_pct, severity, status) as produced by the governance run.
    baseline: previous-run mapping check_key -> {fail_count, pass_pct,
    updated_at}, either flat or wrapped in {"checks": {...}}. None/empty means
    first run: verdict is STABLE with first_run=True.
    config: full gates config dict; the "trend" section is optional and
    defaults to TREND_CONFIG_DEFAULTS.
    """
    cfg = _trend_cfg(config)

    current = {}
    for r in results:
        current[check_key(r.get("layer"), r.get("check_sql"))] = dict(r)

    if not baseline or not isinstance(baseline, dict):
        return _empty_trend(cfg, current, first_run=True)
    prev = baseline.get("checks", baseline)
    if not isinstance(prev, dict) or not prev:
        return _empty_trend(cfg, current, first_run=True)

    regressions, improvements, new_checks = [], [], []
    stable_count = 0

    for key, r in current.items():
        status = r.get("status")
        fc = r.get("fail_count")
        base = prev.get(key)

        if base is None:
            new_checks.append(key)
            continue

        base_fc = base.get("fail_count") if isinstance(base, dict) else None
        if status == "ERROR" or not _is_numeric_fail_count(fc):
            # An errored check cannot be compared numerically; it is always
            # treated as a regression (we lost visibility into it).
            regressions.append(_finding(key, r, "REGRESSION", base_fc, None))
        elif base_fc is None or not _is_numeric_fail_count(base_fc):
            # Baseline was errored/unknown; any numeric result now is a recovery.
            improvements.append(_finding(key, r, "IMPROVED", base_fc, None))
        elif fc > base_fc:
            regressions.append(_finding(key, r, "REGRESSION", base_fc, fc - base_fc))
        elif fc < base_fc:
            improvements.append(_finding(key, r, "IMPROVED", base_fc, fc - base_fc))
        else:
            stable_count += 1

    retired_checks = sorted(k for k in prev if k not in current)
    critical_severities = set(cfg.get("critical_severities") or [])
    critical_regressions = [
        r for r in regressions if r.get("severity") in critical_severities
    ]

    if len(critical_regressions) >= int(cfg.get("fail_on_critical_regressions", 1)):
        status = "FAIL"
    elif len(regressions) >= int(cfg.get("warn_on_regressions", 3)):
        status = "WARN"
    else:
        status = "PASS"

    return {
        "mode": cfg.get("mode", "blocking"),
        "status": status,
        "first_run": False,
        "checks_compared": len(current),
        "stable_count": stable_count,
        "regression_count": len(regressions),
        "improvement_count": len(improvements),
        "new_checks": sorted(new_checks),
        "retired_checks": retired_checks,
        "regressions": regressions,
        "improvements": improvements,
        "critical_regressions": critical_regressions,
        "thresholds": {
            "fail_on_critical_regressions": cfg.get("fail_on_critical_regressions"),
            "warn_on_regressions": cfg.get("warn_on_regressions"),
            "critical_severities": sorted(critical_severities),
        },
    }


def _empty_trend(cfg, current, first_run):
    return {
        "mode": cfg.get("mode", "blocking"),
        "status": "PASS",
        "first_run": first_run,
        "checks_compared": len(current),
        "stable_count": 0,
        "regression_count": 0,
        "improvement_count": 0,
        "new_checks": sorted(current),
        "retired_checks": [],
        "regressions": [],
        "improvements": [],
        "critical_regressions": [],
        "thresholds": {
            "fail_on_critical_regressions": cfg.get("fail_on_critical_regressions"),
            "warn_on_regressions": cfg.get("warn_on_regressions"),
            "critical_severities": sorted(set(cfg.get("critical_severities") or [])),
        },
    }


def evaluate_freshness(paths, config=None):
    """Evaluate age (hours) of key Parquet files against per-layer thresholds.

    paths: dict mapping "<layer>/<table>" -> age in hours (e.g.
    "bronze/employees" -> 51.2). Pure: no filesystem access here.
    config: full gates config dict; the "freshness" section is optional and
    defaults to FRESHNESS_CONFIG_DEFAULTS.
    """
    cfg = _freshness_cfg(config)

    rows = []
    for path in sorted(paths):
        age = paths[path]
        layer = str(path).split("/", 1)[0]
        thresholds = cfg["layers"].get(layer)
        if thresholds is None:
            rows.append({
                "path": path, "layer": layer,
                "age_hours": round(float(age), 2),
                "warn_hours": None, "fail_hours": None,
                "status": "UNKNOWN",
            })
            continue
        warn_hours = thresholds.get("warn_hours")
        fail_hours = thresholds.get("fail_hours")
        if fail_hours is not None and age > fail_hours:
            status = "FAIL"
        elif warn_hours is not None and age > warn_hours:
            status = "WARN"
        else:
            status = "PASS"
        rows.append({
            "path": path, "layer": layer,
            "age_hours": round(float(age), 2),
            "warn_hours": warn_hours, "fail_hours": fail_hours,
            "status": status,
        })

    fail_tables = [r["path"] for r in rows if r["status"] == "FAIL"]
    warn_tables = [r["path"] for r in rows if r["status"] == "WARN"]
    unknown_tables = [r["path"] for r in rows if r["status"] == "UNKNOWN"]
    max_age = round(max((float(paths[p]) for p in paths), default=0.0), 2)

    if fail_tables:
        status = "FAIL"
    elif warn_tables:
        status = "WARN"
    else:
        status = "PASS"

    return {
        "mode": cfg["mode"],
        "status": status,
        "tables_checked": len(rows),
        "warn_tables": warn_tables,
        "fail_tables": fail_tables,
        "unknown_tables": unknown_tables,
        "max_age_hours": max_age,
        "tables": rows,
        "thresholds": {layer: dict(th) for layer, th in cfg["layers"].items()},
    }


def merge_overall_status(overall, trend_verdict=None, freshness_verdict=None):
    """Fold trend/freshness verdicts into the gates overall_status.

    Blocking-mode FAIL raises overall to FAIL; any WARN raises PASS to WARN.
    warn_only FAIL is capped at WARN. Informational never changes overall.
    The overall status is only ever escalated, never downgraded.
    """
    blocking_fail = overall == "FAIL"
    warn_present = overall == "WARN"

    for verdict in (trend_verdict, freshness_verdict):
        if not isinstance(verdict, dict):
            continue
        status = verdict.get("status")
        mode = verdict.get("mode", "blocking")
        if mode not in ("blocking", "warn_only", "informational"):
            mode = "blocking"
        if status == "FAIL":
            if mode == "blocking":
                blocking_fail = True
            elif mode == "warn_only":
                warn_present = True
        elif status == "WARN":
            warn_present = True

    if blocking_fail:
        return "FAIL"
    if warn_present:
        return "WARN"
    return "PASS"
