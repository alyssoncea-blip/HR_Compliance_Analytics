import random
from typing import List
from datetime import date, timedelta

from config import SEED

random.seed(SEED + 3)


def generate_bank_payments(employees: List[dict], payroll: List[dict]) -> List[dict]:
    rows = []
    payid = 1

    for rec in payroll:
        pay_date = date(rec["year"], rec["month"], 1) + timedelta(days=5)
        net = rec["net_total"]

        # ~95% match, ~5% divergence
        paid = net
        status = "paid"
        if random.random() < 0.05:
            paid = round(net * random.uniform(0.7, 0.95), 2)
            status = "partial"

        rows.append({
            "payment_id": payid,
            "employee_id": rec["employee_id"],
            "year": rec["year"],
            "month": rec["month"],
            "competence": rec["competence"],
            "expected_amount": net,
            "paid_amount": paid,
            "payment_date": pay_date,
            "payment_status": status,
            "receipt_code": f"REC-{rec['year']}{rec['month']:02d}-{rec['employee_id']:04d}",
        })
        payid += 1

    return rows
