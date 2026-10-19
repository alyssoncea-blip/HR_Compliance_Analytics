"""
Benchmark harness for the 32-rule validation engine.

Runs the engine as a subprocess (the engine itself is never modified) in
configurable scenarios -- `full` (all competences) or `partitioned` (an
explicit competence subset compared against full on the same set) --
parses its stdout for the per-UC breakdown, and appends a record to an
append-only benchmark history (capped at 50 runs).

Usage:
    python pipelines/benchmark_engine.py --scenario full
    python pipelines/benchmark_engine.py --scenario partitioned --competence 2024-06
"""
import argparse, json, os, platform, re, subprocess, sys, time
from datetime import datetime, timezone

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ENGINE = os.path.join("pipelines", "validation_engine.py")
DEFAULT_OUT = os.path.join(ROOT, "data", "gold", "observability", "engine_benchmark.json")
ENGINE_MANIFEST = os.path.join(ROOT, "data", "gold", "validation_manifest.json")
HISTORY_CAP = 50
ENGINE_TIMEOUT_S = 1800

UC_HEADER = re.compile(r"^\[(?:UC)(\d+)\]")
DETECTED_LINE = re.compile(r"^  -> (\d+) detected \(([\d.]+)s\)")
SKIPPED_LINE = re.compile(r"^  -> skipped")
SUMMARY_LINE = re.compile(
    r"^  UC(\d+)\s+(.+?)\s{2,}(\S+)\s+(\d+) ocorr\.\s+R\$\s*(-?[\d.,]+)\s*$"
)
TOTAL_SUMMARY_LINE = re.compile(r"^  TOTAL\s+(\d+) ocorr\.")
TOTAL_DETECTIONS_LINE = re.compile(r"^  Total detections: (\d+)", re.M)
TOTAL_TIME_LINE = re.compile(r"^  Total time: ([\d.]+)s", re.M)


def parse_engine_output(stdout):
    """Parse engine stdout into per-UC breakdown and run-level counts.

    Per-UC tuple of (uc, rule_name, detections, runtime_s): runtime comes
    from the `-> N detected (Xs)` line under the latest `[UCnn]` header and
    is None for skipped blocks; rule_name/detections come from the final
    SUMMARY BY USE CASE table.
    """
    per_uc, by_uc_runtime, current_uc = {}, {}, None
    summary_total = None
    for line in stdout.splitlines():
        m = UC_HEADER.match(line)
        if m:
            current_uc = int(m.group(1))
            continue
        m = DETECTED_LINE.match(line)
        if m and current_uc is not None:
            by_uc_runtime[current_uc] = float(m.group(2))
            continue
        m = SUMMARY_LINE.match(line)
        if m:
            uc, rule_name, detections = int(m.group(1)), m.group(2), int(m.group(4))
            count = per_uc.get(uc, {})
            count.update(rule_name=rule_name, detections=detections)
            per_uc[uc] = count
            continue
        m = TOTAL_SUMMARY_LINE.match(line)
        if m:
            summary_total = int(m.group(1))
    per_uc_runtime = {
        f"UC{uc:02d}": t for uc, t in sorted(by_uc_runtime.items())
    }
    for uc, entry in per_uc.items():
        entry["uc"] = uc
        entry["runtime_s"] = by_uc_runtime.get(uc)
    rows = [per_uc[uc] for uc in sorted(per_uc)]
    rows = [
        {"uc": e["uc"], "rule_name": e["rule_name"], "detections": e["detections"],
         "runtime_s": e["runtime_s"]}
        for e in rows
    ]
    detections_by_uc = {f"UC{e['uc']:02d}": e["detections"] for e in rows}
    return summary_total, rows, per_uc_runtime, detections_by_uc


def _engine_commit():
    try:
        out = subprocess.run(
            ["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True,
            text=True, timeout=15,
        )
        if out.returncode == 0:
            return out.stdout.strip()
    except Exception:
        pass
    return None


def _host_info():
    return {
        "python": sys.version.split()[0],
        "machine": platform.machine(),
        "platform": platform.platform(),
        "cpu_count": os.cpu_count(),
    }


def _build_engine_cmd(scenario, competences, competence_from, competence_to):
    cmd = [sys.executable, ENGINE]
    if scenario == "partitioned":
        if not competences:
            raise ValueError("partitioned scenario requires at least one --competence")
        for c in competences:
            cmd += ["--competence", c]
        if competence_from:
            cmd += ["--competence-from", competence_from]
        if competence_to:
            cmd += ["--competence-to", competence_to]
    return cmd


def run_benchmark(scenario, competences, competence_from=None, competence_to=None,
                  out_path=DEFAULT_OUT, timeout_s=ENGINE_TIMEOUT_S):
    """Run the engine once, parse stdout + its manifest, append to history."""
    cmd = _build_engine_cmd(scenario, competences, competence_from, competence_to)
    env = dict(os.environ, PYTHONIOENCODING="utf-8")
    t0 = time.perf_counter()
    proc = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True,
                          encoding="utf-8", errors="replace", timeout=timeout_s,
                          env=env)
    runtime_s = time.perf_counter() - t0
    if proc.returncode != 0:
        sys.stderr.write(proc.stdout[-2000:] + proc.stderr[-2000:])
        raise SystemExit(f"engine exited with code {proc.returncode}")

    stdout = proc.stdout
    summary_total, per_uc_rows, per_uc_runtime, detections_by_uc = parse_engine_output(stdout)
    m = TOTAL_DETECTIONS_LINE.search(stdout)
    total_detections = int(m.group(1)) if m else None
    m = TOTAL_TIME_LINE.search(stdout)
    engine_reported = float(m.group(1)) if m else None
    manifest = {}
    if os.path.exists(ENGINE_MANIFEST):
        with open(ENGINE_MANIFEST, "r", encoding="utf-8") as f:
            manifest = json.load(f)
    record = {
        "run_id": datetime.now(timezone.utc).isoformat(),
        "scenario": scenario,
        "competences": list(competences),
        "runtime_s": round(runtime_s, 3),
        "detections": {
            "total_stdout": total_detections,
            "total_uc_summary": summary_total,
            "engine_reported_runtime_s": engine_reported,
        },
        "per_uc": per_uc_rows,
        "detections_by_uc": detections_by_uc,
        "per_uc_runtime_s": per_uc_runtime,
        "manifest_fields": {
            "mode": manifest.get("mode"),
            "competences_processed": manifest.get("competences_processed"),
            "competences_available": manifest.get("competences_available"),
            "total_detections": manifest.get("total_detections"),
            "total_estimated_impact": manifest.get("total_estimated_impact"),
        },
        "host_info": _host_info(),
        "engine_commit": _engine_commit(),
        "engine_returncode": proc.returncode,
    }
    if scenario == "full":
        # full mode runs every available competence; record it from the manifest
        avail = manifest.get("competences_available")
        if avail:
            record["competences"] = avail
        else:
            record["competences"] = ["all (full run)"]
    _append_history(record, out_path)
    return record


def _append_history(record, out_path):
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    history = []
    if os.path.exists(out_path):
        with open(out_path, "r", encoding="utf-8") as f:
            history = json.load(f)
    history.append(record)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(history[-HISTORY_CAP:], f, indent=2, ensure_ascii=False)


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Benchmark harness for the validation engine (append-only history)"
    )
    parser.add_argument("--scenario", choices=["full", "partitioned"], required=True)
    parser.add_argument("--competence", action="append", metavar="YYYY-MM",
                        help="competence passed to the engine in partitioned mode (repeatable)")
    parser.add_argument("--competence-from", dest="competence_from",
                        metavar="YYYY-MM", help="forwarded to the engine")
    parser.add_argument("--competence-to", dest="competence_to",
                        metavar="YYYY-MM", help="forwarded to the engine")
    parser.add_argument("--out", default=DEFAULT_OUT, help="benchmark history JSON path")
    args = parser.parse_args(argv)
    record = run_benchmark(
        args.scenario, args.competence or [], args.competence_from,
        args.competence_to, out_path=args.out,
    )
    print(f"Benchmark record appended: {args.out}")
    print(f"  scenario={record['scenario']} comps={record['competences']} "
          f"runtime={record['runtime_s']}s detections={record['detections']['total_stdout']}")

if __name__ == "__main__":
    main()
