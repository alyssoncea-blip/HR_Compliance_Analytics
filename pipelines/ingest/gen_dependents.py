import random
from typing import List, Dict
from datetime import date, timedelta

from config import SEED, DEPENDENT_PERCENTAGE, MAX_DEPENDENTS_PER_EMPLOYEE, DEPENDENT_AGES_RANGE

random.seed(SEED + 6)

FIRST_NAMES_M = [
    "João", "Carlos", "Antonio", "Francisco", "José", "Pedro", "Lucas", "Marcos",
    "Paulo", "Rafael", "Fernando", "Roberto", "Thiago", "Eduardo", "Bruno",
    "Felipe", "André", "Gabriel", "Samuel", "Miguel", "Arthur", "Heitor",
]
FIRST_NAMES_F = [
    "Maria", "Ana", "Carla", "Juliana", "Fernanda", "Patrícia", "Amanda",
    "Camila", "Letícia", "Vanessa", "Luciana", "Rebeca", "Rafaela", "Tatiane",
    "Bianca", "Priscila", "Daniela", "Renata", "Aline", "Cristiane", "Sofia",
    "Isabela", "Larissa",
]
LAST_NAMES = [
    "Silva", "Santos", "Oliveira", "Souza", "Lima", "Pereira", "Costa",
    "Ferreira", "Almeida", "Rodrigues", "Nascimento", "Araújo", "Carvalho",
    "Gomes", "Martins", "Barbosa", "Ribeiro", "Dias", "Moreira", "Teixeira",
    "Monteiro", "Vieira", "Cavalcanti", "Mendes", "Cardoso", "Correia",
]

RELATIONSHIPS = ["filho", "filha", "conjuge", "enteado", "enteada", "outro"]


def _cpf_dependents() -> str:
    return "".join(str(random.randint(0, 9)) for _ in range(11))


def generate_dependents(employees: List[dict]) -> List[dict]:
    rows = []
    did = 1

    for emp in employees:
        if emp["status"] != "active":
            continue
        if random.random() > DEPENDENT_PERCENTAGE:
            continue

        num = random.choices(
            [1, 2, 3, 4, 5],
            weights=[0.40, 0.30, 0.18, 0.08, 0.04],
            k=1,
        )[0]
        num = min(num, MAX_DEPENDENTS_PER_EMPLOYEE)

        employee_last = emp["name"].split()[-1]
        emp_birth = emp["birth_date"]
        if isinstance(emp_birth, str):
            from datetime import date as dt
            emp_birth = dt.fromisoformat(emp_birth)
        emp_age = date.today().year - emp_birth.year

        for _ in range(num):
            is_adult = random.random() < 0.15  # 15% adult dependents (spouse, etc.)
            if is_adult:
                age = random.randint(18, 70)
                rel = random.choice(["conjuge", "conjuge"])
            else:
                age = random.randint(0, 17)
                rel = random.choice(["filho", "filha", "filho", "filha", "enteado", "enteada"])

            gender_dep = "M" if rel in ("filho", "enteado", "conjuge") and random.random() < 0.7 else "F"
            first = random.choice(FIRST_NAMES_M if gender_dep == "M" else FIRST_NAMES_F)
            last = employee_last if random.random() < 0.60 else random.choice(LAST_NAMES)

            birth_year = date.today().year - age
            birth_month = random.randint(1, 12)
            birth_day = random.randint(1, 28)
            birth = date(birth_year, birth_month, birth_day)

            rows.append({
                "dependent_id": did,
                "employee_id": emp["employee_id"],
                "name": f"{first} {last}",
                "cpf": _cpf_dependents(),
                "birth_date": birth,
                "age": age,
                "relationship": rel,
                "gender": gender_dep,
            })
            did += 1

    return rows
