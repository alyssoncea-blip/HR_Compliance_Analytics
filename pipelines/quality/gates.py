"""Quality gates resolution for the governance pipeline.

Pure logic, no DuckDB/filesystem coupling, so gates can be evaluated directly
against check result dicts. Business-rule checks intentionally fail on the
synthetic data (injected inconsistencies), so by default the regra_negocio
gate is informational; it can be flipped to blocking via configuration.
"""
import json

DEFAULT_CONFIG = {
    "warn_margin_pct": 0.5,
    "gates": [
        {"id": "completude_990", "mode": "blocking", "dimension": "completude", "threshold_pct": 99.0},
        {"id": "unicidade_100", "mode": "blocking", "dimension": "unicidade", "threshold_pct": 100.0},
        {"id": "integ_ref_995", "mode": "blocking", "dimension": "integ_ref", "threshold_pct": 99.5},
        {"id": "consistencia_950", "mode": "blocking", "dimension": "consistencia", "threshold_pct": 95.0},
        {"id": "validade_990", "mode": "blocking", "dimension": "validade", "threshold_pct": 99.0},
        {"id": "regra_negocio_informational", "mode": "informational", "dimension": "regra_negocio"},
        {"id": "fact_payroll_fk_strict", "mode": "blocking", "table": "silver.fact_payroll", "dimension": "integ_ref", "threshold_pct": 99.9},
    ],
}


def load_gates_config(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _matches(check, gate):
    if "dimension" in gate and check.get("dimension") != gate["dimension"]:
        return False
    if "table" in gate:
        full = f"{check.get('layer')}.{check.get('table_name')}"
        if full != gate["table"] and check.get("table_name") != gate["table"]:
            return False
    return True


def _check_pct(check):
    if check.get("status") == "ERROR":
        return 0.0
    return float(check.get("pass_pct", 0.0))


def _violated(check, threshold):
    if check.get("status") in ("ERROR", "FAIL"):
        return True
    return threshold is not None and float(check.get("pass_pct", 0.0)) < threshold


def resolve_gates(results, config=None):
    """Resolve quality gates against check results.

    results: iterable of check dicts (layer, table_name, dimension, status, pass_pct).
    config: gates config dict; when None, DEFAULT_CONFIG is used.
    Returns dict with per-gate verdicts and the aggregated overall status.
    """
    cfg = config if config is not None else DEFAULT_CONFIG
    margin = float(cfg.get("warn_margin_pct", 0.5))
    checks = list(results)
    gates_out = []

    for gate in cfg.get("gates", []):
        mode = gate.get("mode", "blocking")
        threshold = gate.get("threshold_pct")
        matched = [c for c in checks if _matches(c, gate)]

        if not matched or (mode == "blocking" and threshold is None):
            entry = {
                "id": gate.get("id"),
                "mode": mode,
                "dimension": gate.get("dimension"),
                "table": gate.get("table"),
                "threshold_pct": threshold,
                "matched_checks": len(matched),
                "pass_pct": None,
                "status": "ERROR",
                "violations": [],
            }
            gates_out.append(entry)
            continue

        worst = round(min(_check_pct(c) for c in matched), 4)
        violations = [
            {
                "check": f"{c.get('layer')}.{c.get('table_name')}",
                "dimension": c.get("dimension"),
                "status": c.get("status"),
                "pass_pct": round(_check_pct(c), 4),
            }
            for c in matched
            if _violated(c, threshold)
        ]

        if any(c.get("status") == "ERROR" for c in matched):
            status = "ERROR"
        elif mode == "informational":
            status = "INFORMATIONAL" if violations else "PASS"
        elif worst >= threshold:
            status = "PASS"
        elif worst >= threshold - margin:
            status = "WARN"
        else:
            status = "FAIL"

        gates_out.append({
            "id": gate.get("id"),
            "mode": mode,
            "dimension": gate.get("dimension"),
            "table": gate.get("table"),
            "threshold_pct": threshold,
            "matched_checks": len(matched),
            "pass_pct": worst,
            "status": status,
            "violations": violations,
        })

    blocking_bad = [g for g in gates_out if g["mode"] == "blocking" and g["status"] in ("FAIL", "ERROR")]
    warned = [g for g in gates_out if g["status"] == "WARN"]
    informational = [g for g in gates_out if g["status"] == "INFORMATIONAL"]

    if blocking_bad:
        overall = "FAIL"
    elif warned:
        overall = "WARN"
    else:
        overall = "PASS"

    return {
        "overall_status": overall,
        "warn_margin_pct": margin,
        "gates": gates_out,
        "blocking_gate_failures": [g["id"] for g in blocking_bad],
        "warned_gates": [g["id"] for g in warned],
        "informational_gate_findings": [g["id"] for g in informational],
    }
