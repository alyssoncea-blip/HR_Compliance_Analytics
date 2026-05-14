import random
from typing import List
from datetime import date, timedelta

from config import SEED

random.seed(SEED + 4)


def _random_date(start: date, end: date) -> date:
    delta = (end - start).days
    return start + timedelta(days=random.randint(0, max(0, delta)))


def generate_vacations(employees: List[dict]) -> List[dict]:
    rows = []
    vid = 1
    for emp in employees:
        if emp["status"] == "terminated":
            continue
        hire = emp["hire_date"]
        for cycle in range(3):
            aq_start = hire + timedelta(days=365 * cycle)
            aq_end = aq_start + timedelta(days=364)
            deadline = aq_end + timedelta(days=365)
            if aq_end > date(2025, 12, 31):
                continue

            # ~70% taken, 15% scheduled, 10% expired, 5% pending
            r = random.random()
            if r < 0.70:
                taken_start = _random_date(aq_start + timedelta(days=30), min(aq_end, date(2025, 12, 31)))
                taken_end = taken_start + timedelta(days=min(30, random.randint(10, 30)))
                status = "taken"
                days_taken = (taken_end - taken_start).days
                days_sold = random.choice([0, 0, 0, 5, 10])
                payment = round(emp["base_salary"] * (days_taken / 30) * 1.33, 2)
                rows.append({
                    "vacation_id": vid, "employee_id": emp["employee_id"],
                    "acquisition_start": aq_start, "acquisition_end": aq_end,
                    "concession_deadline": deadline,
                    "scheduled_start": taken_start, "scheduled_end": taken_end,
                    "days_taken": days_taken, "days_sold": days_sold,
                    "payment_amount": payment, "status": status,
                })
            elif r < 0.85:
                sched_start = _random_date(max(aq_start + timedelta(days=30), date.today()), min(deadline, date(2025, 12, 31)))
                rows.append({
                    "vacation_id": vid, "employee_id": emp["employee_id"],
                    "acquisition_start": aq_start, "acquisition_end": aq_end,
                    "concession_deadline": deadline,
                    "scheduled_start": sched_start, "scheduled_end": sched_start + timedelta(days=30),
                    "days_taken": 0, "days_sold": 0,
                    "payment_amount": 0.0, "status": "scheduled",
                })
            elif r < 0.95:
                rows.append({
                    "vacation_id": vid, "employee_id": emp["employee_id"],
                    "acquisition_start": aq_start, "acquisition_end": aq_end,
                    "concession_deadline": deadline,
                    "scheduled_start": None, "scheduled_end": None,
                    "days_taken": 0, "days_sold": 0,
                    "payment_amount": 0.0, "status": "expired",
                })
            else:
                rows.append({
                    "vacation_id": vid, "employee_id": emp["employee_id"],
                    "acquisition_start": aq_start, "acquisition_end": aq_end,
                    "concession_deadline": deadline,
                    "scheduled_start": None, "scheduled_end": None,
                    "days_taken": 0, "days_sold": 0,
                    "payment_amount": 0.0, "status": "pending",
                })
            vid += 1
    return rows


def generate_leaves(employees: List[dict]) -> List[dict]:
    rows = []
    lid = 1
    for emp in employees:
        if random.random() > 0.20:
            continue
        start = _random_date(date(2024, 3, 1), date(2025, 10, 1))
        days = random.choice([3, 5, 7, 10, 15, 30])
        end = start + timedelta(days=days)
        ltype = random.choice(["medical", "medical", "medical", "maternity", "bereavement", "marriage"])
        rows.append({
            "leave_id": lid,
            "employee_id": emp["employee_id"],
            "start_date": start,
            "end_date": end,
            "type": ltype,
            "certificate_code": f"ATEST-{lid:04d}" if ltype == "medical" else None,
            "status": "expired" if end < date(2025, 12, 31) else "active",
            "days_count": days,
        })
        lid += 1
    return rows


def generate_salary_history(employees: List[dict], positions: List[dict]) -> List[dict]:
    rows = []
    hid = 1
    for emp in employees:
        if random.random() > 0.15:
            continue
        pos = next((p for p in positions if p["position_id"] == emp["position_id"]), positions[0])
        new_salary = round(emp["base_salary"] * random.uniform(1.05, 1.25), 2)
        rows.append({
            "history_id": hid,
            "employee_id": emp["employee_id"],
            "effective_date": _random_date(emp["hire_date"] + timedelta(days=180), date(2025, 6, 1)),
            "previous_position_id": emp["position_id"],
            "new_position_id": emp["position_id"],
            "previous_salary": emp["base_salary"],
            "new_salary": new_salary,
            "change_reason": random.choice(["promotion", "adjustment", "reclassification"]),
            "approved_by": random.choice(["Gestor RH", "Diretor", "Coordenador"]),
        })
        hid += 1
    return rows


def generate_terminations(employees: List[dict]) -> List[dict]:
    rows = []
    for emp in employees:
        if emp["status"] != "terminated" or not emp["termination_date"]:
            continue
        rows.append({
            "termination_id": emp["employee_id"],
            "employee_id": emp["employee_id"],
            "termination_date": emp["termination_date"],
            "type": emp["termination_type"],
            "severance_paid": round(emp["base_salary"] * random.uniform(1.5, 4.0), 2),
            "has_homologation": random.random() < 0.80,
        })
    return rows


def generate_hour_bank(employees: List[dict], time_records: List[dict]) -> List[dict]:
    rows = []
    hbid = 1
    from collections import defaultdict

    # Aggregate overtime per employee per month
    emp_month_ot = defaultdict(lambda: defaultdict(float))
    for tr in time_records:
        key = f"{tr['date'].year}-{tr['date'].month:02d}"
        emp_month_ot[tr["employee_id"]][key] += tr["overtime_50"] + tr["overtime_70"] + tr["overtime_100"]

    for emp in employees:
        prev_balance = 0.0
        for year in range(2024, 2026):
            for month in range(1, 13):
                key = f"{year}-{month:02d}"
                if date(year, month, 1) > date(2025, 12, 1):
                    continue

                credits = emp_month_ot[emp["employee_id"]].get(key, 0.0)
                # Debits: absences
                debits = 0.0
                negative = prev_balance + credits < 0

                rows.append({
                    "hour_bank_id": hbid,
                    "employee_id": emp["employee_id"],
                    "year": year,
                    "month": month,
                    "competence": key,
                    "previous_balance": round(prev_balance, 1),
                    "credits": round(credits, 1),
                    "debits": round(debits, 1),
                    "current_balance": round(prev_balance + credits - debits, 1),
                    "negative_balance": negative,
                })
                prev_balance = prev_balance + credits - debits
                hbid += 1
    return rows
