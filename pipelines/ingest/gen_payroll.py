import random
from typing import List, Dict
from datetime import date

from config import CCT_RULES, SEED

random.seed(SEED + 2)


def _get_cct(union_id: int):
    return CCT_RULES[union_id - 1] if 1 <= union_id <= len(CCT_RULES) else CCT_RULES[0]


def generate_payroll(employees: List[dict], time_records: List[dict]) -> List[dict]:
    rows = []
    pid = 1

    # Group time records by employee and month
    tr_by_emp_month: Dict[int, Dict[str, List[dict]]] = {}
    for tr in time_records:
        emp_id = tr["employee_id"]
        key = f"{tr['date'].year}-{tr['date'].month:02d}"
        tr_by_emp_month.setdefault(emp_id, {}).setdefault(key, []).append(tr)

    for emp in employees:
        if emp["status"] == "terminated":
            continue  # will handle terminated separately

        union_rules = _get_cct(emp["union_id"])
        salary = emp["base_salary"]
        hourly_rate = salary / (emp["weekly_hours"] * 4.33)

        for year in range(2024, 2026):
            for month in range(1, 13):
                key = f"{year}-{month:02d}"
                # Skip future months
                if date(year, month, 1) > date(2025, 12, 1):
                    continue

                month_tr = tr_by_emp_month.get(emp["employee_id"], {}).get(key, [])

                sum_ot_50 = sum(t["overtime_50"] for t in month_tr)
                sum_ot_70 = sum(t["overtime_70"] for t in month_tr)
                sum_ot_100 = sum(t["overtime_100"] for t in month_tr)
                sum_night = sum(t["night_hours"] for t in month_tr)

                ot_50_amount = round(sum_ot_50 * hourly_rate * (1 + union_rules.he_first_hour_percent), 2)
                ot_70_amount = round(sum_ot_70 * hourly_rate * (1 + union_rules.he_additional_hours_percent), 2)
                ot_100_amount = round(sum_ot_100 * hourly_rate * (1 + union_rules.he_sunday_percent), 2)

                night_amount = round(sum_night * hourly_rate * (1 + union_rules.night_shift_percent), 2)

                periculosidade = round(salary * union_rules.periculosidade_percent, 2) if emp["periculosidade_eligible"] else 0.0
                insalubridade = round(salary * union_rules.insalubridade_percent, 2) if emp["insalubridade_eligible"] else 0.0

                # DSR: simplified = avg hourly rate * (Sundays+Holidays worked) * 1.5
                sunday_hours = sum(t["total_hours"] for t in month_tr if t.get("is_sunday"))
                holiday_hours = sum(t["total_hours"] for t in month_tr if t.get("is_holiday"))
                dsr = round((sunday_hours + holiday_hours) * hourly_rate * 1.5, 2)

                salary_family = 0.0
                if emp["dependents"] > 0 and salary < 1800:
                    salary_family = round(min(emp["dependents"], 3) * 62.04, 2)

                gross = round(salary + ot_50_amount + ot_70_amount + ot_100_amount +
                         night_amount + periculosidade + insalubridade + dsr + salary_family, 2)

                # Discounts (simplified)
                inss = round(gross * 0.09, 2)
                irrf = round(max(0, (gross - 2500) * 0.075), 2) if gross > 2800 else 0.0
                union_disc = round(salary * 0.01, 2)
                other = round(salary * 0.005, 2)  # vale-transporte etc.

                net = round(gross - inss - irrf - union_disc - other, 2)

                # Adjustments for specific months
                if month == union_rules.salary_adjustment_percent:
                    pass  # could apply later

                rows.append({
                    "payroll_id": pid,
                    "employee_id": emp["employee_id"],
                    "year": year,
                    "month": month,
                    "competence": key,
                    "base_salary": salary,
                    "overtime_50_hours": round(sum_ot_50, 1),
                    "overtime_50_amount": ot_50_amount,
                    "overtime_70_hours": round(sum_ot_70, 1),
                    "overtime_70_amount": ot_70_amount,
                    "overtime_100_hours": round(sum_ot_100, 1),
                    "overtime_100_amount": ot_100_amount,
                    "night_shift_hours": round(sum_night, 1),
                    "night_shift_amount": night_amount,
                    "periculosidade_amount": periculosidade,
                    "insalubridade_amount": insalubridade,
                    "dsr_amount": dsr,
                    "salary_family_amount": salary_family,
                    "gross_total": gross,
                    "inss_discount": inss,
                    "irrf_discount": irrf,
                    "union_discount": union_disc,
                    "other_discounts": other,
                    "net_total": net,
                })
                pid += 1

    return rows
