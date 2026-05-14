import csv
from collections import Counter

counts = Counter()
with open("data/bronze/hr_system/employees.csv", encoding="utf-8") as f:
    reader = csv.DictReader(f, delimiter=";")
    for row in reader:
        sched = row["work_schedule"]
        st = row.get("shift_type", "?")
        e1 = row.get("shift_entry_1", "?")
        s1 = row.get("shift_exit_1", "?")
        e2 = row.get("shift_entry_2", "")
        s2 = row.get("shift_exit_2", "")
        key = f"{sched} {st} [{e1}-{s1}/{e2}-{s2}]"
        counts[key] += 1

print("Shift distributions:")
for k, v in sorted(counts.items()):
    print(f"  {v:>5} x {k}")

print(f"\nTotal employees with shift_entry_1: ", end="")
with open("data/bronze/hr_system/employees.csv", encoding="utf-8") as f:
    reader = csv.DictReader(f, delimiter=";")
    total = 0
    has_shift = 0
    for row in reader:
        total += 1
        if row.get("shift_entry_1"):
            has_shift += 1
    print(f"{has_shift}/{total}")
