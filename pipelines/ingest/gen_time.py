import random
from datetime import date, timedelta, time
from typing import List, Dict, Optional, Tuple

from config import CCT_RULES, PERIOD_START, PERIOD_END, SEED

random.seed(SEED + 1)


def _is_weekend(d: date) -> bool:
    return d.weekday() >= 5


def _is_sunday(d: date) -> bool:
    return d.weekday() == 6


def _build_holiday_set(holidays: List[dict]) -> Dict[date, str]:
    return {h["date"]: h["name"] for h in holidays}


def _parse_time(s: Optional[str]) -> Optional[time]:
    if not s:
        return None
    parts = s.split(":")
    return time(int(parts[0]), int(parts[1]))


def _calc_hours(e1: time, s1: time, e2: Optional[time], s2: Optional[time]) -> float:
    """Calculate effective work hours from shift times. Handles midnight crossover."""
    def _diff(start: time, end: time) -> float:
        h = end.hour - start.hour + (end.minute - start.minute) / 60.0
        if h < 0:
            h += 24  # crosses midnight
        return max(0, h)

    h = _diff(e1, s1)
    if e2 and s2:
        h += _diff(e2, s2)
    return h


def _apply_overtime(exit_2: time, max_extra: float = 3.0) -> Tuple[time, float, float]:
    """Apply random overtime. Returns (new_exit_2, ot_50, ot_70)."""
    extra = random.choice([0, 0, 0, 0, 1.0, 1.5, 2.0, 2.5, 3.0])
    if extra == 0:
        return exit_2, 0.0, 0.0
    new_h = min(exit_2.hour + int(extra), 23)
    new_exit = time(new_h, 0)
    if extra > 1.0:
        return new_exit, 1.0, extra - 1.0
    return new_exit, extra, 0.0


def _work_hours_5x2(emp: dict, d: date, cct) -> dict:
    """5x2 schedule from employee's registered shift."""
    if _is_weekend(d):
        return _zero_day()

    e1 = _parse_time(emp["shift_entry_1"])
    s1 = _parse_time(emp["shift_exit_1"])
    e2 = _parse_time(emp.get("shift_entry_2"))
    s2 = _parse_time(emp.get("shift_exit_2"))

    base = _calc_hours(e1, s1, e2, s2) if e1 and s1 else cct.standard_weekly_hours / 5
    ot_50, ot_70, ot_100 = 0.0, 0.0, 0.0

    s2_new = s2
    if s2:
        s2_new, ot_50, ot_70 = _apply_overtime(s2)

    total = base + ot_50 + ot_70

    return {
        "total_hours": round(total, 1), "overtime_50": round(ot_50, 1),
        "overtime_70": round(ot_70, 1), "overtime_100": 0.0,
        "night_hours": 0.0, "night_overtime": 0.0,
        "entry_1": e1, "exit_1": s1, "entry_2": e2, "exit_2": s2_new,
        "interval_min": 60, "absence_type": None,
        "is_holiday": False, "is_sunday": False, "has_approval": True,
    }


def _work_hours_6x1(emp: dict, d: date, cct) -> dict:
    """6x1: Mon-Sat, Sunday off."""
    if _is_sunday(d):
        return _zero_day()

    e1 = _parse_time(emp["shift_entry_1"])
    s1 = _parse_time(emp["shift_exit_1"])
    e2 = _parse_time(emp.get("shift_entry_2"))
    s2 = _parse_time(emp.get("shift_exit_2"))

    # Saturday: 4h (half shift)
    if d.weekday() == 5:
        base = 4.0
        e2 = None
        s2 = None
    else:
        base = _calc_hours(e1, s1, e2, s2) if e1 and s1 else 8.0

    ot_50, ot_70, ot_100 = 0.0, 0.0, 0.0
    s2_new = s2
    if s2 and random.random() < 0.15:
        s2_new, ot_50, _ = _apply_overtime(s2, 2.0)
    elif not s2 and e1 and random.random() < 0.15:
        s1_new = time(min(s1.hour + 2, 23), 0)
        return {
            "total_hours": round(base + 2, 1), "overtime_50": 2.0,
            "overtime_70": 0.0, "overtime_100": 0.0,
            "night_hours": 0.0, "night_overtime": 0.0,
            "entry_1": e1, "exit_1": s1_new, "entry_2": None, "exit_2": None,
            "interval_min": 60, "absence_type": None,
            "is_holiday": False, "is_sunday": False, "has_approval": True,
        }

    total = base + ot_50

    return {
        "total_hours": round(total, 1), "overtime_50": round(ot_50, 1),
        "overtime_70": 0.0, "overtime_100": 0.0,
        "night_hours": 0.0, "night_overtime": 0.0,
        "entry_1": e1, "exit_1": s1, "entry_2": e2, "exit_2": s2_new,
        "interval_min": 60, "absence_type": None,
        "is_holiday": False, "is_sunday": False, "has_approval": True,
    }


def _work_hours_12x36(emp: dict, d: date, cct) -> dict:
    """12x36: work day, off day, alternating."""
    start = date(2024, 1, 1)
    delta = (d - start).days
    if delta % 2 != 0:
        return _zero_day()

    e1 = _parse_time(emp["shift_entry_1"])
    s1 = _parse_time(emp["shift_exit_1"])
    e2 = _parse_time(emp.get("shift_entry_2"))
    s2 = _parse_time(emp.get("shift_exit_2"))

    base = _calc_hours(e1, s1, e2, s2) if e1 and s1 else 11.0
    ot = 0.0
    s2_new = s2
    if s2 and random.random() < 0.10:
        s2_new = time(min(s2.hour + 1, 23), 0)
        ot = 1.0

    return {
        "total_hours": round(base + ot, 1), "overtime_50": round(ot, 1),
        "overtime_70": 0.0, "overtime_100": 0.0,
        "night_hours": 0.0, "night_overtime": 0.0,
        "entry_1": e1, "exit_1": s1, "entry_2": e2, "exit_2": s2_new,
        "interval_min": 60, "absence_type": None,
        "is_holiday": False, "is_sunday": _is_sunday(d), "has_approval": True,
    }


def _work_hours_3x3(emp: dict, d: date, cct) -> dict:
    """3x3: RN operational schedule."""
    start = date(2024, 1, 1)
    delta = (d - start).days
    cycle_pos = delta % 6
    if cycle_pos >= 3:
        return _zero_day()

    e1 = _parse_time(emp["shift_entry_1"])
    s1 = _parse_time(emp["shift_exit_1"])
    e2 = _parse_time(emp.get("shift_entry_2"))
    s2 = _parse_time(emp.get("shift_exit_2"))

    base = _calc_hours(e1, s1, e2, s2) if e1 and s1 else 11.0
    night_h = 0.0
    ot = 0.0

    s2_new = s2
    if s2 and random.random() < 0.10:
        s2_new = time(min(s2.hour + 1, 23), 0)
        ot = 1.0

    # If night shift (registered shift_entry_1 starts at 19h)
    if e1 and e1.hour >= 18:
        night_h = base
        base = 0

    return {
        "total_hours": round(base + ot, 1), "overtime_50": round(ot, 1),
        "overtime_70": 0.0, "overtime_100": 0.0,
        "night_hours": round(night_h, 1), "night_overtime": 0.0,
        "entry_1": e1, "exit_1": s1, "entry_2": e2, "exit_2": s2_new,
        "interval_min": 60, "absence_type": None,
        "is_holiday": False, "is_sunday": _is_sunday(d), "has_approval": True,
    }


def _zero_day() -> dict:
    return {
        "total_hours": 0, "overtime_50": 0, "overtime_70": 0, "overtime_100": 0,
        "night_hours": 0, "night_overtime": 0,
        "entry_1": None, "exit_1": None, "entry_2": None, "exit_2": None,
        "interval_min": 0, "absence_type": None,
        "is_holiday": False, "is_sunday": False, "has_approval": True,
    }


SCHEDULE_FUNCS = {
    "5x2": _work_hours_5x2,
    "6x1": _work_hours_6x1,
    "12x36": _work_hours_12x36,
    "3x3": _work_hours_3x3,
}


def generate_time_records(employees: List[dict], holidays: List[dict]) -> List[dict]:
    rows = []
    holiday_map = _build_holiday_set(holidays)
    cct_by_union = {i + 1: c for i, c in enumerate(CCT_RULES)}

    rid = 1
    current = PERIOD_START
    while current <= PERIOD_END:
        for emp in employees:
            if emp.get("status") == "terminated" and emp.get("termination_date") and current >= emp["termination_date"]:
                continue
            if emp.get("hire_date") and emp["hire_date"] > current:
                continue
            if emp.get("termination_date") and current >= emp["termination_date"]:
                continue

            schedule = emp.get("work_schedule", "5x2")
            union_rules = cct_by_union.get(emp.get("union_id", 1), CCT_RULES[0])
            func = SCHEDULE_FUNCS.get(schedule, _work_hours_5x2)
            result = func(emp, current, union_rules)

            # ~2% absence rate
            if random.random() < 0.02 and result["total_hours"] > 0:
                atype = random.choice(["medical", "unjustified"])
                result = dict(_zero_day())
                result["absence_type"] = atype

            is_hol = current in holiday_map

            if is_hol and result["total_hours"] > 0:
                result["is_holiday"] = True
                result["overtime_100"] = result["total_hours"]
                result["overtime_50"] = 0.0
                result["overtime_70"] = 0.0

            rows.append({
                "record_id": rid,
                "employee_id": emp["employee_id"],
                "date": current,
                "entry_1": result["entry_1"],
                "exit_1": result["exit_1"],
                "entry_2": result["entry_2"],
                "exit_2": result["exit_2"],
                "total_hours": result["total_hours"],
                "overtime_50": result["overtime_50"],
                "overtime_70": result["overtime_70"],
                "overtime_100": result["overtime_100"],
                "night_hours": result["night_hours"],
                "night_overtime": result["night_overtime"],
                "interval_minutes": result["interval_min"],
                "absence_type": result["absence_type"],
                "is_holiday": result["is_holiday"],
                "is_sunday": result["is_sunday"],
                "has_overtime_approval": result["has_approval"],
            })
            rid += 1
        current += timedelta(days=1)

    return rows
