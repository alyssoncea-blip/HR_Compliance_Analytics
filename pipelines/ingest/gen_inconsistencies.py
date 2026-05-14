"""
Injects deliberate inconsistencies into clean synthetic data to cover all 32 use cases.
Each function modifies records in-place and returns a log of what was injected.
"""
import random
from typing import List, Dict, Tuple
from datetime import date, timedelta

from config import INCONSISTENCY_RATES, CCT_RULES, SEED

random.seed(SEED + 5)


def _sample_employees(employees: List[dict], rate: float) -> List[dict]:
    count = max(1, int(len(employees) * rate))
    return random.sample([e for e in employees if e["status"] != "terminated"], count)


def _get_cct(emp: dict) -> object:
    uid = emp.get("union_id")
    if uid is None:
        return CCT_RULES[0]
    idx = uid - 1
    return CCT_RULES[idx] if 0 <= idx < len(CCT_RULES) else CCT_RULES[0]


# ---------------------------------------------------------------------------
# UC1: HE Progressive wrong — second+ hour paid at 50% instead of 70%
# ---------------------------------------------------------------------------

def _log(uc: int, eid: int, detail: str, ref: str = ""):
    return {"use_case": uc, "employee_id": eid, "ref": ref, "detail": detail}

def _get_hourly(emp: dict, employees: List[dict]) -> float:
    return emp["base_salary"] / (emp["weekly_hours"] * 4.33)

def inject_he_progressive_wrong(payroll: List[dict], employees: List[dict]) -> List[dict]:
    affected = _sample_employees(employees, INCONSISTENCY_RATES["he_progressive_wrong"])
    log = []
    emp_map = {e["employee_id"]: e for e in employees}
    for rec in payroll:
        if any(e["employee_id"] == rec["employee_id"] for e in affected):
            if rec["overtime_70_hours"] > 0:
                old = rec["overtime_70_amount"]
                emp = emp_map[rec["employee_id"]]
                cct = _get_cct(emp)
                hourly = _get_hourly(emp, employees)
                rec["overtime_70_amount"] = round(rec["overtime_70_hours"] * hourly * (1 + cct.he_first_hour_percent), 2)
                rec["gross_total"] = round(rec["gross_total"] - old + rec["overtime_70_amount"], 2)
                rec["net_total"] = round(rec["gross_total"] - rec["inss_discount"] - rec["irrf_discount"] - rec["union_discount"] - rec["other_discounts"], 2)
                log.append(_log(1, rec["employee_id"], "HE adicional paga a 50% em vez de 70%", rec["competence"]))
    return log


# ---------------------------------------------------------------------------
# UC2: HE Sunday paid at 50% instead of 100%
# ---------------------------------------------------------------------------

def inject_he_sunday_wrong(payroll: List[dict], employees: List[dict]) -> List[dict]:
    affected = _sample_employees(employees, INCONSISTENCY_RATES["he_sunday_wrong"])
    log = []
    emp_map = {e["employee_id"]: e for e in employees}
    for rec in payroll:
        if any(e["employee_id"] == rec["employee_id"] for e in affected):
            if rec["overtime_100_hours"] > 0:
                old = rec["overtime_100_amount"]
                emp = emp_map[rec["employee_id"]]
                hourly = _get_hourly(emp, employees)
                rec["overtime_100_amount"] = round(rec["overtime_100_hours"] * hourly * (1 + 0.50), 2)
                rec["gross_total"] = round(rec["gross_total"] - old + rec["overtime_100_amount"], 2)
                rec["net_total"] = round(rec["gross_total"] - rec["inss_discount"] - rec["irrf_discount"] - rec["union_discount"] - rec["other_discounts"], 2)
                log.append(_log(2, rec["employee_id"], "HE domingo paga a 50% em vez de 100%", rec["competence"]))
    return log


# ---------------------------------------------------------------------------
# UC3: Night shift missing — worked 22h-5h without additional
# ---------------------------------------------------------------------------

def inject_night_shift_missing(payroll: List[dict], employees: List[dict]) -> List[dict]:
    affected = _sample_employees(employees, INCONSISTENCY_RATES["night_shift_missing"])
    log = []
    for rec in payroll:
        if any(e["employee_id"] == rec["employee_id"] for e in affected):
            if rec["night_shift_hours"] > 0 and rec["night_shift_amount"] > 0:
                rec["night_shift_amount"] = 0.0
                rec["gross_total"] = round(rec["gross_total"], 2)
                rec["net_total"] = round(rec["gross_total"] - rec["inss_discount"] - rec["irrf_discount"] - rec["union_discount"] - rec["other_discounts"], 2)
                log.append(_log(3, rec["employee_id"], "Adicional noturno não aplicado", rec["competence"]))
    return log


# ---------------------------------------------------------------------------
# UC4: Hour bank exceeded limit (> 40h)
# ---------------------------------------------------------------------------

def inject_hour_bank_exceeded(hour_bank: List[dict], employees: List[dict]) -> List[dict]:
    affected = _sample_employees(employees, INCONSISTENCY_RATES["hour_bank_exceeded"])
    log = []
    for rec in hour_bank:
        if any(e["employee_id"] == rec["employee_id"] for e in affected):
            if rec["current_balance"] > 0:
                rec["current_balance"] = round(random.uniform(45.0, 60.0), 1)
                rec["credits"] = rec["current_balance"]
                log.append(_log(4, rec["employee_id"], f"Banco de horas excedido: {rec['current_balance']}h (limite 40h)", rec["competence"]))
                break
    return log


# ---------------------------------------------------------------------------
# UC5: Interval violation — less than 1h break on >6h journey
# ---------------------------------------------------------------------------

def inject_interval_violation(time_records: List[dict], employees: List[dict]) -> List[dict]:
    affected = _sample_employees(employees, INCONSISTENCY_RATES["interval_violation"])
    emp_ids = {e["employee_id"] for e in affected}
    log = []
    for rec in time_records:
        if rec["employee_id"] in emp_ids and rec["total_hours"] > 6 and rec["interval_minutes"] >= 60:
            rec["interval_minutes"] = random.choice([0, 15, 30])
            log.append(_log(5, rec["employee_id"], f"Intervalo de {rec['interval_minutes']}min em jornada >6h", str(rec["date"])))
            emp_ids.discard(rec["employee_id"])
    return log


# ---------------------------------------------------------------------------
# UC6: Point vs Payroll divergence — payroll has fewer HE hours
# ---------------------------------------------------------------------------

def inject_point_payroll_divergence(payroll: List[dict], time_records: List[dict], employees: List[dict]) -> List[dict]:
    affected = _sample_employees(employees, INCONSISTENCY_RATES["point_vs_payroll_divergence"])
    log = []
    for rec in payroll:
        if any(e["employee_id"] == rec["employee_id"] for e in affected):
            total_he = rec["overtime_50_hours"] + rec["overtime_70_hours"] + rec["overtime_100_hours"]
            if total_he >= 5:
                rec["overtime_50_hours"] = round(total_he * 0.5, 1)
                rec["overtime_50_amount"] = round(rec["overtime_50_amount"] * 0.5, 2)
                rec["gross_total"] = round(rec["gross_total"] * 0.85, 2)
                rec["net_total"] = round(rec["gross_total"] - rec["inss_discount"] - rec["irrf_discount"] - rec["union_discount"] - rec["other_discounts"], 2)
                log.append(_log(6, rec["employee_id"], "Horas extras na folha menores que no ponto", rec["competence"]))
    return log


# ---------------------------------------------------------------------------
# UC7: Payment divergence — bank paid different from payroll net
# ---------------------------------------------------------------------------

def inject_payment_divergence(payments: List[dict], employees: List[dict]) -> List[dict]:
    affected = _sample_employees(employees, INCONSISTENCY_RATES["payment_divergence"])
    log = []
    for rec in payments:
        if any(e["employee_id"] == rec["employee_id"] for e in affected):
            rec["paid_amount"] = round(rec["expected_amount"] * random.uniform(0.75, 0.92), 2)
            rec["payment_status"] = "partial"
            log.append(_log(7, rec["employee_id"], f"Pagamento parcial: R${rec['expected_amount']} esperado, R${rec['paid_amount']} pago", rec["competence"]))
    return log


# ---------------------------------------------------------------------------
# UC8: Missing time records — active employee without point records
# ---------------------------------------------------------------------------

def inject_missing_time_records(time_records: List[dict], employees: List[dict]) -> List[dict]:
    candidates = [e for e in employees if e["status"] == "active" and e["hire_date"] < date(2024, 1, 1)]
    count = max(1, int(len(candidates) * INCONSISTENCY_RATES["missing_time_record"]))
    affected = random.sample(candidates, min(count, len(candidates)))
    affected_ids = {e["employee_id"] for e in affected}
    for r in time_records:
        if r["employee_id"] in affected_ids and r["date"].year == 2024 and r["date"].month >= 6:
            r["total_hours"] = 0
            r["entry_1"] = None
            r["exit_1"] = None
            r["absence_type"] = "missing"
    log = [_log(8, eid, "Funcionário ativo sem registros de ponto no período (06/2024+)", "") for eid in affected_ids]
    return log


# ---------------------------------------------------------------------------
# UC9: Post-termination payment — terminated employee still on payroll
# ---------------------------------------------------------------------------

def inject_post_termination_payment(payroll: List[dict], employees: List[dict]) -> List[dict]:
    terminated = [e for e in employees if e["status"] == "terminated" and e["termination_date"]]
    count = max(1, int(len(terminated) * INCONSISTENCY_RATES["post_termination_payment"]))
    affected = random.sample(terminated, min(count, len(terminated)))
    log = []
    max_pid = max(p["payroll_id"] for p in payroll) if payroll else 0
    for emp in affected:
        term_date = emp["termination_date"]
        # Add fake post-termination payroll records
        for offset in [1, 2]:
            month = term_date.month + offset
            yr = term_date.year
            if month > 12:
                month -= 12
                yr += 1
            if yr > 2025:
                continue
            max_pid += 1
            payroll.append({
                "payroll_id": max_pid, "employee_id": emp["employee_id"],
                "year": yr, "month": month,
                "competence": f"{yr}-{month:02d}",
                "base_salary": emp["base_salary"],
                "overtime_50_hours": 0, "overtime_50_amount": 0.0,
                "overtime_70_hours": 0, "overtime_70_amount": 0.0,
                "overtime_100_hours": 0, "overtime_100_amount": 0.0,
                "night_shift_hours": 0, "night_shift_amount": 0.0,
                "periculosidade_amount": 0.0, "insalubridade_amount": 0.0,
                "dsr_amount": 0.0, "salary_family_amount": 0.0,
                "gross_total": emp["base_salary"],
                "inss_discount": round(emp["base_salary"] * 0.09, 2),
                "irrf_discount": 0.0, "union_discount": 0.0,
                "other_discounts": 0.0, "net_total": emp["base_salary"],
            })
            log.append(_log(9, emp["employee_id"], f"Demitido em {term_date} continua recebendo em {yr}-{month:02d}", f"{yr}-{month:02d}"))
    return log


# ---------------------------------------------------------------------------
# UC13: Periculosidade missing for eligible employee
# ---------------------------------------------------------------------------

def inject_periculosidade_missing(payroll: List[dict], employees: List[dict]) -> List[dict]:
    eligible = [e["employee_id"] for e in employees if e["periculosidade_eligible"] and e["status"] == "active"]
    count = max(1, int(len(eligible) * INCONSISTENCY_RATES["periculosidade_missing"]))
    affected = set(random.sample(eligible, min(count, len(eligible))))
    log = []
    for rec in payroll:
        if rec["employee_id"] in affected and rec["periculosidade_amount"] > 0:
            rec["periculosidade_amount"] = 0.0
            rec["gross_total"] = round(rec["gross_total"] * 0.85, 2)
            rec["net_total"] = round(rec["gross_total"] - rec["inss_discount"] - rec["irrf_discount"] - rec["union_discount"] - rec["other_discounts"], 2)
            log.append(_log(13, rec["employee_id"], "Adicional de periculosidade não aplicado", rec["competence"]))
    return log


# ---------------------------------------------------------------------------
# UC17: CPF divergence between HR and Finance
# ---------------------------------------------------------------------------

def inject_cpf_divergence(employees: List[dict]) -> List[dict]:
    """Add __alternative_cpf field for downstream reconciliation."""
    affected = _sample_employees(employees, INCONSISTENCY_RATES["cpf_divergent"])
    log = []
    for emp in affected:
        emp["__divergent_cpf"] = "".join(str(random.randint(0, 9)) for _ in range(11))
        log.append(_log(17, emp["employee_id"], "CPF divergente entre RH e Financeiro", ""))
    return log


# ---------------------------------------------------------------------------
# UC19: No union defined
# ---------------------------------------------------------------------------

def inject_no_union(employees: List[dict]) -> List[dict]:
    affected = _sample_employees(employees, INCONSISTENCY_RATES["no_union"])
    log = []
    for emp in affected:
        emp["union_id"] = None
        log.append(_log(19, emp["employee_id"], "Funcionário sem sindicato definido", ""))
    return log


# ---------------------------------------------------------------------------
# UC21: Duplicate payment — same event paid twice
# ---------------------------------------------------------------------------

def inject_duplicate_payment(payments: List[dict], employees: List[dict]) -> List[dict]:
    affected = _sample_employees(employees, INCONSISTENCY_RATES["duplicate_payment"])
    log = []
    added = []
    max_id = max(p["payment_id"] for p in payments) if payments else 0
    for emp in affected:
        existing = [p for p in payments if p["employee_id"] == emp["employee_id"]]
        if existing:
            dup = existing[0].copy()
            max_id += 1
            dup["payment_id"] = max_id
            added.append(dup)
            log.append(_log(21, emp["employee_id"], "Pagamento duplicado", dup["competence"]))
    payments.extend(added)
    return log


# ---------------------------------------------------------------------------
# UC25: Weekly limit exceeded — more than 44h (or 30h RN) in a week
# ---------------------------------------------------------------------------

def inject_weekly_limit_exceeded(time_records: List[dict], employees: List[dict]) -> List[dict]:
    affected = _sample_employees(employees, INCONSISTENCY_RATES["weekly_limit_exceeded"])
    log = []
    emp_ids = {e["employee_id"]: e for e in affected}
    for rec in time_records:
        if rec["employee_id"] in emp_ids and rec["total_hours"] > 0 and rec["date"].weekday() < 5:
            rec["total_hours"] += random.choice([1.0, 1.5, 2.0])
            rec["overtime_50"] += 1.0
            if random.random() < 0.3:
                log.append(_log(25, rec["employee_id"], "Jornada semanal acima do limite legal", str(rec["date"])))
    return log


# ---------------------------------------------------------------------------
# UC31: Expired vacation
# ---------------------------------------------------------------------------

def inject_expired_vacation(vacations: List[dict], employees: List[dict]) -> List[dict]:
    affected = _sample_employees(employees, INCONSISTENCY_RATES["expired_vacation"])
    log = []
    for vac in vacations:
        if any(e["employee_id"] == vac["employee_id"] for e in affected):
            if vac["status"] in ("taken", "scheduled", "pending"):
                vac["status"] = "expired"
                vac["scheduled_start"] = None
                vac["scheduled_end"] = None
                vac["days_taken"] = 0
                log.append(_log(31, vac["employee_id"], f"Férias vencidas: {vac['acquisition_start']} a {vac['acquisition_end']}", ""))
    return log


# ---------------------------------------------------------------------------
# UC32: Impending vacation (< 30 days from deadline)
# ---------------------------------------------------------------------------

def inject_impending_vacation(vacations: List[dict], employees: List[dict]) -> List[dict]:
    affected = _sample_employees(employees, INCONSISTENCY_RATES["impending_vacation"])
    log = []
    for vac in vacations:
        if any(e["employee_id"] == vac["employee_id"] for e in affected):
            vac["status"] = "impending"
            vac["scheduled_start"] = date.today() + timedelta(days=random.randint(5, 25))
            log.append(_log(32, vac["employee_id"], f"Férias próximas ao vencimento (prazo: {vac['concession_deadline']})", ""))
    return log


# ---------------------------------------------------------------------------
# Master injector — run all
# ---------------------------------------------------------------------------

def inject_he_by_position_wrong(payroll: List[dict], employees: List[dict], positions: List[dict]) -> List[dict]:
    """UC10: Supervisor-level employees get HE at 50% instead of 80%."""
    pos_map = {p["position_id"]: p for p in positions}
    supervisor_ids = [e["employee_id"] for e in employees
                      if pos_map.get(e["position_id"], {}).get("level") == "supervisor"]
    count = max(1, int(len(supervisor_ids) * 0.3))
    affected = set(random.sample(supervisor_ids, min(count, len(supervisor_ids))))
    log = []
    for rec in payroll:
        if rec["employee_id"] in affected and rec["overtime_50_hours"] > 0:
            rec["overtime_50_amount"] = round(rec["overtime_50_amount"] * 0.5 / 0.8, 2)
            rec["gross_total"] = round(rec["gross_total"], 2)
            rec["net_total"] = round(rec["gross_total"] - rec["inss_discount"] - rec["irrf_discount"] - rec["union_discount"] - rec["other_discounts"], 2)
            log.append(_log(10, rec["employee_id"], "Supervisor: HE paga a 50% em vez de 80% conforme CCT", rec["competence"]))
    return log


def inject_12x36_exceeded(time_records: List[dict], employees: List[dict]) -> List[dict]:
    """UC12: 12x36 worker exceeded 12h shift."""
    candidates = [e for e in employees if e["work_schedule"] == "12x36"]
    count = max(1, int(len(candidates) * 0.15))
    affected = {e["employee_id"] for e in random.sample(candidates, min(count, len(candidates)))}
    log = []
    for rec in time_records:
        if rec["employee_id"] in affected and rec["total_hours"] > 11:
            rec["total_hours"] += random.choice([2.0, 3.0])
            rec["overtime_50"] += 2.0
            log.append(_log(12, rec["employee_id"], f"Jornada 12x36 excedida: {rec['total_hours']}h registradas", str(rec["date"])))
            affected.discard(rec["employee_id"])
    return log


def inject_incompatible_schedule(employees: List[dict]) -> List[dict]:
    """UC20: RN employee on 6x1 instead of 3x3 (operational) or 5x2 (admin)."""
    rn_employees = [e for e in employees if e.get("union_id") == 3]
    count = max(1, int(len(rn_employees) * INCONSISTENCY_RATES["incompatible_schedule"]))
    affected = random.sample(rn_employees, min(count, len(rn_employees)))
    log = []
    for emp in affected:
        old = emp["work_schedule"]
        emp["work_schedule"] = "6x1"
        emp["weekly_hours"] = 44
        log.append(_log(20, emp["employee_id"], f"Escala incompatível: RN deveria ser 3x3 ou 5x2, registrado como {old} -> 6x1", ""))
    return log


def inject_insalubridade_missing(payroll: List[dict], employees: List[dict]) -> List[dict]:
    """UC29: Insalubridade missing for eligible employee."""
    eligible = [e["employee_id"] for e in employees if e.get("insalubridade_eligible") and e["status"] == "active"]
    count = max(1, int(len(eligible) * INCONSISTENCY_RATES["insalubridade_missing"]))
    affected = set(random.sample(eligible, min(count, len(eligible))))
    log = []
    for rec in payroll:
        if rec["employee_id"] in affected and rec["insalubridade_amount"] > 0:
            rec["insalubridade_amount"] = 0.0
            rec["gross_total"] = round(rec["gross_total"] * 0.85, 2)
            rec["net_total"] = round(rec["gross_total"] - rec["inss_discount"] - rec["irrf_discount"] - rec["union_discount"] - rec["other_discounts"], 2)
            log.append(_log(29, rec["employee_id"], "Adicional de insalubridade não aplicado", rec["competence"]))
    return log


def inject_cct_temporal_mismatch(payroll: List[dict], employees: List[dict]) -> List[dict]:
    """UC30: Apply 2025 CCT rule to 2024 period."""
    affected = _sample_employees(employees, INCONSISTENCY_RATES["cct_temporal_mismatch"])
    log = []
    # Mark: payroll in 2024 that uses 2025 rule by adjusting HE rates upward
    for rec in payroll:
        if any(e["employee_id"] == rec["employee_id"] for e in affected) and rec["year"] == 2024 and rec["overtime_50_hours"] > 0:
            rec["overtime_50_amount"] = round(rec["overtime_50_amount"] * 1.1, 2)  # +10% simulated future rule
            rec["gross_total"] = round(rec["gross_total"], 2)
            rec["net_total"] = round(rec["gross_total"] - rec["inss_discount"] - rec["irrf_discount"] - rec["union_discount"] - rec["other_discounts"], 2)
            log.append(_log(30, rec["employee_id"], "Regra CCT 2025 aplicada em competência 2024", rec["competence"]))
    return log


def inject_overlapping_journey(time_records: List[dict], employees: List[dict]) -> List[dict]:
    """UC28: Two overlapping clock entries on same day."""
    affected = _sample_employees(employees, INCONSISTENCY_RATES["overlapping_journey"])
    log = []
    emp_ids = {e["employee_id"] for e in affected}
    for rec in time_records:
        if rec["employee_id"] in emp_ids and rec["total_hours"] > 0:
            rec["__overlap"] = True
            log.append(_log(28, rec["employee_id"], "Jornada sobreposta detectada no ponto", str(rec["date"])))
            emp_ids.discard(rec["employee_id"])
    return log


def inject_dsr_wrong(payroll: List[dict], employees: List[dict]) -> List[dict]:
    """UC14: DSR calculated without considering HE."""
    affected = _sample_employees(employees, INCONSISTENCY_RATES["dsr_wrong"])
    log = []
    for rec in payroll:
        if any(e["employee_id"] == rec["employee_id"] for e in affected) and rec["dsr_amount"] > 0:
            rec["dsr_amount"] = round(rec["dsr_amount"] * 0.5, 2)
            rec["gross_total"] = round(rec["gross_total"], 2)
            rec["net_total"] = round(rec["gross_total"] - rec["inss_discount"] - rec["irrf_discount"] - rec["union_discount"] - rec["other_discounts"], 2)
            log.append(_log(14, rec["employee_id"], "DSR calculado sem considerar horas extras", rec["competence"]))
    return log


def inject_holiday_without_extra(payroll: List[dict], time_records: List[dict], employees: List[dict]) -> List[dict]:
    """UC15: Holiday worked without extra pay."""
    holiday_workers = set()
    for tr in time_records:
        if tr.get("is_holiday") and tr["total_hours"] > 0:
            holiday_workers.add(tr["employee_id"])
    candidates = [e for e in employees if e["employee_id"] in holiday_workers]
    count = max(1, int(len(candidates) * INCONSISTENCY_RATES["holiday_without_extra"]))
    affected = {e["employee_id"] for e in random.sample(candidates, min(count, len(candidates)))}
    log = []
    for rec in payroll:
        if rec["employee_id"] in affected and rec["overtime_100_hours"] > 0:
            rec["overtime_100_hours"] = 0
            rec["overtime_100_amount"] = 0.0
            rec["gross_total"] = round(rec["gross_total"], 2)
            rec["net_total"] = round(rec["gross_total"] - rec["inss_discount"] - rec["irrf_discount"] - rec["union_discount"] - rec["other_discounts"], 2)
            log.append(_log(15, rec["employee_id"], "Feriado trabalhado sem adicional de 100%", rec["competence"]))
    return log


def inject_hour_bank_negative_exceeded(hour_bank: List[dict], employees: List[dict]) -> List[dict]:
    """UC16: Negative hour bank above allowed limit."""
    affected = _sample_employees(employees, INCONSISTENCY_RATES["hour_bank_negative_exceeded"])
    log = []
    for rec in hour_bank:
        if any(e["employee_id"] == rec["employee_id"] for e in affected):
            if rec["current_balance"] >= 0:
                rec["current_balance"] = round(random.uniform(-30.0, -15.0), 1)
                rec["negative_balance"] = True
                log.append(_log(16, rec["employee_id"], f"Banco de horas negativo: {rec['current_balance']}h (acima do permitido)", rec["competence"]))
                break
    return log


def inject_orphan_payment(payments: List[dict], employees: List[dict]) -> List[dict]:
    """UC18: Payment without corresponding payroll event."""
    affected = _sample_employees(employees, INCONSISTENCY_RATES["orphan_payment"])
    log = []
    max_id = max(p["payment_id"] for p in payments) if payments else 0
    for emp in affected:
        max_id += 1
        payments.append({
            "payment_id": max_id, "employee_id": emp["employee_id"],
            "year": 2024, "month": 6, "competence": "2024-06",
            "expected_amount": 0.0, "paid_amount": round(random.uniform(200, 800), 2),
            "payment_date": date(2024, 7, 5), "payment_status": "paid",
            "receipt_code": f"ORPHAN-{max_id:04d}",
        })
        log.append(_log(18, emp["employee_id"], "Pagamento sem evento correspondente na folha", "2024-06"))
    return log


def inject_overtime_without_approval(time_records: List[dict], employees: List[dict]) -> List[dict]:
    """UC22: >2h daily overtime without approval."""
    affected = _sample_employees(employees, INCONSISTENCY_RATES["overtime_without_approval"])
    emp_ids = {e["employee_id"] for e in affected}
    log = []
    for rec in time_records:
        if rec["employee_id"] in emp_ids and rec["overtime_50"] + rec["overtime_70"] > 2:
            rec["has_overtime_approval"] = False
            log.append(_log(22, rec["employee_id"], "HE >2h sem aprovação do gestor", str(rec["date"])))
            emp_ids.discard(rec["employee_id"])
    return log


def inject_promotion_without_adjustment(salary_history: List[dict], employees: List[dict]) -> List[dict]:
    """UC23: Promotion recorded but salary stayed the same."""
    promos = [h for h in salary_history if h["change_reason"] == "promotion"]
    count = max(1, int(len(promos) * INCONSISTENCY_RATES["promotion_without_adjustment"]))
    affected = random.sample(promos, min(count, len(promos)))
    log = []
    for rec in affected:
        rec["new_salary"] = rec["previous_salary"]
        log.append(_log(23, rec["employee_id"], f"Promoção sem reajuste salarial em {rec['effective_date']}", ""))
    return log


def inject_night_shift_outside_range(time_records: List[dict], employees: List[dict]) -> List[dict]:
    """UC24: Night additional applied before 22h — force a night entry starting at 20h."""
    affected = _sample_employees(employees, INCONSISTENCY_RATES["night_shift_outside_range"])
    log = []
    for rec in time_records:
        if any(e["employee_id"] == rec["employee_id"] for e in affected) and rec["total_hours"] > 0 and rec["entry_1"]:
            entry_h = rec["entry_1"].hour
            if 6 <= entry_h <= 21:  # daytime entry — force night annotation
                rec["night_hours"] = max(rec["night_hours"], random.uniform(1.0, 3.0))
                log.append(_log(24, rec["employee_id"], f"Adicional noturno aplicado fora da faixa 22h-5h (entry: {rec['entry_1']})", str(rec["date"])))
                break
    return log


def inject_wrong_union_cct(employees: List[dict]) -> List[dict]:
    """UC26: Employee assigned to wrong union's CCT."""
    candidates = [e for e in employees if e.get("union_id") in (1, 2, 3)]
    count = max(1, int(len(candidates) * INCONSISTENCY_RATES["wrong_union_cct"]))
    affected = random.sample(candidates, min(count, len(candidates)))
    log = []
    for emp in affected:
        original = emp["union_id"]
        if original == 1:
            emp["union_id"] = 2
        elif original == 2:
            emp["union_id"] = 1
        elif original == 3:
            emp["union_id"] = 1
        log.append(_log(26, emp["employee_id"], f"CCT do sindicato errado aplicada (era {original}, virou {emp['union_id']})", ""))
    return log


def inject_absence_deducted_wrongly(time_records: List[dict], employees: List[dict]) -> List[dict]:
    """UC27: Medical absence wrongly deducted (certificate ignored)."""
    affected = _sample_employees(employees, INCONSISTENCY_RATES["absence_deducted_wrongly"])
    emp_ids = {e["employee_id"] for e in affected}
    log = []
    for rec in time_records:
        if rec["employee_id"] in emp_ids and rec["absence_type"] == "medical":
            rec["absence_type"] = "unjustified"
            log.append(_log(27, rec["employee_id"], "Falta com atestado médico descontada como injustificada", str(rec["date"])))
            emp_ids.discard(rec["employee_id"])
    return log


def inject_cct_change_between_years(payroll: List[dict], employees: List[dict]) -> List[dict]:
    """UC11: 2023 CCT rule applied to 2024 period (HE Sunday 80% instead of 100%)."""
    affected = _sample_employees(employees, INCONSISTENCY_RATES.get("cct_temporal_mismatch", 0.02))
    log = []
    for rec in payroll:
        if any(e["employee_id"] == rec["employee_id"] for e in affected) and rec["year"] == 2024:
            if rec["overtime_100_hours"] > 0:
                old = rec["overtime_100_amount"]
                rec["overtime_100_amount"] = round(rec["overtime_100_hours"] * rec["base_salary"] / 173.33 * 0.80, 2)
                rec["gross_total"] = round(rec["gross_total"] - old + rec["overtime_100_amount"], 2)
                rec["net_total"] = round(rec["gross_total"] - rec["inss_discount"] - rec["irrf_discount"] - rec["union_discount"] - rec["other_discounts"], 2)
                log.append(_log(11, rec["employee_id"], "Regra CCT 2023 (HE dom 80%) aplicada em 2024 (deveria 100%)", rec["competence"]))
    return log


def inject_all(payroll: List[dict], time_records: List[dict], payments: List[dict],
               hour_bank: List[dict], vacations: List[dict], employees: List[dict],
               holidays: List[dict], positions: List[dict] = None,
               salary_history: List[dict] = None) -> List[dict]:
    logs = []
    logs.extend(inject_he_progressive_wrong(payroll, employees))
    logs.extend(inject_he_sunday_wrong(payroll, employees))
    logs.extend(inject_night_shift_missing(payroll, employees))
    logs.extend(inject_hour_bank_exceeded(hour_bank, employees))
    logs.extend(inject_interval_violation(time_records, employees))
    logs.extend(inject_point_payroll_divergence(payroll, time_records, employees))
    logs.extend(inject_payment_divergence(payments, employees))
    logs.extend(inject_missing_time_records(time_records, employees))
    logs.extend(inject_post_termination_payment(payroll, employees))
    logs.extend(inject_periculosidade_missing(payroll, employees))
    logs.extend(inject_cpf_divergence(employees))
    logs.extend(inject_no_union(employees))
    logs.extend(inject_duplicate_payment(payments, employees))
    logs.extend(inject_weekly_limit_exceeded(time_records, employees))
    logs.extend(inject_expired_vacation(vacations, employees))
    logs.extend(inject_impending_vacation(vacations, employees))
    if positions:
        logs.extend(inject_he_by_position_wrong(payroll, employees, positions))
    logs.extend(inject_12x36_exceeded(time_records, employees))
    logs.extend(inject_incompatible_schedule(employees))
    logs.extend(inject_insalubridade_missing(payroll, employees))
    logs.extend(inject_cct_temporal_mismatch(payroll, employees))
    logs.extend(inject_overlapping_journey(time_records, employees))
    logs.extend(inject_dsr_wrong(payroll, employees))
    logs.extend(inject_holiday_without_extra(payroll, time_records, employees))
    logs.extend(inject_hour_bank_negative_exceeded(hour_bank, employees))
    logs.extend(inject_orphan_payment(payments, employees))
    logs.extend(inject_overtime_without_approval(time_records, employees))
    if salary_history:
        logs.extend(inject_promotion_without_adjustment(salary_history, employees))
    logs.extend(inject_night_shift_outside_range(time_records, employees))
    logs.extend(inject_wrong_union_cct(employees))
    logs.extend(inject_absence_deducted_wrongly(time_records, employees))
    logs.extend(inject_cct_change_between_years(payroll, employees))
    return logs
